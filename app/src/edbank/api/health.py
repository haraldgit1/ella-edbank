import logging
from urllib.parse import urlparse
from fastapi import APIRouter
from sqlalchemy import text
import httpx

from edbank.config import settings
from edbank.db.session import engine

logger = logging.getLogger(__name__)
router = APIRouter()


async def _check_postgres() -> tuple[str, str]:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "postgres", "ok"
    except Exception:
        return "postgres", "unavailable"


async def _check_pgvector() -> tuple[str, str]:
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            if result.fetchone():
                return "pgvector", "ok"
            return "pgvector", "not_installed"
    except Exception:
        return "pgvector", "unavailable"


async def _check_mcp() -> tuple[str, str]:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            parsed = urlparse(settings.mcp_server_url)
            health_url = f"{parsed.scheme}://{parsed.netloc}/health"
            r = await client.get(health_url)
            if r.status_code == 200:
                return "mcp_server", "ok"
            return "mcp_server", "degraded"
    except Exception:
        return "mcp_server", "unavailable"


async def _check_llm() -> tuple[str, str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.llm_base_url}/models")
            if r.status_code == 200:
                data = r.json()
                if data.get("data"):
                    return "llm_server", "ok"
                return "llm_server", "no_model_loaded"
            return "llm_server", "unavailable"
    except Exception:
        return "llm_server", "unavailable"


@router.get("/api/health")
async def health():
    results = {}
    for key, status in await _gather_checks():
        results[key] = status

    results["app"] = "ok"
    overall = "ok" if all(v == "ok" for v in results.values()) else "degraded"
    return {"status": overall, "components": results}


async def _gather_checks():
    import asyncio
    return await asyncio.gather(
        _check_postgres(),
        _check_pgvector(),
        _check_mcp(),
        _check_llm(),
    )
