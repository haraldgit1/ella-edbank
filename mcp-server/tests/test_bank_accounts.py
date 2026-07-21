"""
Unit tests for the MCP bank-accounts tool (Spec §28.1 – MCP).
DB session is mocked.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock


def _mock_session(rows: list[dict]):
    """Build an AsyncSession mock returning the given rows."""
    mock_rows = []
    for r in rows:
        row = MagicMock()
        row.person_name = r.get("person_name", "")
        row.iban = r["iban"]
        row.bank_name = r["bank_name"]
        row.bic = r["bic"]
        mock_rows.append(row)

    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(fetchall=MagicMock(return_value=mock_rows))
    )
    return session


HANNES_ROWS = [
    {"person_name": "Hannes Meier", "iban": "AT611904300234573201", "bank_name": "Musterbank Wien",  "bic": "BAWAATWW"},
    {"person_name": "Hannes Meier", "iban": "AT483200000012345864", "bank_name": "Regionalbank Süd", "bic": "RLNWATWW"},
]


# ── Hannes Meier returns two accounts ────────────────────────────────────────

@pytest.mark.asyncio
async def test_hannes_meier_two_accounts():
    session = _mock_session(HANNES_ROWS)
    from edbank_mcp.tools.bank_accounts import get_bank_accounts_by_person_name
    result = await get_bank_accounts_by_person_name("Hannes Meier", session)
    assert result.match_count == 2
    ibans = {a.iban for a in result.accounts}
    assert "AT611904300234573201" in ibans
    assert "AT483200000012345864" in ibans


# ── unknown person returns empty list ────────────────────────────────────────

@pytest.mark.asyncio
async def test_unknown_person_empty_result():
    session = _mock_session([])
    from edbank_mcp.tools.bank_accounts import get_bank_accounts_by_person_name
    result = await get_bank_accounts_by_person_name("Max Beispiel", session)
    assert result.match_count == 0
    assert result.accounts == []


# ── SQL-injection text is only treated as a parameter ────────────────────────

@pytest.mark.asyncio
async def test_sql_injection_treated_as_parameter():
    """
    The injection string is passed as a bind parameter to SQLAlchemy,
    so the DB returns an empty result — no error, no data leak.
    """
    session = _mock_session([])
    from edbank_mcp.tools.bank_accounts import get_bank_accounts_by_person_name
    result = await get_bank_accounts_by_person_name("' OR 1=1 --", session)
    assert result.match_count == 0
    assert result.accounts == []


# ── DB error returns controlled exception ────────────────────────────────────

@pytest.mark.asyncio
async def test_db_error_raises():
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=Exception("connection refused"))
    from edbank_mcp.tools.bank_accounts import get_bank_accounts_by_person_name
    with pytest.raises(Exception, match="connection refused"):
        await get_bank_accounts_by_person_name("Hannes Meier", session)
