import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from edbank.api.health import router as health_router
from edbank.api.chat import router as chat_router
from edbank.api.rag import router as rag_router
from edbank.config import settings

logging.basicConfig(
    level=settings.edbank_log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("edbank-app starting (env=%s)", settings.edbank_env)
    yield
    logger.info("edbank-app shutting down")


app = FastAPI(title="Ella-DemoBank API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(rag_router)


@app.get("/")
async def root():
    return {"service": "edbank-app", "status": "running"}
