from pydantic import BaseModel


class ImportResponse(BaseModel):
    document_id: str
    source_name: str
    imported_records: int
    warnings: list[str]
    status: str


class RagStatusResponse(BaseModel):
    documents: int
    chunks: int
    embedding_model: str
    ready: bool


class RetrievalResult(BaseModel):
    record_key: str | None
    content: str
    score: float
    source_name: str
    metadata: dict = {}
