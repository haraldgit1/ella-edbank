#!/usr/bin/env bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Application role: read/write on RAG, read-only on banking
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'edbank_app') THEN
            CREATE ROLE edbank_app WITH LOGIN PASSWORD '${APP_DB_PASSWORD}';
        END IF;
    END
    \$\$;

    -- Reader role: read-only on banking (used by MCP server)
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'edbank_reader') THEN
            CREATE ROLE edbank_reader WITH LOGIN PASSWORD '${READER_DB_PASSWORD}';
        END IF;
    END
    \$\$;

    -- edbank_app: read/write on rag schema
    GRANT USAGE ON SCHEMA rag TO edbank_app;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA rag TO edbank_app;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA rag TO edbank_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA rag
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO edbank_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA rag
        GRANT USAGE, SELECT ON SEQUENCES TO edbank_app;

    -- edbank_app: read-only on banking schema
    GRANT USAGE ON SCHEMA banking TO edbank_app;
    GRANT SELECT ON ALL TABLES IN SCHEMA banking TO edbank_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA banking
        GRANT SELECT ON TABLES TO edbank_app;

    -- edbank_reader: read-only on banking schema only
    GRANT USAGE ON SCHEMA banking TO edbank_reader;
    GRANT SELECT ON ALL TABLES IN SCHEMA banking TO edbank_reader;
    ALTER DEFAULT PRIVILEGES IN SCHEMA banking
        GRANT SELECT ON TABLES TO edbank_reader;
EOSQL
