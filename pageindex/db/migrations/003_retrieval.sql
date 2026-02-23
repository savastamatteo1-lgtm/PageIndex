-- 003_retrieval.sql
-- Retrieval engine infrastructure: pg_trgm fuzzy indexes, description
-- embedding column, and match_descriptions RPC.
--
-- This migration adds the database infrastructure needed by Phase 3
-- retrieval engines:
--   1. pg_trgm extension for trigram-based fuzzy matching
--   2. GIN trigram indexes on text metadata columns for fast ILIKE queries
--   3. description_embedding vector column on documents for description search
--   4. HNSW index on description_embedding for fast cosine similarity
--   5. match_descriptions RPC function for description embedding search
--
-- The existing B-tree indexes from 001 coexist with the new GIN indexes:
-- B-tree handles equality lookups, GIN handles ILIKE pattern matching.

-- =============================================================================
-- Extensions
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =============================================================================
-- Trigram GIN Indexes for ILIKE Fuzzy Matching
-- =============================================================================

-- Accelerate ILIKE patterns on text metadata columns used by the metadata
-- retrieval engine.  Without these indexes, ILIKE '%pattern%' triggers
-- sequential scans on the entire documents table.

CREATE INDEX IF NOT EXISTS documents_doc_type_trgm_idx
    ON documents USING GIN (doc_type gin_trgm_ops);

CREATE INDEX IF NOT EXISTS documents_authority_trgm_idx
    ON documents USING GIN (authority gin_trgm_ops);

CREATE INDEX IF NOT EXISTS documents_court_level_trgm_idx
    ON documents USING GIN (court_level gin_trgm_ops);

CREATE INDEX IF NOT EXISTS documents_ecli_trgm_idx
    ON documents USING GIN (ecli gin_trgm_ops);

-- =============================================================================
-- Description Embedding Column
-- =============================================================================

-- Add a vector column for pre-embedded document descriptions.
-- The description engine compares query embeddings against these vectors
-- for fast document-level similarity search without an LLM call per query.

ALTER TABLE documents ADD COLUMN IF NOT EXISTS description_embedding vector(768);

-- =============================================================================
-- HNSW Index on Description Embeddings
-- =============================================================================

-- Fast approximate nearest-neighbour search using cosine distance.
-- Same HNSW parameters as the chunks embedding index from migration 001.

CREATE INDEX IF NOT EXISTS documents_desc_embedding_hnsw_idx
    ON documents USING hnsw (description_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- =============================================================================
-- match_descriptions RPC Function
-- =============================================================================

-- Vector similarity search against document description embeddings.
-- Called via supabase.rpc('match_descriptions', {...}) from the
-- description retrieval engine.  Mirrors the match_chunks pattern from
-- migration 001 but operates on document-level description vectors.

CREATE OR REPLACE FUNCTION match_descriptions(
    query_embedding vector(768),
    match_threshold float DEFAULT 0.7,
    match_count int DEFAULT 10
)
RETURNS TABLE (
    doc_id UUID,
    doc_name TEXT,
    doc_description TEXT,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.doc_id,
        d.doc_name,
        d.doc_description,
        1 - (d.description_embedding <=> query_embedding) AS similarity
    FROM documents d
    WHERE d.description_embedding IS NOT NULL
      AND 1 - (d.description_embedding <=> query_embedding) > match_threshold
    ORDER BY d.description_embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- =============================================================================
-- Permissions
-- =============================================================================

-- Grant SELECT on the new function to the read-only role for defense-in-depth.
-- This ensures LLM-driven queries can only read, never modify data.

GRANT EXECUTE ON FUNCTION match_descriptions(vector(768), float, int)
    TO pageindex_readonly;
