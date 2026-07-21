"""
Generic RAG importer.

Selects the correct parser by file extension and stores the resulting
chunks (with embeddings) in rag.document + rag.chunk.

ORA-CSV specific logic lives entirely in parsers/csv_parser.py.
"""
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from edbank.config import settings
from edbank.rag.embeddings import embed_passages
from edbank.rag.parsers import get_parser, SUPPORTED_EXTENSIONS
from edbank.rag.schemas import ImportResponse

logger = logging.getLogger(__name__)


async def import_document(
    content: bytes,
    filename: str,
    session: AsyncSession,
) -> ImportResponse:
    """Parse, embed and persist a document of any supported type."""
    if not content:
        raise ValueError("Datei ist leer.")

    if len(content) > settings.max_csv_size_mb * 1024 * 1024:
        raise ValueError(f"Datei zu groß (max. {settings.max_csv_size_mb} MB).")

    parser = get_parser(filename)
    if parser is None:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(
            f"Nicht unterstützter Dateityp. Unterstützt: {supported}"
        )

    sha256 = hashlib.sha256(content).hexdigest()
    existing = await session.execute(
        text("SELECT id FROM rag.document WHERE source_name = :n AND source_sha256 = :h"),
        {"n": filename, "h": sha256},
    )
    if existing.fetchone():
        raise ValueError("Diese Datei wurde bereits importiert (gleicher Inhalt).")

    chunks, warnings = parser(content, filename)

    rag_texts = [c.content for c in chunks]
    embeddings = embed_passages(rag_texts)

    doc_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    await session.execute(
        text(
            "INSERT INTO rag.document (id, source_name, source_sha256, imported_at, record_count, status) "
            "VALUES (:id, :sn, :sh, :ia, :rc, 'ready')"
        ),
        {"id": str(doc_id), "sn": filename, "sh": sha256, "ia": now, "rc": len(chunks)},
    )

    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        vec_str = "[" + ",".join(f"{x:.8f}" for x in emb) + "]"
        meta = {**chunk.metadata, "source_name": filename}

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
                "rk": chunk.record_key,
                "ct": chunk.content,
                "md": json.dumps(meta),
                "emb": vec_str,
            },
        )

    await session.commit()

    logger.info(
        "import source_name=%s document_id=%s records=%d warnings=%d",
        filename, doc_id, len(chunks), len(warnings),
    )

    return ImportResponse(
        document_id=str(doc_id),
        source_name=filename,
        imported_records=len(chunks),
        warnings=warnings,
        status="ready",
    )


# Backwards-compatible alias used in tests and older call sites
async def import_csv(
    content: bytes,
    filename: str,
    session: AsyncSession,
) -> ImportResponse:
    return await import_document(content, filename, session)
