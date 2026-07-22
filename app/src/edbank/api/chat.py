import json
import logging
import re
import uuid
from collections import defaultdict
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from edbank.config import settings
from edbank.db.session import get_db
from edbank.llm.client import get_llm_client
from edbank.llm.prompts import SYSTEM_PROMPT
from edbank.llm.tool_loop import run_full_loop, run_tool_rounds, ToolTrace
from edbank.rag import retriever as rag_retriever
from edbank.rag.schemas import RetrievalResult

logger = logging.getLogger(__name__)
router = APIRouter()

_conversations: dict[str, list[dict]] = defaultdict(list)

MAX_MESSAGE_LENGTH = 4000
MAX_HISTORY_MESSAGES = 20

# Pattern für eindeutige MCP-Anfragen (IBAN/Konto einer Person).
# Bei Match wird RAG-Kontext nicht injiziert, damit das MCP-Tool
# nicht durch Banking-HTML-Treffer konkurriert.
_MCP_INTENT_RE = re.compile(
    r"\b(iban|konto|bankverbindung|kontonummer|bic)\b",
    re.IGNORECASE,
)


class ChatRequest(BaseModel):
    conversation_id: str | None = Field(default=None)
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)


class SourceInfo(BaseModel):
    record_key: str | None
    source_name: str
    score: float


class ToolCallInfo(BaseModel):
    name: str
    status: str
    duration_ms: int | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    answer_markdown: str
    sources: list[SourceInfo] = []
    tool_calls: list[ToolCallInfo] = []
    model: str
    finish_reason: str


def _build_initial_messages(
    conversation_id: str,
    user_message: str,
    rag_context: str | None,
) -> list[dict]:
    """Build the message list for the first LLM call of this turn."""
    history = _conversations[conversation_id][-MAX_HISTORY_MESSAGES:]

    content = user_message
    if rag_context:
        content = f"{content}\n\n{rag_context}"

    current_msg = {"role": "user", "content": content}

    if not history:
        # Inject system prompt into first user message (Mistral v0.3 quirk)
        current_msg["content"] = f"{SYSTEM_PROMPT}\n\n{content}"
        return [current_msg]

    # Continuing conversation: ensure system prompt stays in context.
    # History is stored without the system prompt prefix, so we re-inject
    # it into the first history message here (only for the LLM call, not persisted).
    msgs = list(history)
    first = msgs[0]
    if first["role"] == "user" and not first["content"].startswith(SYSTEM_PROMPT):
        msgs[0] = {"role": first["role"], "content": f"{SYSTEM_PROMPT}\n\n{first['content']}"}
    msgs.append(current_msg)
    return msgs


def _traces_to_info(traces: list[ToolTrace]) -> list[ToolCallInfo]:
    return [
        ToolCallInfo(name=t.name, status=t.status, duration_ms=t.duration_ms)
        for t in traces
    ]


def _sources_from_rag(results: list[RetrievalResult]) -> list[SourceInfo]:
    return [
        SourceInfo(record_key=r.record_key, source_name=r.source_name, score=r.score)
        for r in results
    ]


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, session=Depends(get_db)) -> ChatResponse:
    conversation_id = req.conversation_id or str(uuid.uuid4())
    user_message = req.message.strip()
    if not user_message:
        raise HTTPException(status_code=422, detail="Nachricht darf nicht leer sein.")

    # RAG — bei klaren MCP-Anfragen (IBAN/Konto) nicht injizieren,
    # damit Banking-HTML-Treffer das MCP-Tool nicht verdrängen.
    mcp_intent = bool(_MCP_INTENT_RE.search(user_message))
    rag_results: list[RetrievalResult] = []
    if not mcp_intent:
        try:
            rag_results = await rag_retriever.search(user_message, session)
        except Exception as exc:
            logger.warning("RAG search failed: %s", exc)

    rag_context = rag_retriever.build_rag_context(rag_results) if rag_results else None
    messages = _build_initial_messages(conversation_id, user_message, rag_context)
    client = get_llm_client()

    try:
        loop_result = await run_full_loop(messages, client)
    except Exception as exc:
        logger.error("Tool loop failed: %s", exc)
        raise HTTPException(status_code=503, detail="Das lokale Sprachmodell ist derzeit nicht erreichbar.") from exc

    answer = loop_result.answer

    # Persist raw user message + answer (without injected context)
    _conversations[conversation_id].append({"role": "user", "content": user_message})
    _conversations[conversation_id].append({"role": "assistant", "content": answer})

    logger.info(
        "chat conversation_id=%s rag_hits=%d tool_calls=%d",
        conversation_id, len(rag_results), len(loop_result.traces),
    )

    return ChatResponse(
        conversation_id=conversation_id,
        answer_markdown=answer,
        sources=_sources_from_rag(rag_results),
        tool_calls=_traces_to_info(loop_result.traces),
        model=settings.llm_model,
        finish_reason="stop",
    )


