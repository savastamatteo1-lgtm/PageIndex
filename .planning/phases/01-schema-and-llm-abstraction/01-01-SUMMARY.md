---
phase: 01-schema-and-llm-abstraction
plan: 01
subsystem: database
tags: [supabase, postgres, pgvector, italian-legal, sql-migration, data-access-layer]

# Dependency graph
requires:
  - phase: none
    provides: "First plan - no prior dependencies"
provides:
  - "Supabase DDL migration with documents, document_trees, chunks tables"
  - "match_chunks RPC function for vector similarity search"
  - "pageindex_readonly role for LLM-generated SQL safety"
  - "Python data access layer (pageindex.db) for all three tables"
  - "Italian legal vocabulary reference for metadata extraction"
affects: [01-02, ingestion-pipeline, retrieval-engines]

# Tech tracking
tech-stack:
  added: [supabase, pgvector]
  patterns: [singleton-client, rpc-vector-search, open-text-taxonomy, upsert-on-conflict]

key-files:
  created:
    - pageindex/db/migrations/001_initial_schema.sql
    - pageindex/db/__init__.py
    - pageindex/db/client.py
    - pageindex/db/documents.py
    - pageindex/db/chunks.py
    - pageindex/db/trees.py
    - pageindex/schema/legal_vocabulary.yaml
  modified: []

key-decisions:
  - "Used DO block for conditional role creation to avoid errors if role already exists"
  - "Trees use upsert on doc_id conflict to support re-indexing without manual deletion"
  - "Supabase range() for pagination instead of limit/offset to match PostgREST API"

patterns-established:
  - "Singleton client: all DB access goes through get_client() from pageindex.db.client"
  - "RPC for vector search: match_chunks function called via supabase.rpc(), not direct operator queries"
  - "Open text taxonomy: no CHECK constraints or Postgres ENUMs on doc_type, court_level, legal_area"
  - "Metadata filtering: insert_document filters None values to let DB defaults apply"

requirements-completed: [FOUND-01, FOUND-02]

# Metrics
duration: 3min
completed: 2026-02-22
---

# Phase 1 Plan 01: Schema and Data Access Layer Summary

**Supabase DDL migration with three tables (documents, chunks, document_trees), HNSW vector index, match_chunks RPC, pageindex_readonly role, Python data access layer, and Italian legal vocabulary reference**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-22T07:58:15Z
- **Completed:** 2026-02-22T08:01:44Z
- **Tasks:** 2
- **Files created:** 7

## Accomplishments
- SQL migration with full Italian legal metadata schema (doc_type, date, authority, ecli, gu_number, legal_area, parties, court_level, cross_references) using open text fields -- no hardcoded enums
- HNSW index on chunks.embedding (m=16, ef_construction=64) for scalable vector similarity search from day one
- match_chunks RPC function wrapping pgvector cosine distance operator for PostgREST compatibility
- Python data access layer with typed functions for documents (insert/get/list), chunks (batch insert/vector search), and trees (upsert/get)
- Italian legal vocabulary YAML with hierarchical taxonomy of doc_types, legal_areas, court_levels, party_roles, and cross_reference_types

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Supabase migration SQL and legal vocabulary reference** - `8c633d1` (feat)
2. **Task 2: Create Supabase Python data access layer** - `2d6c0b3` (feat)

## Files Created/Modified
- `pageindex/db/migrations/001_initial_schema.sql` - DDL for all tables, indexes, RPC function, and read-only role
- `pageindex/db/__init__.py` - Package init re-exporting all key functions
- `pageindex/db/client.py` - Supabase client singleton with env var validation
- `pageindex/db/documents.py` - Documents table CRUD (insert, get, get_by_name, list)
- `pageindex/db/chunks.py` - Chunks table operations and match_chunks RPC wrapper
- `pageindex/db/trees.py` - Document trees upsert and retrieval
- `pageindex/schema/legal_vocabulary.yaml` - Italian legal terminology conventions for LLM metadata extraction

## Decisions Made
- Used `DO $$ ... END $$` block for conditional role creation to make the migration idempotent (avoids error if `pageindex_readonly` already exists)
- Trees module uses `upsert` with `on_conflict="doc_id"` so re-indexing a document replaces its tree without requiring manual deletion
- Documents module uses Supabase `range()` for pagination to align with PostgREST conventions
- Metadata column set defined explicitly in `_METADATA_COLUMNS` to prevent injection of arbitrary columns

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. The migration SQL must be applied to a Supabase instance before the data access layer can be used, but that is expected setup for Phase 2.

## Next Phase Readiness
- Database schema and Python access layer are ready for Plan 02 (LiteLLM provider abstraction)
- After Plan 02 completes, Phase 2 (Ingestion Pipeline) can store processed documents via this data access layer
- The legal vocabulary YAML is ready for the LLM metadata extractor in Phase 2

## Self-Check: PASSED

- All 7 created files verified present on disk
- Commit `8c633d1` (Task 1) verified in git log
- Commit `2d6c0b3` (Task 2) verified in git log

---
*Phase: 01-schema-and-llm-abstraction*
*Completed: 2026-02-22*
