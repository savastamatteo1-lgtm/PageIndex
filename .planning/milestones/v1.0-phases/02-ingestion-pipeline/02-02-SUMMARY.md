---
phase: 02-ingestion-pipeline
plan: 02
subsystem: ingestion
tags: [pipeline-stages, litellm-structured-output, tenacity-retry, tree-indexing, metadata-extraction, embedding-batching, contextual-embedding, supabase-storage]

# Dependency graph
requires:
  - phase: 02-ingestion-pipeline
    plan: 01
    provides: "DocumentPipeline/ChunkData models, chunker, prompts, JSON schema, vocabulary loader"
  - phase: 01-schema-and-llm-abstraction
    provides: "page_index_main, LLMProvider, DB layer (documents/chunks/trees), config.yaml"
provides:
  - "6 sequential per-document pipeline stages in stages.py"
  - "process_single_document orchestrator composing all stages"
  - "update_document() and delete_document() in DB documents module"
  - "Extended _METADATA_COLUMNS with ingestion_status and needs_review"
affects: [02-03, retrieval-engines, batch-orchestration]

# Tech tracking
tech-stack:
  added: [tenacity]
  patterns: [tenacity-retry-exponential-backoff, litellm-structured-json-output, embedding-batch-250, tree-text-stripping]

key-files:
  created:
    - pageindex/ingestion/stages.py
  modified:
    - pageindex/db/documents.py
    - pageindex/db/__init__.py
    - requirements.txt

key-decisions:
  - "Used litellm.completion() directly for metadata extraction (not provider.complete()) to pass response_format for structured JSON"
  - "METADATA_JSON_SCHEMA already wraps the full response_format structure -- used directly instead of double-nesting"
  - "Embedding text truncation removes words from chunk content end (preserves metadata prefix intact)"
  - "Tree text stripping via deep-copy + recursive key removal before DB storage"

patterns-established:
  - "Tenacity retry: @retry(wait=wait_random_exponential(min=1,max=30), stop=stop_after_attempt(3)) for all LLM/embed calls"
  - "Pipeline stage pattern: each stage mutates DocumentPipeline in-place, no return values"
  - "Embedding batching: split into groups of 250 for Gemini API limits"
  - "Token validation: check embedding text against 2048-token limit before API call"

requirements-completed: [FOUND-04, SEM-01, ENRICH-01, ENRICH-02]

# Metrics
duration: 3min
completed: 2026-02-22
---

# Phase 2 Plan 02: Per-Document Pipeline Stages Summary

**6-stage document pipeline (tree index, metadata extraction, description, chunking, embedding, storage) with tenacity retry, structured JSON output, and DB update/delete helpers**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-22T11:11:20Z
- **Completed:** 2026-02-22T11:14:41Z
- **Tasks:** 2
- **Files created:** 1
- **Files modified:** 3

## Accomplishments
- All 6 per-document pipeline stages implemented in `stages.py`: tree indexing (forces node_id/text/summary), metadata extraction (structured JSON via litellm response_format), description generation (separate LLM call), chunking (tree-aware via chunk_leaf_nodes), embedding (250-batch with 2048-token validation), and storage (tree text stripped, chunks with embeddings)
- `process_single_document` orchestrator that inserts document row with status=processing, runs all 6 stages sequentially, and returns the completed DocumentPipeline
- `update_document()` with column filtering through `_METADATA_COLUMNS` and automatic `updated_at` timestamp, `delete_document()` leveraging ON DELETE CASCADE
- Extended `_METADATA_COLUMNS` set to include `ingestion_status` and `needs_review` for pipeline state tracking

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement per-document pipeline stages** - `5069401` (feat)
2. **Task 2: Extend DB documents module with update and delete helpers** - `2656987` (feat)

## Files Created/Modified
- `pageindex/ingestion/stages.py` - All 6 pipeline stages + process_single_document orchestrator + _strip_text_from_tree helper
- `pageindex/db/documents.py` - Added update_document(), delete_document(), extended _METADATA_COLUMNS with ingestion_status/needs_review
- `pageindex/db/__init__.py` - Re-exports update_document and delete_document
- `requirements.txt` - Added tenacity>=8.2.0

## Decisions Made
- Used `litellm.completion()` directly for metadata extraction instead of `provider.complete()` because the latter does not support `response_format` parameter for structured JSON output
- `METADATA_JSON_SCHEMA` from prompts.py already contains the full `response_format` structure (type + json_schema wrapper), so it is passed directly rather than double-nested as the plan suggested -- this is a correctness fix (Rule 1)
- Embedding text truncation strategy: when text exceeds 2048 tokens, words are removed from the end of chunk content while preserving the metadata prefix intact, since the metadata prefix is critical for contextual retrieval
- Tree text stripping uses deep-copy + recursive removal of `text` keys to avoid mutating the pipeline's tree_json in memory

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed METADATA_JSON_SCHEMA double-nesting**
- **Found during:** Task 1 (stage_extract_metadata implementation)
- **Issue:** Plan instructed `response_format={"type": "json_schema", "json_schema": METADATA_JSON_SCHEMA}` but METADATA_JSON_SCHEMA already IS the full response_format dict (contains both "type" and "json_schema" keys). Double-nesting would cause a malformed request.
- **Fix:** Used `response_format=METADATA_JSON_SCHEMA` directly
- **Files modified:** pageindex/ingestion/stages.py
- **Verification:** Import succeeds without error
- **Committed in:** 5069401 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential correctness fix. The plan's instruction would have produced a malformed API call. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no new external service configuration required. Tenacity is a pure Python library with no external dependencies.

## Next Phase Readiness
- All 6 pipeline stages ready for Plan 03 (batch orchestrator with concurrency, error handling, and rollback)
- `process_single_document` is the entry point that Plan 03's batch orchestrator will call for each PDF
- `delete_document()` is available for rollback logic in the batch orchestrator
- `update_document()` enables status tracking (processing -> complete/failed) from the orchestrator

## Self-Check: PASSED

- File `pageindex/ingestion/stages.py` verified present on disk
- File `pageindex/db/documents.py` verified modified with update_document and delete_document
- File `pageindex/db/__init__.py` verified modified with new exports
- File `requirements.txt` verified contains tenacity
- Commit `5069401` (Task 1) verified in git log
- Commit `2656987` (Task 2) verified in git log

---
*Phase: 02-ingestion-pipeline*
*Completed: 2026-02-22*
