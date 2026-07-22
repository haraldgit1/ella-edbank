"""
HTML parser — removes tags/scripts/styles and delegates to the plain-text parser.
Requires: beautifulsoup4>=4.12

Handles:
- Static HTML pages (full text extraction)
- Minimal pages: falls back to title + meta description
- JS-rendered pages: best-effort with a clear warning
"""
from edbank.rag.parsers.base import ParsedChunk
from edbank.rag.parsers.plaintext_parser import parse as parse_plaintext

_REMOVE_TAGS = {"script", "style", "nav", "footer", "head"}
_MIN_USEFUL_CHARS = 100


def _extract_text(soup) -> str:
    """Extract visible text with double-newline paragraph separation."""
    # Use separator="\n\n" so the plaintext parser can split into paragraphs
    text = soup.get_text(separator="\n\n", strip=True)
    return text


def _extract_meta_fallback(soup) -> str:
    """Extract title and meta description as minimal fallback content."""
    parts = []

    title = soup.find("title")
    if title and title.get_text(strip=True):
        parts.append(title.get_text(strip=True))

    for meta in soup.find_all("meta"):
        name = (meta.get("name") or meta.get("property") or "").lower()
        content = meta.get("content", "").strip()
        if name in ("description", "og:description", "og:title") and content:
            parts.append(content)

    return "\n\n".join(parts)


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

    plain = _extract_text(soup)
    warnings: list[str] = []

    if len(plain.strip()) < _MIN_USEFUL_CHARS:
        # Try meta fallback (JS-rendered pages have almost no server-side text)
        fallback = _extract_meta_fallback(BeautifulSoup(content, "html.parser"))
        if len(fallback.strip()) >= 20:
            plain = fallback
            warnings.append(
                "Seite enthält wenig server-seitig gerenderten Text (vermutlich JavaScript-Anwendung). "
                "Nur Titel und Meta-Beschreibung wurden importiert."
            )
        else:
            raise ValueError(
                "Keine verwertbaren Textinhalte auf dieser Seite gefunden. "
                "Die Seite wird möglicherweise vollständig per JavaScript gerendert "
                "und enthält im Quelltext keinen lesbaren Text."
            )

    chunks, parse_warnings = parse_plaintext(plain.encode("utf-8"), filename)
    return chunks, warnings + parse_warnings
