import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from edbank.config import settings
from edbank.rag.embeddings import embed_query
from edbank.rag.schemas import RetrievalResult

logger = logging.getLogger(__name__)


async def search(
    query: str,
    session: AsyncSession,
    top_k: int | None = None,
    min_score: float | None = None,
) -> list[RetrievalResult]:
    top_k = top_k or settings.rag_top_k
    min_score = min_score if min_score is not None else settings.rag_min_score

    query_vec = embed_query(query)
    vec_str = "[" + ",".join(f"{x:.8f}" for x in query_vec) + "]"

    rows = await session.execute(
        text("""
            SELECT
                c.record_key,
                c.content,
                c.metadata,
                d.source_name,
                1 - (c.embedding <=> CAST(:qv AS vector)) AS score
            FROM rag.chunk c
            JOIN rag.document d ON d.id = c.document_id
            WHERE d.status = 'ready'
              AND 1 - (c.embedding <=> CAST(:qv AS vector)) >= :min_score
            ORDER BY c.embedding <=> CAST(:qv AS vector)
            LIMIT :top_k
        """),
        {"qv": vec_str, "min_score": min_score, "top_k": top_k},
    )

    results = [
        RetrievalResult(
            record_key=r.record_key,
            content=r.content,
            score=float(r.score),
            source_name=r.source_name,
            metadata=r.metadata or {},
        )
        for r in rows.fetchall()
    ]

    logger.info(
        "retrieval query_len=%d results=%d min_score=%.2f",
        len(query), len(results), min_score,
    )
    return results


def build_rag_context(results: list[RetrievalResult]) -> str:
    """
    Build the RAG context block for injection into the LLM prompt.
    Only includes results whose record_key starts with 'ORA-' to avoid
    polluting bank-account queries with irrelevant Oracle error excerpts.
    """
    ora_results = [r for r in results if (r.record_key or "").startswith("ORA-")]
    if not ora_results:
        return ""
    blocks = [r.content for r in ora_results]
    joined = "\n---\n".join(blocks)
    return (
        "Relevante Einträge aus der lokalen Wissensbasis (ora.csv):\n"
        "---\n"
        f"{joined}\n"
        "---\n"
        "Bitte stütze deine Antwort auf diese Einträge und nenne die Quelle."
    )
