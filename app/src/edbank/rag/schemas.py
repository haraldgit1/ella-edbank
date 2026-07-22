from pydantic import BaseModel


class DocumentInfo(BaseModel):
    source_name: str
    record_count: int
    imported_at: str | None = None


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
