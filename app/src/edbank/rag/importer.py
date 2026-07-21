import csv
import hashlib
import io
import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from edbank.config import settings
from edbank.rag.embeddings import embed_passages
from edbank.rag.schemas import ImportResponse

logger = logging.getLogger(__name__)

_ORA_PATTERN = re.compile(r"^ORA-\d{5}$")
OPTIONAL_COLUMNS = ("cause", "action", "category", "version", "source")


def _detect_delimiter(sample: str) -> str:
    semicolons = sample.count(";")
    commas = sample.count(",")
    return ";" if semicolons > commas else ","


def _build_rag_text(row: dict) -> str:
    parts = [
        f"Oracle error code: {row['error_code']}",
        f"Description: {row['description']}",
    ]
    for col in ("cause", "action"):
        if row.get(col):
            parts.append(f"{col.capitalize()}: {row[col]}")
    return "\n".join(parts)


async def import_csv(
    content: bytes,
    filename: str,
    session: AsyncSession,
) -> ImportResponse:
    if len(content) > settings.max_csv_size_mb * 1024 * 1024:
        raise ValueError(f"Datei zu groß (max. {settings.max_csv_size_mb} MB).")

    sha256 = hashlib.sha256(content).hexdigest()

    # Check for duplicate import
    existing = await session.execute(
        text("SELECT id FROM rag.document WHERE source_name = :n AND source_sha256 = :h"),
        {"n": filename, "h": sha256},
    )
    if existing.fetchone():
        raise ValueError("Diese Datei wurde bereits importiert (gleicher Inhalt).")

    text_content = content.decode("utf-8")
    sample = text_content[:2048]
    delimiter = _detect_delimiter(sample)

    reader = csv.DictReader(io.StringIO(text_content), delimiter=delimiter)

    if not reader.fieldnames:
        raise ValueError("CSV-Datei ist leer oder hat keine Kopfzeile.")
    fieldnames_lower = [f.strip().lower() for f in reader.fieldnames]
    for required in ("error_code", "description"):
        if required not in fieldnames_lower:
            raise ValueError(f"Pflichtspalt '{required}' fehlt in der CSV.")

    # Normalise fieldnames
    reader.fieldnames = fieldnames_lower

    rows = []
    warnings: list[str] = []
    seen_codes: set[str] = set()

    for lineno, row in enumerate(reader, start=2):
        # Skip empty rows
        if not any(row.values()):
            continue

        # Strip whitespace from all values
        row = {k: (v.strip() if v else "") for k, v in row.items()}

        # Strip control characters
        row = {k: re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", v) for k, v in row.items()}

        code = row.get("error_code", "").upper()
        row["error_code"] = code

        if not _ORA_PATTERN.match(code):
            raise ValueError(
                f"Zeile {lineno}: Ungültiger ORA-Code '{row.get('error_code')}'. "
                "Erwartet: ORA-NNNNN"
            )
        if not row.get("description"):
            raise ValueError(f"Zeile {lineno}: Pflichtfeld 'description' ist leer.")

        if code in seen_codes:
            warnings.append(f"Doppelter Fehlercode {code} in Zeile {lineno} – übersprungen.")
            continue
        seen_codes.add(code)
        rows.append(row)

    if not rows:
        raise ValueError("Keine gültigen Datensätze in der CSV-Datei gefunden.")

    # Build RAG texts and embeddings
    rag_texts = [_build_rag_text(r) for r in rows]
    embeddings = embed_passages(rag_texts)

    # Transactional insert
    doc_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    await session.execute(
        text(
            "INSERT INTO rag.document (id, source_name, source_sha256, imported_at, record_count, status) "
            "VALUES (:id, :sn, :sh, :ia, :rc, 'ready')"
        ),
        {"id": str(doc_id), "sn": filename, "sh": sha256, "ia": now, "rc": len(rows)},
    )

    for idx, (row, rag_text, emb) in enumerate(zip(rows, rag_texts, embeddings)):
        vec_str = "[" + ",".join(f"{x:.8f}" for x in emb) + "]"
        meta = {col: row[col] for col in OPTIONAL_COLUMNS if row.get(col)}
        meta["source_name"] = filename

        await session.execute(
            text(
                "INSERT INTO rag.chunk "
                "(id, document_id, chunk_index, record_key, content, metadata, embedding) "
                "VALUES (:id, :did, :ci, :rk, :ct, CAST(:md AS jsonb), CAST(:emb AS vector))"
            ),
            {
                "id": str(uuid.uuid4()),
                "did": str(doc_id),
                "ci": idx,
                "rk": row["error_code"],
                "ct": rag_text,
                "md": __import__("json").dumps(meta),
                "emb": vec_str,
            },
        )

    await session.commit()

    logger.info(
        "import source_name=%s document_id=%s records=%d warnings=%d",
        filename, doc_id, len(rows), len(warnings),
    )

    return ImportResponse(
        document_id=str(doc_id),
        source_name=filename,
        imported_records=len(rows),
        warnings=warnings,
        status="ready",
    )
