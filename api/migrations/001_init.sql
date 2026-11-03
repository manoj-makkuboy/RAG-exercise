CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id          UUID PRIMARY KEY,
    filename    TEXT NOT NULL,
    media_type  TEXT NOT NULL,
    sha256      TEXT NOT NULL UNIQUE,
    page_count  INT  NOT NULL,
    chunk_count INT  NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id          UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT  NOT NULL,
    page_number INT,
    content     TEXT NOT NULL,
    token_count INT  NOT NULL,
    embedding   vector(384) NOT NULL,
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);

CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_gin ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_document_id ON chunks (document_id);

-- One row per chat request: what we retrieved, what we answered, how long it took.
CREATE TABLE IF NOT EXISTS query_traces (
    id             UUID PRIMARY KEY,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    question       TEXT NOT NULL,
    outcome        TEXT NOT NULL,
    retrieved      JSONB NOT NULL,
    answer         TEXT,
    model          TEXT,
    input_tokens   INT,
    output_tokens  INT,
    timings_ms     JSONB NOT NULL
);
