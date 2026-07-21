"""
RTF parser — strips RTF control words and delegates to the plain-text parser.
Requires: striprtf>=0.0.26
"""
from edbank.rag.parsers.base import ParsedChunk
from edbank.rag.parsers.plaintext_parser import parse as parse_plaintext


def parse(content: bytes, filename: str) -> tuple[list[ParsedChunk], list[str]]:
    try:
        from striprtf.striprtf import rtf_to_text
    except ImportError as exc:
        raise RuntimeError(
            "RTF-Unterstützung nicht verfügbar. Bitte 'striprtf>=0.0.26' installieren."
        ) from exc

    try:
        rtf_text = content.decode("utf-8", errors="replace")
        plain = rtf_to_text(rtf_text)
    except Exception as exc:
        raise ValueError(f"RTF-Datei konnte nicht gelesen werden: {exc}") from exc

    return parse_plaintext(plain.encode("utf-8"), filename)
