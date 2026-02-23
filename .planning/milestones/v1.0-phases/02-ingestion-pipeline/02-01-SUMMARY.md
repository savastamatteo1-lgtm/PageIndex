---
phase: 02-ingestion-pipeline
plan: 01
subsystem: ingestion
tags: [chunker, prompts, llm-metadata, recursive-split, tree-aware, italian-legal, dataclasses, sql-migration]

# Dependency graph
requires:
  - phase: 01-schema-and-llm-abstraction
    provides: "documents table schema, LLMProvider with count_tokens, legal_vocabulary.yaml"
provides:
  - "DB migration adding ingestion_status and needs_review columns to documents table"
  - "DocumentPipeline and ChunkData dataclasses for pipeline state management"
  - "LLM prompt templates for Italian legal metadata extraction with vocabulary injection"
  - "JSON schema for structured LLM output via LiteLLM response_format"
  - "Recursive text splitter respecting tree leaf node boundaries with configurable overlap"
  - "Tree path builder and contextual embedding text builder"
affects: [02-02, 02-03, retrieval-engines]

# Tech tracking
tech-stack:
  added: []
  patterns: [tree-aware-chunking, contextual-embedding-prefix, vocabulary-injection, separator-hierarchy-split]

key-files:
  created:
    - pageindex/db/migrations/002_ingestion_status.sql
    - pageindex/ingestion/__init__.py
    - pageindex/ingestion/models.py
    - pageindex/ingestion/prompts.py
    - pageindex/ingestion/chunker.py
  modified: []

key-decisions:
  - "Recursive splitter uses separator hierarchy (paragraphs > lines > sentences > words) with midpoint fallback"
  - "Vocabulary formatting helpers convert YAML structure to readable prompt sections for LLM injection"
  - "ChunkData.metadata.sub_chunk_index is None for single-chunk leaves, integer for sub-chunks"
  - "build_tree_path uses DFS with backtracking to construct human-readable node paths"

patterns-established:
  - "Tree-aware chunking: leaf nodes are the primary semantic container, sub-chunking only when size forces it"
  - "Contextual embedding prefix: every chunk gets full metadata block + tree path before embedding"
  - "Vocabulary injection: full legal_vocabulary.yaml formatted and injected into extraction prompt"
  - "Module-level caching: load_vocabulary() caches at module level to avoid repeated disk reads"

requirements-completed: [FOUND-04, SEM-01, ENRICH-01, ENRICH-02]

# Metrics
duration: 3min
completed: 2026-02-22
---

# Phase 2 Plan 01: Ingestion Building Blocks Summary

**Recursive tree-aware text chunker, Italian legal metadata extraction prompts with vocabulary injection, and pipeline data models for the ingestion pipeline**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-22T11:04:21Z
- **Completed:** 2026-02-22T11:07:27Z
- **Tasks:** 2
- **Files created:** 5

## Accomplishments
- DB migration adding `ingestion_status` (pending/processing/complete/failed) and `needs_review` columns with B-tree index for efficient filtering
- `DocumentPipeline` and `ChunkData` dataclasses that carry intermediate state between all pipeline stages
- Metadata extraction prompt builder that injects the full Italian legal vocabulary (doc_types, legal_areas, court_levels, party_roles, cross_reference_types) for consistent LLM terminology
- JSON schema for structured LLM output compatible with LiteLLM `response_format` for reliable metadata extraction
- Hand-rolled recursive text splitter with separator hierarchy (paragraphs -> lines -> sentences -> words), configurable overlap, and midpoint fallback
- Tree path builder via DFS with backtracking, and contextual embedding text builder that prepends metadata + tree path to every chunk

## Task Commits

Each task was committed atomically:

1. **Task 1: Create DB migration and pipeline data models** - `6dbc042` (feat)
2. **Task 2: Create LLM prompt templates and recursive text splitter** - `1d2e9df` (feat)

## Files Created/Modified
- `pageindex/db/migrations/002_ingestion_status.sql` - DDL adding ingestion_status TEXT and needs_review BOOLEAN columns with index
- `pageindex/ingestion/__init__.py` - Package init (re-exports deferred to Plan 03)
- `pageindex/ingestion/models.py` - DocumentPipeline and ChunkData dataclasses for pipeline state
- `pageindex/ingestion/prompts.py` - Metadata extraction prompt with vocabulary injection, description prompt, JSON schema, vocabulary loader with module-level cache
- `pageindex/ingestion/chunker.py` - chunk_leaf_nodes, recursive_split, build_tree_path, build_embedding_text

## Decisions Made
- Recursive splitter uses a separator hierarchy (`["\n\n", "\n", ". ", " "]`) matching the LangChain-inspired pattern from RESEARCH.md, with an additional midpoint fallback for text with no separators
- Vocabulary formatting helpers convert the nested YAML structure into readable prompt sections, preserving descriptions and examples for the LLM
- `ChunkData.metadata.sub_chunk_index` is `None` for single-chunk leaves and an integer for sub-chunks, providing clear distinction downstream
- `build_tree_path` uses iterative DFS with backtracking rather than a flat scan, correctly handling nested tree structures of arbitrary depth

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. The migration SQL must be applied to a Supabase instance before ingestion can run, but that is pre-existing setup from Phase 1.

## Next Phase Readiness
- All building blocks are ready for Plan 02 (per-document pipeline stages: tree indexing, metadata extraction, description generation, chunking, embedding, storage)
- The chunker's `chunk_leaf_nodes()` accepts a `count_tokens_fn` parameter, ready to wire up with `LLMProvider.count_tokens()`
- Prompt templates and JSON schema are ready for use with `litellm.completion(response_format=METADATA_JSON_SCHEMA)`
- DocumentPipeline dataclass carries state between all pipeline stages

## Self-Check: PASSED

- All 5 created files verified present on disk
- Commit `6dbc042` (Task 1) verified in git log
- Commit `1d2e9df` (Task 2) verified in git log

---
*Phase: 02-ingestion-pipeline*
*Completed: 2026-02-22*
