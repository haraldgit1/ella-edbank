"""
Unit tests for the manual tool-use orchestration loop (Spec §28.1 – Orchestrierung).
LLM client and MCP client are fully mocked.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_llm_response(content: str):
    choice = MagicMock()
    choice.message.content = content
    choice.finish_reason = "stop"
    completion = MagicMock()
    completion.choices = [choice]
    return completion


def _tool_call_text(name: str, person_name: str) -> str:
    return (
        f'<tool_call>\n'
        f'{{"name": "{name}", "arguments": {{"person_name": "{person_name}"}}}}\n'
        f'</tool_call>'
    )


HANNES_RESULT = {
    "person_name": "Hannes Meier",
    "match_count": 2,
    "accounts": [
        {"iban": "AT611904300234573201", "bank_name": "Musterbank Wien", "bic": "BAWAATWW"},
        {"iban": "AT483200000012345864", "bank_name": "Regionalbank Süd", "bic": "RLNWATWW"},
    ],
}


# ── parse helper ─────────────────────────────────────────────────────────────

def test_parse_tool_call_valid():
    from edbank.llm.tool_loop import _parse_tool_call
    text = _tool_call_text("get_bank_accounts_by_person_name", "Hannes Meier")
    result = _parse_tool_call(text)
    assert result is not None
    assert result["name"] == "get_bank_accounts_by_person_name"
    assert result["arguments"]["person_name"] == "Hannes Meier"


def test_parse_tool_call_none_when_absent():
    from edbank.llm.tool_loop import _parse_tool_call
    assert _parse_tool_call("Eine normale Antwort ohne Tool-Tag.") is None


def test_parse_tool_call_none_on_invalid_json():
    from edbank.llm.tool_loop import _parse_tool_call
    assert _parse_tool_call("<tool_call>{invalid json}</tool_call>") is None


# ── orchestration: ORA question uses RAG, no tool ────────────────────────────

@pytest.mark.asyncio
async def test_ora_question_no_tool_call():
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=_make_llm_response("ORA-01555 bedeutet Snapshot too old.")
    )

    from edbank.llm.tool_loop import run_full_loop
    messages = [{"role": "user", "content": "Was bedeutet ORA-01555?"}]
    result = await run_full_loop(messages, client)

    assert "ORA-01555" in result.answer
    assert result.traces == []
    assert client.chat.completions.create.call_count == 1


# ── orchestration: IBAN question triggers MCP tool ───────────────────────────

@pytest.mark.asyncio
async def test_iban_question_triggers_mcp_tool():
    tool_text = _tool_call_text("get_bank_accounts_by_person_name", "Hannes Meier")
    final_answer = "Hannes Meier hat zwei Konten: AT611... und AT483..."

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        side_effect=[
            _make_llm_response(tool_text),   # round 0: tool call
            _make_llm_response(final_answer), # final answer
        ]
    )

    with patch("edbank.llm.tool_loop.mcp_client.call_tool", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = HANNES_RESULT
        from edbank.llm.tool_loop import run_full_loop
        result = await run_full_loop(
            [{"role": "user", "content": "Welchen IBAN hat Herr Hannes Meier?"}],
            client,
        )

    assert result.answer == final_answer
    assert len(result.traces) == 1
    assert result.traces[0].name == "get_bank_accounts_by_person_name"
    assert result.traces[0].status == "success"
    mock_call.assert_called_once_with(
        "get_bank_accounts_by_person_name", {"person_name": "Hannes Meier"}
    )


# ── orchestration: tool result is preserved unchanged ────────────────────────

@pytest.mark.asyncio
async def test_tool_result_fully_passed_to_model():
    tool_text = _tool_call_text("get_bank_accounts_by_person_name", "Hannes Meier")

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        side_effect=[
            _make_llm_response(tool_text),
            _make_llm_response("Fertige Antwort"),
        ]
    )

    with patch("edbank.llm.tool_loop.mcp_client.call_tool", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = HANNES_RESULT
        from edbank.llm.tool_loop import run_full_loop
        result = await run_full_loop(
            [{"role": "user", "content": "IBAN von Hannes Meier?"}],
            client,
        )

    # The second LLM call must include both IBANs in its messages
    second_call_messages = client.chat.completions.create.call_args_list[1][1]["messages"]
    combined = " ".join(m["content"] for m in second_call_messages)
    assert "AT611904300234573201" in combined
    assert "AT483200000012345864" in combined


# ── orchestration: invalid tool name rejected ─────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_tool_name_rejected():
    bad_tool = '<tool_call>\n{"name": "execute_sql", "arguments": {"query": "SELECT *"}}\n</tool_call>'
    final_answer = "Ich kann das Tool nicht aufrufen."

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        side_effect=[
            _make_llm_response(bad_tool),
            _make_llm_response(final_answer),
        ]
    )

    with patch("edbank.llm.tool_loop.mcp_client.call_tool", new_callable=AsyncMock) as mock_call:
        from edbank.llm.tool_loop import run_full_loop
        result = await run_full_loop(
            [{"role": "user", "content": "Führe SQL aus"}],
            client,
        )

    mock_call.assert_not_called()
    assert result.traces[0].status == "validation_error"


# ── orchestration: max rounds abort ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_max_rounds_abort():
    tool_text = _tool_call_text("get_bank_accounts_by_person_name", "Hannes Meier")

    client = AsyncMock()
    # Always return a tool call → loop runs to max
    client.chat.completions.create = AsyncMock(return_value=_make_llm_response(tool_text))

    with patch("edbank.llm.tool_loop.mcp_client.call_tool", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = HANNES_RESULT
        from edbank.llm.tool_loop import run_tool_rounds, ABORT_MSG
        from edbank.config import settings
        msgs, traces, direct = await run_tool_rounds(
            [{"role": "user", "content": "IBAN?"}],
            client,
        )

    assert direct == ABORT_MSG
    assert len(traces) == settings.mcp_max_tool_rounds
