import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from edbank.config import settings
from edbank.db.session import get_db
from edbank.rag.importer import import_csv
from edbank.rag.schemas import ImportResponse, RagStatusResponse

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTENSIONS = {".csv"}
ALLOWED_MIME_TYPES = {"text/csv", "text/plain", "application/csv", "application/octet-stream"}


@router.post("/api/rag/import", response_model=ImportResponse)
async def rag_import(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
) -> ImportResponse:
    filename = file.filename or "upload.csv"

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=422, detail="Nur .csv-Dateien sind erlaubt.")

    content = await file.read()

    if not content:
        raise HTTPException(status_code=422, detail="Datei ist leer.")

    # Rough MIME / content check: first non-whitespace chars should be printable text
    try:
        sample = content[:512].decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="Datei muss UTF-8-codiert sein.")

    try:
        result = await import_csv(content, filename, session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("CSV import failed: %s", exc)
        raise HTTPException(status_code=500, detail="Import fehlgeschlagen.") from exc

    return result


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
