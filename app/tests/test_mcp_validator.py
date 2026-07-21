"""
Unit tests for MCP tool-call validator (Spec §28.1 – MCP).
No network or database required.
"""
import pytest
from edbank.mcp.validator import validate_tool_call


TOOL = "get_bank_accounts_by_person_name"


# ── valid calls ───────────────────────────────────────────────────────────────

def test_valid_call_returns_none():
    assert validate_tool_call(TOOL, {"person_name": "Hannes Meier"}) is None


def test_valid_call_short_name():
    assert validate_tool_call(TOOL, {"person_name": "Li"}) is None


def test_valid_call_long_name():
    assert validate_tool_call(TOOL, {"person_name": "A" * 200}) is None


# ── unknown tool ──────────────────────────────────────────────────────────────

def test_unknown_tool_rejected():
    error = validate_tool_call("execute_sql", {"query": "SELECT 1"})
    assert error is not None
    assert "execute_sql" in error


def test_unknown_tool_not_in_allowed_set():
    error = validate_tool_call("drop_table", {}, allowed_tools={"get_bank_accounts_by_person_name"})
    assert error is not None


# ── person_name validation ────────────────────────────────────────────────────

def test_missing_person_name():
    error = validate_tool_call(TOOL, {})
    assert error is not None


def test_non_string_person_name():
    error = validate_tool_call(TOOL, {"person_name": 123})
    assert error is not None


def test_too_short_person_name():
    error = validate_tool_call(TOOL, {"person_name": "X"})
    assert error is not None


def test_too_long_person_name():
    error = validate_tool_call(TOOL, {"person_name": "A" * 201})
    assert error is not None


# ── SQL-injection / suspicious input ─────────────────────────────────────────

def test_sql_injection_single_quote():
    error = validate_tool_call(TOOL, {"person_name": "' OR 1=1 --"})
    assert error is not None


def test_sql_injection_or_keyword():
    error = validate_tool_call(TOOL, {"person_name": "x OR y"})
    assert error is not None


def test_sql_injection_semicolon():
    error = validate_tool_call(TOOL, {"person_name": "name; DROP TABLE"})
    assert error is not None


def test_sql_injection_select():
    error = validate_tool_call(TOOL, {"person_name": "SELECT * FROM person"})
    assert error is not None


def test_normal_name_with_hyphen_allowed():
    """Names like 'Müller-Huber' must not be blocked."""
    assert validate_tool_call(TOOL, {"person_name": "Müller-Huber"}) is None


def test_normal_name_with_space_allowed():
    assert validate_tool_call(TOOL, {"person_name": "Maria Anna Unbekannt"}) is None
