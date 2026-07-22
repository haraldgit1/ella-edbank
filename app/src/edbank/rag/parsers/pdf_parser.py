"""
PDF parser — extrahiert Text aus Text-PDFs (selektierbarer Text).
Requires: pypdf>=4.0

Jede Seite wird als eigener Chunk behandelt, mit Seitennummer im record_key.
Seiten ohne extrahierbaren Text werden übersprungen (z.B. reine Bild-Seiten).

Hinweis: Gescannte PDFs (Bild-PDFs ohne Textebene) liefern keinen Text —
dafür ist OCR nötig (nicht in Phase 1 enthalten).
"""
import io

from edbank.rag.parsers.base import ParsedChunk
from edbank.rag.parsers.plaintext_parser import parse as parse_plaintext

_MIN_PAGE_CHARS = 30  # Seiten mit weniger Zeichen werden übersprungen


def parse(content: bytes, filename: str) -> tuple[list[ParsedChunk], list[str]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "PDF-Unterstützung nicht verfügbar. Bitte 'pypdf>=4.0' installieren."
        ) from exc

    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as exc:
        raise ValueError(f"PDF konnte nicht gelesen werden: {exc}") from exc

    if len(reader.pages) == 0:
        raise ValueError("Das PDF enthält keine Seiten.")

    chunks: list[ParsedChunk] = []
    warnings: list[str] = []
    skipped = 0

    for page_num, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        text = text.strip()
        if len(text) < _MIN_PAGE_CHARS:
            skipped += 1
            continue

        # Jede Seite durch den Plaintext-Parser chunken
        # (lange Seiten werden an Absatzgrenzen geteilt)
        try:
            page_chunks, _ = parse_plaintext(text.encode("utf-8"), filename)
        except ValueError:
            skipped += 1
            continue

        # record_key: dateiname#seite_NNN#chunk_MM
        for i, chunk in enumerate(page_chunks):
            chunks.append(ParsedChunk(
                record_key=f"{filename}#s{page_num:03d}#{i:02d}",
                content=chunk.content,
                metadata={"page": page_num, "chunk_on_page": i},
            ))

    if not chunks:
        if skipped == len(reader.pages):
            raise ValueError(
                f"Kein extrahierbarer Text gefunden ({len(reader.pages)} Seiten überprüft). "
                "Dieses PDF enthält möglicherweise nur Bilder und benötigt OCR."
            )
        raise ValueError("Keine verwertbaren Textabschnitte im PDF gefunden.")

    if skipped > 0:
        warnings.append(
            f"{skipped} Seite(n) ohne extrahierbaren Text übersprungen "
            "(Bild-Seiten oder leere Seiten)."
        )

    return chunks, warnings
