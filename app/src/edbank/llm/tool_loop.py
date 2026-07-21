"""
Manual tool-use loop for Mistral 7B in LM Studio.

Mistral-Instruct-v0.3 in LM Studio supports only user/assistant roles
and rejects tool/system roles and the OpenAI `tools` parameter.

We instead inject tool descriptions into the system prompt and parse
the model's text output for <tool_call>…</tool_call> tags.
"""
import json
import logging
import re
import time
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from edbank.config import settings
from edbank.mcp import client as mcp_client
from edbank.mcp.validator import validate_tool_call
from edbank.llm.prompts import TOOL_RESULT_TEMPLATE, TOOL_ERROR_TEMPLATE

logger = logging.getLogger(__name__)

ABORT_MSG = (
    "Die Anfrage konnte nicht innerhalb der zulässigen "
    "Verarbeitungsschritte abgeschlossen werden."
)

_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL,
)


@dataclass
class ToolTrace:
    name: str
    status: str          # "success" | "validation_error" | "mcp_error"
    duration_ms: int | None = None
    result_rows: int | None = None


@dataclass
class LoopResult:
    answer: str
    traces: list[ToolTrace] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)


def _parse_tool_call(text: str) -> dict | None:
    """Extract and parse the first <tool_call>…</tool_call> block, or None."""
    match = _TOOL_CALL_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


async def _execute_tool(name: str, arguments: dict, traces: list[ToolTrace]) -> str:
    """
    Validate, call MCP tool, append trace.
    Returns the user-message content to inject back into the conversation.
    """
    validation_error = validate_tool_call(name, arguments)
    if validation_error:
        traces.append(ToolTrace(name=name, status="validation_error"))
        logger.warning("tool validation_error tool=%s msg=%s", name, validation_error)
        return TOOL_ERROR_TEMPLATE.format(error_message=validation_error)

    t0 = time.monotonic()
    try:
        result = await mcp_client.call_tool(name, arguments)
        duration_ms = int((time.monotonic() - t0) * 1000)
        row_count = result.get("match_count") if isinstance(result, dict) else None
        traces.append(ToolTrace(name=name, status="success", duration_ms=duration_ms, result_rows=row_count))
        logger.info("tool_call tool=%s status=success duration_ms=%d rows=%s", name, duration_ms, row_count)
        return TOOL_RESULT_TEMPLATE.format(result_json=json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        traces.append(ToolTrace(name=name, status="mcp_error", duration_ms=duration_ms))
        logger.error("tool_call tool=%s error=%s", name, exc)
        return TOOL_ERROR_TEMPLATE.format(error_message="Der Datenbankdienst ist nicht verfügbar.")


async def run_tool_rounds(
    messages: list[dict],
    client: AsyncOpenAI,
) -> tuple[list[dict], list[ToolTrace], str | None]:
    """
    Run up to MAX_TOOL_ROUNDS of manual tool-use.

    Returns (updated_messages, traces, direct_answer_or_None).
    If direct_answer is set, the caller can skip the final LLM call.
    """
    traces: list[ToolTrace] = []
    msgs = list(messages)

    for round_num in range(settings.mcp_max_tool_rounds):
        completion = await client.chat.completions.create(
            model=settings.llm_model,
            messages=msgs,
            max_tokens=settings.llm_max_output_tokens,
            temperature=settings.llm_temperature,
        )
        response_text = completion.choices[0].message.content or ""
        logger.info("tool_loop round=%d finish=%s has_tool_tag=%s",
                    round_num, completion.choices[0].finish_reason,
                    "<tool_call>" in response_text)

        tool_call = _parse_tool_call(response_text)

        if tool_call is None:
            # No tool call — this IS the final answer
            msgs.append({"role": "assistant", "content": response_text})
            return msgs, traces, response_text

        # Execute tool
        name = tool_call.get("name", "")
        arguments = tool_call.get("arguments", {})
        result_json = await _execute_tool(name, arguments, traces)

        # Add assistant turn (the tool call text) + user turn (the result)
        msgs.append({"role": "assistant", "content": response_text})
        msgs.append({"role": "user", "content": result_json})

    # Exceeded max rounds
    logger.warning("tool_loop max_rounds=%d exceeded", settings.mcp_max_tool_rounds)
    return msgs, traces, ABORT_MSG


async def run_full_loop(
    messages: list[dict],
    client: AsyncOpenAI,
) -> LoopResult:
    """Full tool loop including final non-streaming LLM call. Used by POST /api/chat."""
    msgs, traces, direct_answer = await run_tool_rounds(messages, client)

    if direct_answer is not None:
        return LoopResult(answer=direct_answer, traces=traces, messages=msgs)

    # Final call after tool rounds (model should now answer from tool result)
    completion = await client.chat.completions.create(
        model=settings.llm_model,
        messages=msgs,
        max_tokens=settings.llm_max_output_tokens,
        temperature=settings.llm_temperature,
    )
    answer = completion.choices[0].message.content or ""
    msgs.append({"role": "assistant", "content": answer})
    return LoopResult(answer=answer, traces=traces, messages=msgs)
