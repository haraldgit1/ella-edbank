import logging
import threading
from edbank.config import settings

logger = logging.getLogger(__name__)

_model = None
_lock = threading.Lock()


def _load_model():
    from sentence_transformers import SentenceTransformer
    logger.info("Loading embedding model: %s", settings.embedding_model)
    m = SentenceTransformer(settings.embedding_model)
    logger.info("Embedding model loaded.")
    return m


def get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                _model = _load_model()
    return _model


def embed_query(text: str) -> list[float]:
    return get_model().encode(
        f"query: {text}",
        normalize_embeddings=True,
        show_progress_bar=False,
    ).tolist()


def embed_passages(texts: list[str]) -> list[list[float]]:
    prefixed = [f"passage: {t}" for t in texts]
    return get_model().encode(
        prefixed,
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=False,
    ).tolist()
