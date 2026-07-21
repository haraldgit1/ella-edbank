"""
RAG document parsers.

Each parser converts raw file bytes into a list of ParsedChunk objects.
The dispatcher `get_parser` selects the correct parser by file extension.
"""
from edbank.rag.parsers.base import ParsedChunk
from edbank.rag.parsers.csv_parser import parse as parse_csv
from edbank.rag.parsers.plaintext_parser import parse as parse_plaintext
from edbank.rag.parsers.rtf_parser import parse as parse_rtf
from edbank.rag.parsers.html_parser import parse as parse_html

_PARSERS = {
    ".csv":  parse_csv,
    ".txt":  parse_plaintext,
    ".md":   parse_plaintext,
    ".rtf":  parse_rtf,
    ".html": parse_html,
    ".htm":  parse_html,
}

SUPPORTED_EXTENSIONS = set(_PARSERS.keys())


def get_parser(filename: str):
    """Return the parser function for the given filename, or None if unsupported."""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    return _PARSERS.get(ext)
