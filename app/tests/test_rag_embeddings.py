"""
Unit tests for RAG embeddings and retriever (Spec §28.1 – RAG).
Embedding model is loaded once for the test session.
Retriever DB calls are mocked.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── embedding tests ───────────────────────────────────────────────────────────

def test_embed_query_returns_384_dimensions():
    from edbank.rag.embeddings import embed_query
    vec = embed_query("Was bedeutet ORA-01555?")
    assert len(vec) == 384


def test_embed_passages_returns_384_dimensions():
    from edbank.rag.embeddings import embed_passages
    texts = ["Oracle error code: ORA-01555\nDescription: Snapshot too old"]
    vecs = embed_passages(texts)
    assert len(vecs) == 1
    assert len(vecs[0]) == 384


def test_embed_query_normalized():
    """E5 with normalize_embeddings=True → unit vector (L2-norm ≈ 1.0)."""
    import math
    from edbank.rag.embeddings import embed_query
    vec = embed_query("test query")
    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 0.01


# ── retriever context builder ─────────────────────────────────────────────────

def test_build_rag_context_filters_non_ora():
    from edbank.rag.schemas import RetrievalResult
    from edbank.rag.retriever import build_rag_context

    results = [
        RetrievalResult(record_key="ORA-01555", content="snapshot too old", score=0.85, source_name="ora.csv"),
        RetrievalResult(record_key="IBAN-query", content="bank stuff", score=0.80, source_name="ora.csv"),
    ]
    ctx = build_rag_context(results)
    assert "snapshot too old" in ctx
    assert "bank stuff" not in ctx


def test_build_rag_context_empty_returns_empty():
    from edbank.rag.retriever import build_rag_context
    assert build_rag_context([]) == ""


def test_build_rag_context_only_non_ora_returns_empty():
    from edbank.rag.schemas import RetrievalResult
    from edbank.rag.retriever import build_rag_context
    results = [
        RetrievalResult(record_key="IBAN", content="irrelevant", score=0.90, source_name="ora.csv"),
    ]
    assert build_rag_context(results) == ""


# ── retriever search (mocked DB) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retriever_returns_ora_01555():
    from edbank.rag.schemas import RetrievalResult

    mock_row = MagicMock()
    mock_row.record_key = "ORA-01555"
    mock_row.content = "Oracle error code: ORA-01555\nDescription: Snapshot too old"
    mock_row.score = 0.85
    mock_row.source_name = "ora.csv"
    mock_row.metadata = {}

    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(fetchall=MagicMock(return_value=[mock_row])))

    with patch("edbank.rag.retriever.embed_query", return_value=[0.1] * 384):
        from edbank.rag.retriever import search
        results = await search("Was bedeutet ORA-01555?", session)

    assert len(results) == 1
    assert results[0].record_key == "ORA-01555"
    assert results[0].score == pytest.approx(0.85)


@pytest.mark.asyncio
async def test_retriever_irrelevant_question_returns_empty():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))

    with patch("edbank.rag.retriever.embed_query", return_value=[0.1] * 384):
        from edbank.rag.retriever import search
        results = await search("Wie ist das Wetter heute?", session)

    assert results == []


@pytest.mark.asyncio
async def test_retriever_preserves_source_metadata():
    mock_row = MagicMock()
    mock_row.record_key = "ORA-00001"
    mock_row.content = "Oracle error code: ORA-00001"
    mock_row.score = 0.80
    mock_row.source_name = "ora.csv"
    mock_row.metadata = {"source_name": "ora.csv"}

    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(fetchall=MagicMock(return_value=[mock_row])))

    with patch("edbank.rag.retriever.embed_query", return_value=[0.1] * 384):
        from edbank.rag.retriever import search
        results = await search("ORA-00001", session)

    assert results[0].source_name == "ora.csv"
    assert results[0].metadata == {"source_name": "ora.csv"}
