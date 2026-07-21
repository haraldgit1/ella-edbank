"""
Unit tests for the CSV importer (Spec §28.1 – CSV).
No database or embedding model required: the importer is tested
up to the point where it would call embed_passages / session.execute.
"""
import io
import re
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── helpers ──────────────────────────────────────────────────────────────────

def _csv(rows: list[dict], sep: str = ",") -> bytes:
    if not rows:
        return b""
    headers = sep.join(rows[0].keys())
    lines = [headers] + [sep.join(str(v) for v in r.values()) for r in rows]
    return "\n".join(lines).encode("utf-8")


def _make_session():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(fetchone=MagicMock(return_value=None)))
    session.commit = AsyncMock()
    return session


VALID_ROW = {
    "error_code": "ORA-01555",
    "description": "Snapshot too old",
    "cause": "Required undo information was overwritten",
    "action": "Increase undo retention",
}


# ── tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_valid_csv_comma():
    content = _csv([VALID_ROW], sep=",")
    session = _make_session()
    with patch("edbank.rag.importer.embed_passages", return_value=[[0.0] * 384]):
        from edbank.rag.importer import import_csv
        result = await import_csv(content, "ora.csv", session)
    assert result.imported_records == 1
    assert result.status == "ready"
    assert result.warnings == []


@pytest.mark.asyncio
async def test_valid_csv_semicolon():
    content = _csv([VALID_ROW], sep=";")
    session = _make_session()
    with patch("edbank.rag.importer.embed_passages", return_value=[[0.0] * 384]):
        from edbank.rag.importer import import_csv
        result = await import_csv(content, "ora.csv", session)
    assert result.imported_records == 1


@pytest.mark.asyncio
async def test_utf8_umlauts():
    row = {
        "error_code": "ORA-00001",
        "description": "Eindeutigkeitsverletzung: Schlüssel bereits vorhanden",
        "cause": "Ursächlich: Doppelter Eintrag",
        "action": "Anderen Schlüssel verwenden",
    }
    content = _csv([row])
    session = _make_session()
    with patch("edbank.rag.importer.embed_passages", return_value=[[0.0] * 384]):
        from edbank.rag.importer import import_csv
        result = await import_csv(content, "ora.csv", session)
    assert result.imported_records == 1


@pytest.mark.asyncio
async def test_missing_required_column():
    # A CSV with only 'error_code' but no 'description' column is now handled
    # in generic mode (no ORA validation). A CSV with both columns but an invalid
    # ORA code triggers the ORA-specific error.
    content = b"error_code,description\nERR-001,bad code\n"
    session = _make_session()
    from edbank.rag.importer import import_csv
    with pytest.raises(ValueError, match="ORA-Code"):
        await import_csv(content, "ora.csv", session)


@pytest.mark.asyncio
async def test_invalid_ora_code():
    row = {"error_code": "ERR-001", "description": "bad"}
    content = _csv([row])
    session = _make_session()
    from edbank.rag.importer import import_csv
    with pytest.raises(ValueError, match="ORA-Code"):
        await import_csv(content, "ora.csv", session)


@pytest.mark.asyncio
async def test_duplicate_ora_code_warns():
    rows = [
        {"error_code": "ORA-00001", "description": "First"},
        {"error_code": "ORA-00001", "description": "Duplicate"},
    ]
    content = _csv(rows)
    session = _make_session()
    with patch("edbank.rag.importer.embed_passages", return_value=[[0.0] * 384]):
        from edbank.rag.importer import import_csv
        result = await import_csv(content, "ora.csv", session)
    assert result.imported_records == 1
    assert len(result.warnings) == 1
    assert "ORA-00001" in result.warnings[0]


@pytest.mark.asyncio
async def test_empty_file():
    session = _make_session()
    from edbank.rag.importer import import_csv
    with pytest.raises(ValueError):
        await import_csv(b"", "ora.csv", session)


@pytest.mark.asyncio
async def test_file_too_large():
    from edbank.config import settings
    big = b"error_code,description\n" + b"ORA-00001,x\n" * 10
    session = _make_session()
    from edbank.rag.importer import import_csv
    with patch.object(settings, "max_csv_size_mb", 0):
        with pytest.raises(ValueError, match="groß"):
            await import_csv(big, "ora.csv", session)
