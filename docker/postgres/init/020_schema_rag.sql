CREATE SCHEMA IF NOT EXISTS rag;

CREATE TABLE rag.document (
    id              UUID PRIMARY KEY,
    source_name     TEXT NOT NULL,
    source_sha256   CHAR(64) NOT NULL,
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    record_count    INTEGER NOT NULL,
    status          TEXT NOT NULL,
    UNIQUE (source_name, source_sha256)
);

CREATE TABLE rag.chunk (
    id              UUID PRIMARY KEY,
    document_id     UUID NOT NULL
                    REFERENCES rag.document(id)
                    ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    record_key      TEXT,
    content         TEXT NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding       vector(384) NOT NULL,
    UNIQUE (document_id, chunk_index)
);
