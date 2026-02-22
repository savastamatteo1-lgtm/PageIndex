-- 001_initial_schema.sql
-- Initial database schema for PageIndex Legal Retrieval
-- Creates: documents, document_trees, chunks tables with indexes,
--          match_chunks RPC function, and pageindex_readonly role.

-- =============================================================================
-- Extensions
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- =============================================================================
-- Tables
-- =============================================================================

-- Documents table: stores Italian legal document metadata.
-- All taxonomy fields use open TEXT (no hardcoded enums) so new values
-- can be added without schema migrations. Standard conventions are
-- documented in pageindex/schema/legal_vocabulary.yaml.
CREATE TABLE IF NOT EXISTS documents (
    doc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_name TEXT NOT NULL,
    doc_description TEXT,

    -- Italian legal metadata (open text, no enum constraints)
    doc_type TEXT,                                       -- sentenza, ordinanza, decreto, legge, etc.
    date DATE,                                           -- document date
    authority TEXT,                                      -- issuing authority
    ecli TEXT,                                           -- European Case Law Identifier
    gu_number TEXT,                                      -- Gazzetta Ufficiale number
    legal_area TEXT[],                                   -- array of legal sub-areas
    parties JSONB DEFAULT '[]'::jsonb,                   -- [{name, role}]
    court_level TEXT,                                    -- Cassazione, Corte d'Appello, Tribunale, etc.
    cross_references JSONB DEFAULT '[]'::jsonb,          -- [{ref, source, type}]

    -- Flexible overflow for rare/unexpected fields
    additional_fields JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Document trees: one tree structure per document, produced by PageIndex.
CREATE TABLE IF NOT EXISTS document_trees (
    tree_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    tree_json JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(doc_id)
);

-- Chunks: leaf-node text segments with vector embeddings for semantic search.
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    node_id TEXT,                                        -- node_id from tree structure for traceability
    content TEXT NOT NULL,                               -- chunk text content
    embedding vector(768),                               -- default 768 dimensions, configurable via migration regeneration
    metadata JSONB DEFAULT '{}'::jsonb,                  -- node title, start/end page, etc.
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- Indexes
-- =============================================================================

-- HNSW index for vector similarity search (cosine distance)
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
    ON chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- GIN indexes for JSONB query performance
CREATE INDEX IF NOT EXISTS documents_parties_gin_idx
    ON documents USING GIN (parties);
CREATE INDEX IF NOT EXISTS documents_cross_refs_gin_idx
    ON documents USING GIN (cross_references);

-- GIN index for text[] array column
CREATE INDEX IF NOT EXISTS documents_legal_area_idx
    ON documents USING GIN (legal_area);

-- B-tree indexes for common filter columns
CREATE INDEX IF NOT EXISTS documents_doc_type_idx ON documents (doc_type);
CREATE INDEX IF NOT EXISTS documents_date_idx ON documents (date);
CREATE INDEX IF NOT EXISTS documents_court_level_idx ON documents (court_level);
CREATE INDEX IF NOT EXISTS documents_ecli_idx ON documents (ecli);

-- =============================================================================
-- RPC Functions
-- =============================================================================

-- Vector similarity search via cosine distance.
-- PostgREST does not support pgvector operators directly, so this
-- function is called via supabase.rpc('match_chunks', {...}).
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(768),
    match_threshold float DEFAULT 0.7,
    match_count int DEFAULT 20
)
RETURNS TABLE (
    chunk_id UUID,
    doc_id UUID,
    content TEXT,
    metadata JSONB,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.chunk_id,
        c.doc_id,
        c.content,
        c.metadata,
        1 - (c.embedding <=> query_embedding) AS similarity
    FROM chunks c
    WHERE 1 - (c.embedding <=> query_embedding) > match_threshold
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- =============================================================================
-- Read-only role for LLM-generated SQL queries (Phase 3 safety net)
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pageindex_readonly') THEN
        CREATE ROLE pageindex_readonly WITH LOGIN;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO pageindex_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO pageindex_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO pageindex_readonly;

-- Explicitly deny write permissions
REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM pageindex_readonly;