async def _stream_with_tool_loop(
    conversation_id: str,
    user_message: str,
    rag_results: list[RetrievalResult],
) -> AsyncIterator[str]:
    rag_context = rag_retriever.build_rag_context(rag_results) if rag_results else None
    messages = _build_initial_messages(conversation_id, user_message, rag_context)
    client = get_llm_client()

    try:
        # Run tool rounds (non-streaming) first
        msgs, traces, direct_answer = await run_tool_rounds(messages, client)
    except Exception as exc:
        logger.error("Tool rounds failed: %s", exc)
        err = json.dumps({"error": "Das lokale Sprachmodell ist derzeit nicht erreichbar."})
        yield f"data: {err}\n\n"
        return

    full_answer: str

    if direct_answer is not None:
        # Model answered directly (no tool call needed, or max rounds reached)
        # Emit as a single delta so the frontend renders it progressively
        full_answer = direct_answer
        payload = json.dumps({"delta": direct_answer, "conversation_id": conversation_id})
        yield f"data: {payload}\n\n"
    else:
        # Final streaming call (no tools offered — model just answers)
        collected = []
        try:
            stream = await client.chat.completions.create(
                model=settings.llm_model,
                messages=msgs,
                max_tokens=settings.llm_max_output_tokens,
                temperature=settings.llm_temperature,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    collected.append(delta)
                    payload = json.dumps({"delta": delta, "conversation_id": conversation_id})
                    yield f"data: {payload}\n\n"
        except Exception as exc:
            logger.error("Final stream failed: %s", exc)
            err = json.dumps({"error": "Das lokale Sprachmodell ist derzeit nicht erreichbar."})
            yield f"data: {err}\n\n"
            return
        full_answer = "".join(collected)

    # Persist
    _conversations[conversation_id].append({"role": "user", "content": user_message})
    _conversations[conversation_id].append({"role": "assistant", "content": full_answer})

    sources_json = [
        {"record_key": r.record_key, "source_name": r.source_name, "score": r.score}
        for r in rag_results
    ]
    tool_calls_json = [
        {"name": t.name, "status": t.status, "duration_ms": t.duration_ms}
        for t in traces
    ]
    done = json.dumps({
        "done": True,
        "conversation_id": conversation_id,
        "model": settings.llm_model,
        "sources": sources_json,
        "tool_calls": tool_calls_json,
    })
    yield f"data: {done}\n\n"


@router.post("/api/chat/stream")
async def chat_stream(req: ChatRequest, session=Depends(get_db)) -> StreamingResponse:
    conversation_id = req.conversation_id or str(uuid.uuid4())
    user_message = req.message.strip()
    if not user_message:
        raise HTTPException(status_code=422, detail="Nachricht darf nicht leer sein.")

    mcp_intent = bool(_MCP_INTENT_RE.search(user_message))
    rag_results: list[RetrievalResult] = []
    if not mcp_intent:
        try:
            rag_results = await rag_retriever.search(user_message, session)
        except Exception as exc:
            logger.warning("RAG search failed: %s", exc)

    return StreamingResponse(
        _stream_with_tool_loop(conversation_id, user_message, rag_results),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/chat/{conversation_id}/context")
async def conversation_context(conversation_id: str) -> dict:
    msgs = _conversations.get(conversation_id, [])
    turns = len(msgs) // 2  # user + assistant pairs
    # Rough token estimate: ~4 chars per token
    char_count = sum(len(m.get("content", "")) for m in msgs) + len(SYSTEM_PROMPT)
    token_estimate = char_count // 4
    context_limit = settings.llm_context_tokens
    return {
        "conversation_id": conversation_id,
        "turns": turns,
        "messages": len(msgs),
        "token_estimate": token_estimate,
        "context_limit": context_limit,
        "context_pct": min(100, round(token_estimate / context_limit * 100)),
    }


@router.delete("/api/chat/{conversation_id}")
async def clear_conversation(conversation_id: str) -> dict:
    _conversations.pop(conversation_id, None)
    return {"conversation_id": conversation_id, "cleared": True}
