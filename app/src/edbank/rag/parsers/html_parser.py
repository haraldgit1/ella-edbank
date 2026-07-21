"""
HTML parser — removes tags/scripts/styles and delegates to the plain-text parser.
Requires: beautifulsoup4>=4.12
"""
from edbank.rag.parsers.base import ParsedChunk
from edbank.rag.parsers.plaintext_parser import parse as parse_plaintext

_REMOVE_TAGS = {"script", "style", "nav", "footer", "head"}


def parse(content: bytes, filename: str) -> tuple[list[ParsedChunk], list[str]]:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError(
            "HTML-Unterstützung nicht verfügbar. Bitte 'beautifulsoup4>=4.12' installieren."
        ) from exc

    soup = BeautifulSoup(content, "html.parser")
    for tag in soup.find_all(_REMOVE_TAGS):
        tag.decompose()

    plain = soup.get_text(separator="\n")
    return parse_plaintext(plain.encode("utf-8"), filename)
