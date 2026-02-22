---
phase: 02-ingestion-pipeline
plan: 03
subsystem: ingestion
tags: [batch-orchestration, threadpoolexecutor, rollback, idempotent-resume, ingest-errors-jsonl, config-loading, dual-error-tracking]

# Dependency graph
requires:
  - phase: 02-ingestion-pipeline
    plan: 02
    provides: "process_single_document orchestrator, 6 pipeline stages, delete_document for rollback, get_document_by_name for skip check"
  - phase: 02-ingestion-pipeline
    plan: 01
    provides: "DocumentPipeline/ChunkData models, chunker, prompts"
  - phase: 01-schema-and-llm-abstraction
    provides: "LLMProvider singleton via get_provider(), DB layer, config.yaml"
provides:
  - "ingest() batch entry point with ThreadPoolExecutor concurrency"
  - "Per-document rollback via _process_with_rollback() + delete_document CASCADE"
  - "Dual error tracking: DB ingestion_status + local ingest_errors.jsonl"
  - "load_ingestion_config() reading ingestion section from config.yaml"
  - "Package re-exports: from pageindex.ingestion import ingest"
  - "config.yaml ingestion section with pipeline defaults"
affects: [retrieval-engines, public-api, batch-operations]

# Tech tracking
tech-stack:
  added: []
  patterns: [threadpoolexecutor-batch, rollback-on-failure, config-override-chain, dual-error-tracking]

key-files:
  created:
    - pageindex/ingestion/pipeline.py
  modified:
    - pageindex/ingestion/__init__.py
    - pageindex/config.yaml

key-decisions:
  - "Function parameters override config.yaml defaults via None-check pattern (explicit arg wins, else config.yaml, else hardcoded default)"
  - "Rollback looks up document by name after failure rather than tracking doc_id through the call -- simpler and handles cases where insert_document itself fails"
  - "ingest_errors.jsonl written in append mode so consecutive runs accumulate in the same file"

patterns-established:
  - "Config override chain: hardcoded defaults -> config.yaml -> function parameters"
  - "Batch processing: ThreadPoolExecutor with as_completed for progress tracking"
  - "Rollback pattern: try/except with get_document_by_name + delete_document for cleanup"
  - "Dual error tracking: DB column for queryable status + local JSONL for batch analysis"

requirements-completed: [FOUND-04]

# Metrics
duration: 2min
completed: 2026-02-22
---

# Phase 2 Plan 03: Batch Orchestration Summary

**Batch ingest() entry point with ThreadPoolExecutor concurrency, per-document rollback via CASCADE delete, idempotent resume skipping completed documents, and dual error tracking (DB ingestion_status + ingest_errors.jsonl)**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-22T11:17:55Z
- **Completed:** 2026-02-22T11:19:45Z
- **Tasks:** 2
- **Files created:** 1
- **Files modified:** 2

## Accomplishments
- `ingest(directory)` function that discovers PDFs, skips already-ingested documents (status=complete), processes remaining with configurable ThreadPoolExecutor concurrency, and returns a structured summary dict
- Per-document rollback via `_process_with_rollback()` that deletes partial data on failure using `delete_document()` with ON DELETE CASCADE, ensuring no partial state in the database
- Dual error tracking: DB `ingestion_status` column for queryable state + local `ingest_errors.jsonl` appended per batch for offline analysis
- `load_ingestion_config()` reading the new `ingestion` section from config.yaml with sensible defaults, following the same pattern as `load_llm_config()`
- Package `__init__.py` re-exports `ingest`, `DocumentPipeline`, `ChunkData`, and `process_single_document` for clean public API

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement batch orchestration with ingest() entry point** - `6c229d9` (feat)
2. **Task 2: Wire up package exports and ingestion config** - `d6e11e3` (feat)

## Files Created/Modified
- `pageindex/ingestion/pipeline.py` - Batch orchestrator: ingest(), _process_with_rollback(), load_ingestion_config()
- `pageindex/ingestion/__init__.py` - Re-exports ingest, DocumentPipeline, ChunkData, process_single_document
- `pageindex/config.yaml` - Added ingestion section with metadata_pages, chunk_max_tokens, chunk_overlap, max_workers, max_embedding_batch

## Decisions Made
- Function parameters use None defaults and override config.yaml values only when explicitly provided -- this gives a clean config override chain (hardcoded -> config.yaml -> explicit function arg)
- Rollback looks up the document by name after failure rather than threading doc_id through the call chain -- this is simpler and handles the case where `insert_document()` itself fails (no doc_id to track)
- `ingest_errors.jsonl` uses append mode so multiple batch runs against the same directory accumulate error history in a single file

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. All dependencies (ThreadPoolExecutor, json, logging, pathlib) are Python stdlib.

## Next Phase Readiness
- Phase 2 ingestion pipeline is now complete: all 3 plans delivered
- `from pageindex.ingestion import ingest` is the primary entry point for batch processing
- Ready for Phase 3 (Retrieval Engines) which will query the data stored by this pipeline
- The ingestion pipeline produces documents with metadata, tree structures, and embedded chunks in Supabase -- all ready for metadata search, semantic search, tree search, and description search

## Self-Check: PASSED

- File `pageindex/ingestion/pipeline.py` verified present on disk
- File `pageindex/ingestion/__init__.py` verified modified with re-exports
- File `pageindex/config.yaml` verified contains ingestion section
- Commit `6c229d9` (Task 1) verified in git log
- Commit `d6e11e3` (Task 2) verified in git log

---
*Phase: 02-ingestion-pipeline*
*Completed: 2026-02-22*
