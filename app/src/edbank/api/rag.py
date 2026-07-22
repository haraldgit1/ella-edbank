import logging
from datetime import datetime
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from edbank.config import settings
from edbank.db.session import get_db
from edbank.rag.importer import import_document
from edbank.rag.parsers import SUPPORTED_EXTENSIONS
from edbank.rag.schemas import ImportResponse, RagStatusResponse, DocumentInfo

logger = logging.getLogger(__name__)
router = APIRouter()

_URL_FETCH_TIMEOUT = 15  # seconds
_MAX_URL_CONTENT_BYTES = 5 * 1024 * 1024  # 5 MB


class UrlImportRequest(BaseModel):
    url: str


@router.post("/api/rag/import", response_model=ImportResponse)
async def rag_import(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
) -> ImportResponse:
    filename = file.filename or "upload"

    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise HTTPException(
            status_code=422,
            detail=f"Nicht unterstützter Dateityp '{ext}'. Erlaubt: {supported}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Datei ist leer.")

    try:
        content[:512].decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="Datei muss UTF-8-codiert sein.")

    try:
        result = await import_document(content, filename, session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Import failed: %s", exc)
        raise HTTPException(status_code=500, detail="Import fehlgeschlagen.") from exc

    return result


@router.post("/api/rag/import-url", response_model=ImportResponse)
async def rag_import_url(
    req: UrlImportRequest,
    session: AsyncSession = Depends(get_db),
) -> ImportResponse:
    url = req.url.strip()

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=422, detail="Ungültige URL. Nur http:// und https:// sind erlaubt.")

    # Derive a readable filename from the URL (used as source_name)
    path = parsed.path.rstrip("/")
    filename = path.split("/")[-1] if path else parsed.netloc
    if not filename:
        filename = parsed.netloc
    # Ensure .html extension so the HTML parser is selected
    if "." not in filename.split("/")[-1]:
        filename = filename + ".html"
    elif not filename.lower().endswith((".html", ".htm")):
        filename = filename + ".html"

    logger.info("url_import url=%s filename=%s", url, filename)

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=_URL_FETCH_TIMEOUT) as client:
            response = await client.get(url, headers={"User-Agent": "Ella-DemoBank/1.0 RAG-Importer"})
            response.raise_for_status()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"Timeout beim Abrufen der URL (>{_URL_FETCH_TIMEOUT}s).")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=422, detail=f"HTTP-Fehler beim Abrufen: {exc.response.status_code}.")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"URL konnte nicht abgerufen werden: {exc}") from exc

    content = response.content
    if len(content) > _MAX_URL_CONTENT_BYTES:
        raise HTTPException(status_code=422, detail="Seite zu groß (max. 5 MB).")

    if not content:
        raise HTTPException(status_code=422, detail="Die URL lieferte keinen Inhalt.")

    try:
        result = await import_document(content, filename, session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("URL import failed: %s", exc)
        raise HTTPException(status_code=500, detail="Import fehlgeschlagen.") from exc

    return result


@router.get("/api/rag/documents", response_model=list[DocumentInfo])
async def rag_documents(session: AsyncSession = Depends(get_db)) -> list[DocumentInfo]:
    try:
        rows = await session.execute(text("""
            SELECT source_name, record_count, imported_at
            FROM rag.document
            WHERE status = 'ready'
            ORDER BY imported_at DESC
        """))
        return [
            DocumentInfo(
                source_name=r.source_name,
                record_count=r.record_count,
                imported_at=r.imported_at.isoformat() if r.imported_at else None,
            )
            for r in rows.fetchall()
        ]
    except Exception:
        return []


@router.get("/api/rag/status", response_model=RagStatusResponse)
async def rag_status(session: AsyncSession = Depends(get_db)) -> RagStatusResponse:
    try:
        doc_count = (await session.execute(
            text("SELECT COUNT(*) FROM rag.document WHERE status = 'ready'")
        )).scalar() or 0

        chunk_count = (await session.execute(
            text("""
                SELECT COUNT(*) FROM rag.chunk c
                JOIN rag.document d ON d.id = c.document_id
                WHERE d.status = 'ready'
            """)
        )).scalar() or 0
    except Exception:
        return RagStatusResponse(
            documents=0, chunks=0,
            embedding_model=settings.embedding_model,
            ready=False,
        )

    return RagStatusResponse(
        documents=int(doc_count),
        chunks=int(chunk_count),
        embedding_model=settings.embedding_model,
        ready=chunk_count > 0,
    )
