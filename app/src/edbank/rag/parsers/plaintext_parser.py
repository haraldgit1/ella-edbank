"""
Plain-text and Markdown parser.

Splits text into chunks at blank lines (paragraphs).
Short paragraphs (<50 chars) are merged with the next one.
Long paragraphs (>1000 chars) are split at sentence boundaries.

record_key: {filename}#{index:04d}
"""
import re

from edbank.rag.parsers.base import ParsedChunk

_MIN_CHUNK_LEN = 50
_MAX_CHUNK_LEN = 1000

# Matches end of a sentence (. ! ?) followed by whitespace or end of string
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

# Strip Markdown heading markers for cleaner text
_MD_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)


def _split_long(text: str) -> list[str]:
    """Split text that exceeds MAX_CHUNK_LEN at sentence boundaries."""
    parts = _SENTENCE_END.split(text)
    chunks: list[str] = []
    current = ""
    for part in parts:
        if len(current) + len(part) > _MAX_CHUNK_LEN and current:
            chunks.append(current.strip())
            current = part
        else:
            current = (current + " " + part).strip() if current else part
    if current:
        chunks.append(current.strip())
    return chunks or [text]


def parse(content: bytes, filename: str) -> tuple[list[ParsedChunk], list[str]]:
    text = content.decode("utf-8")

    # Strip Markdown heading markers (keep the heading text itself)
    text = _MD_HEADING.sub("", text)

    # Split into paragraphs at blank lines
    raw_paragraphs = re.split(r"\n{2,}", text)

    # Normalise whitespace within each paragraph
    paragraphs: list[str] = []
    pending = ""
    for para in raw_paragraphs:
        para = " ".join(para.split())
        if not para:
            continue
        if len(para) < _MIN_CHUNK_LEN:
            pending = (pending + " " + para).strip() if pending else para
        else:
            if pending:
                para = (pending + " " + para).strip()
                pending = ""
            paragraphs.append(para)
    if pending:
        paragraphs.append(pending)

    # Split oversized paragraphs
    final: list[str] = []
    for para in paragraphs:
        if len(para) > _MAX_CHUNK_LEN:
            final.extend(_split_long(para))
        else:
            final.append(para)

    if not final:
        raise ValueError("Keine verwertbaren Textabsätze in der Datei gefunden.")

    chunks = [
        ParsedChunk(
            record_key=f"{filename}#{i:04d}",
            content=text_block,
            metadata={"chunk_index": i},
        )
        for i, text_block in enumerate(final)
    ]
    return chunks, []
