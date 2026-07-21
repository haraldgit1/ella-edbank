"""
CSV parser — generisch, mit optionalem ORA-Modus.

ORA-Modus wird automatisch aktiviert wenn:
- Spalten 'error_code' und 'description' vorhanden sind
- error_code dem Pattern ORA-NNNNN entspricht

Im generischen Modus: jede Zeile = ein Chunk, alle nicht-leeren Spalten
werden als "Spaltenname: Wert" ausgegeben.

Rückgabe: (list[ParsedChunk], list[str])  — Chunks und Warnungen.
"""
import csv
import io
import re

from edbank.rag.parsers.base import ParsedChunk

_ORA_PATTERN = re.compile(r"^ORA-\d{5}$")
_ORA_OPTIONAL_COLUMNS = ("cause", "action", "category", "version", "source")


def _detect_delimiter(sample: str) -> str:
    return ";" if sample.count(";") > sample.count(",") else ","


def _is_ora_mode(fieldnames: list[str]) -> bool:
    return "error_code" in fieldnames and "description" in fieldnames


def _build_ora_text(row: dict) -> str:
    parts = [
        f"Oracle error code: {row['error_code']}",
        f"Description: {row['description']}",
    ]
    for col in ("cause", "action"):
        if row.get(col):
            parts.append(f"{col.capitalize()}: {row[col]}")
    return "\n".join(parts)


def _build_generic_text(row: dict) -> str:
    return "\n".join(f"{k}: {v}" for k, v in row.items() if v)


def parse(content: bytes, filename: str) -> tuple[list[ParsedChunk], list[str]]:
    text = content.decode("utf-8")
    delimiter = _detect_delimiter(text[:2048])
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    if not reader.fieldnames:
        raise ValueError("CSV-Datei ist leer oder hat keine Kopfzeile.")

    fieldnames = [f.strip().lower() for f in reader.fieldnames]
    reader.fieldnames = fieldnames
    ora_mode = _is_ora_mode(fieldnames)

    if ora_mode:
        for required in ("error_code", "description"):
            if required not in fieldnames:
                raise ValueError(f"Pflichtspalt '{required}' fehlt in der CSV.")

    chunks: list[ParsedChunk] = []
    warnings: list[str] = []
    seen_keys: set[str] = set()

    for lineno, row in enumerate(reader, start=2):
        if not any(row.values()):
            continue

        row = {k: (v.strip() if v else "") for k, v in row.items()}
        row = {k: re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", v) for k, v in row.items()}

        if ora_mode:
            code = row.get("error_code", "").upper()
            row["error_code"] = code
            if not _ORA_PATTERN.match(code):
                raise ValueError(
                    f"Zeile {lineno}: Ungültiger ORA-Code '{code}'. Erwartet: ORA-NNNNN"
                )
            if not row.get("description"):
                raise ValueError(f"Zeile {lineno}: Pflichtfeld 'description' ist leer.")
            record_key = code
            text_content = _build_ora_text(row)
            meta = {col: row[col] for col in _ORA_OPTIONAL_COLUMNS if row.get(col)}
        else:
            first_col = fieldnames[0]
            key_value = row.get(first_col, "").strip()
            record_key = key_value if key_value else f"{filename}#{lineno:04d}"
            text_content = _build_generic_text(row)
            meta = {}

        if not text_content.strip():
            continue

        if record_key in seen_keys:
            warnings.append(f"Doppelter Schlüssel '{record_key}' in Zeile {lineno} – übersprungen.")
            continue
        seen_keys.add(record_key)

        chunks.append(ParsedChunk(record_key=record_key, content=text_content, metadata=meta))

    if not chunks:
        raise ValueError("Keine gültigen Datensätze in der CSV-Datei gefunden.")

    return chunks, warnings
