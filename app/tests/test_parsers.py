"""
Unit tests for the RAG document parsers (Phase 1 DocType Enhancement).
No database or embedding model required.
"""
import pytest


# ── CSV parser ────────────────────────────────────────────────────────────────

class TestCsvParser:

    def test_ora_mode_valid(self):
        from edbank.rag.parsers.csv_parser import parse
        content = b"error_code,description,cause\nORA-01555,Snapshot too old,Undo overwritten\n"
        chunks, warnings = parse(content, "ora.csv")
        assert len(chunks) == 1
        assert chunks[0].record_key == "ORA-01555"
        assert "Oracle error code: ORA-01555" in chunks[0].content
        assert warnings == []

    def test_ora_mode_semicolon_delimiter(self):
        from edbank.rag.parsers.csv_parser import parse
        content = b"error_code;description\nORA-00001;Unique constraint\n"
        chunks, warnings = parse(content, "ora.csv")
        assert len(chunks) == 1
        assert chunks[0].record_key == "ORA-00001"

    def test_ora_mode_invalid_code_raises(self):
        from edbank.rag.parsers.csv_parser import parse
        content = b"error_code,description\nERR-001,bad\n"
        with pytest.raises(ValueError, match="ORA-Code"):
            parse(content, "ora.csv")

    def test_ora_mode_duplicate_warns(self):
        from edbank.rag.parsers.csv_parser import parse
        content = b"error_code,description\nORA-00001,First\nORA-00001,Second\n"
        chunks, warnings = parse(content, "ora.csv")
        assert len(chunks) == 1
        assert len(warnings) == 1
        assert "ORA-00001" in warnings[0]

    def test_generic_mode(self):
        from edbank.rag.parsers.csv_parser import parse
        content = b"name,city,role\nAlice,Vienna,Engineer\nBob,Berlin,Manager\n"
        chunks, warnings = parse(content, "staff.csv")
        assert len(chunks) == 2
        assert "Alice" in chunks[0].record_key or "Alice" in chunks[0].content
        assert warnings == []

    def test_empty_raises(self):
        from edbank.rag.parsers.csv_parser import parse
        with pytest.raises(ValueError):
            parse(b"", "empty.csv")

    def test_no_rows_raises(self):
        from edbank.rag.parsers.csv_parser import parse
        with pytest.raises(ValueError):
            parse(b"error_code,description\n", "ora.csv")


# ── Plain-text parser ─────────────────────────────────────────────────────────

class TestPlaintextParser:

    def test_basic_paragraphs(self):
        from edbank.rag.parsers.plaintext_parser import parse
        content = b"First paragraph with enough text to pass the minimum length check.\n\nSecond paragraph also long enough to be kept as its own chunk here.\n"
        chunks, warnings = parse(content, "notes.txt")
        assert len(chunks) == 2
        assert warnings == []

    def test_short_paragraphs_merged(self):
        from edbank.rag.parsers.plaintext_parser import parse
        content = b"Too short.\n\nAlso short.\n\nThis paragraph is long enough to anchor the merged content above it properly.\n"
        chunks, warnings = parse(content, "notes.txt")
        # Short paragraphs get merged — result should be fewer than 3 chunks
        assert len(chunks) < 3

    def test_markdown_heading_stripped(self):
        from edbank.rag.parsers.plaintext_parser import parse
        content = b"## My Heading\n\nSome content that is long enough to form a valid chunk in the result output.\n"
        chunks, warnings = parse(content, "doc.md")
        assert all("##" not in c.content for c in chunks)

    def test_record_key_format(self):
        from edbank.rag.parsers.plaintext_parser import parse
        content = b"A sufficiently long paragraph to pass the minimum length requirement set.\n\nAnother sufficiently long paragraph to pass the minimum length requirement here.\n"
        chunks, _ = parse(content, "doc.txt")
        assert chunks[0].record_key == "doc.txt#0000"
        assert chunks[1].record_key == "doc.txt#0001"

    def test_empty_raises(self):
        from edbank.rag.parsers.plaintext_parser import parse
        with pytest.raises(ValueError):
            parse(b"   \n\n   \n", "empty.txt")


# ── HTML parser ───────────────────────────────────────────────────────────────

class TestHtmlParser:

    def test_basic_html(self):
        from edbank.rag.parsers.html_parser import parse
        content = b"""<html><body>
        <h1>Title</h1>
        <p>This is a sufficiently long paragraph that should survive the minimum length filter.</p>
        </body></html>"""
        chunks, warnings = parse(content, "page.html")
        assert len(chunks) >= 1
        assert all("<" not in c.content for c in chunks)

    def test_script_and_style_removed(self):
        from edbank.rag.parsers.html_parser import parse
        content = b"""<html><head><style>body{color:red}</style></head>
        <body><script>alert(1)</script>
        <p>Visible content that is long enough to be included in the output chunks.</p>
        </body></html>"""
        chunks, _ = parse(content, "page.html")
        combined = " ".join(c.content for c in chunks)
        assert "alert" not in combined
        assert "color:red" not in combined
        assert "Visible content" in combined


# ── Dispatcher ────────────────────────────────────────────────────────────────

class TestDispatcher:

    def test_known_extensions(self):
        from edbank.rag.parsers import get_parser
        for ext in (".csv", ".txt", ".md", ".html", ".htm", ".rtf"):
            assert get_parser(f"file{ext}") is not None

    def test_unknown_extension_returns_none(self):
        from edbank.rag.parsers import get_parser
        assert get_parser("file.pdf") is None
        assert get_parser("file.docx") is None

    def test_case_insensitive(self):
        from edbank.rag.parsers import get_parser
        assert get_parser("FILE.CSV") is not None
        assert get_parser("DOC.HTML") is not None
