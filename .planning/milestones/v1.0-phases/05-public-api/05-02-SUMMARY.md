---
phase: 05-public-api
plan: 02
subsystem: api
tags: [facade-pattern, delegation, singleton-reset, public-api, pageindex-class]

# Dependency graph
requires:
  - phase: 05-public-api
    plan: 01
    provides: "PageIndexSettings, exception hierarchy, public return dataclasses"
  - phase: 04-strategy-orchestration
    provides: "Strategy dispatcher search() and SearchResponse with engine_gaps"
  - phase: 03-retrieval
    provides: "Semantic, metadata, tree_search engines and result types"
  - phase: 02-ingestion
    provides: "process_single_document pipeline and DocumentPipeline model"
provides:
  - "PageIndex class with 7 public methods: search, search_semantic, search_metadata, search_tree, ingest, retrieve, list_documents"
  - "Constructor-based subsystem wiring (DB client reset, LLM provider injection)"
  - "reset_client() function in db/client.py for singleton credential rotation"
affects: [05-03-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns: [facade-pattern, singleton-reset, env-var-propagation, lazy-import-delegation]

key-files:
  created: []
  modified:
    - pageindex/api.py
    - pageindex/db/client.py

key-decisions:
  - "Lazy imports inside methods to avoid circular dependencies and heavy import-time side effects"
  - "Empty dict for _build_ingestion_config since tree indexer uses its own ConfigLoader defaults"
  - "Text ingestion raises IngestionError with clear message -- deferred to future release"
  - "All search methods wrap errors in SearchError for uniform exception handling"

patterns-established:
  - "Facade pattern: PageIndex delegates to internal engines without wrapping their internals"
  - "Singleton reset pattern: reset_client() clears cached DB client for credential rotation"
  - "Constructor subsystem wiring: env vars + singleton reset before any downstream access"

requirements-completed: [FOUND-05]

# Metrics
duration: 2min
completed: 2026-02-23
---

# Phase 5 Plan 2: PageIndex Class Summary

**PageIndex facade class with 7 public methods delegating to proven retrieval, ingestion, and DB subsystems, plus DB client singleton reset for credential injection**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-23T13:04:53Z
- **Completed:** 2026-02-23T13:07:13Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- PageIndex class with search(), search_semantic(), search_metadata(), search_tree(), ingest(), retrieve(), list_documents()
- Constructor validates config via pydantic-settings and raises ConfigError on failure
- Subsystem singletons (DB client, LLM provider) wired from PageIndex settings in constructor
- DB client singleton supports reset via reset_client() for multi-instance credential scenarios

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement PageIndex class with all public methods** - `d22e055` (feat)
2. **Task 2: Wire DB client singleton to accept injected credentials** - `3bf7c34` (feat)

## Files Created/Modified
- `pageindex/api.py` - Added PageIndex class with 7 public methods, constructor, and subsystem wiring
- `pageindex/db/client.py` - Added reset_client() function for singleton credential rotation

## Decisions Made
- **Lazy imports in methods**: All delegation imports (retrieval engines, ingestion stages, DB functions) are inside method bodies to avoid circular dependencies and minimize import-time side effects. This matches the project's established pattern from utils.py (Phase 1 decision).
- **Empty ingestion config dict**: `_build_ingestion_config()` returns `{}` because the tree indexer uses its own `ConfigLoader` defaults. Non-tree parameters (metadata_pages, chunk sizes) are passed as explicit kwargs to `process_single_document()`.
- **Text ingestion deferred**: `ingest(text=...)` raises a clear `IngestionError` explaining the limitation and that it's planned. The underlying pipeline only supports file paths.
- **Uniform error wrapping**: All public methods catch exceptions and re-raise as the appropriate custom exception type (SearchError, IngestionError, ConfigError).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- PageIndex class is fully functional and importable from `pageindex.api`
- Ready for Plan 03 to wire package exports (`from pageindex import PageIndex`) and migrate run_pageindex.py
- All 7 public methods delegate to proven internal engines without re-implementing logic

## Self-Check: PASSED

- FOUND: pageindex/api.py
- FOUND: pageindex/db/client.py
- FOUND: commit d22e055 (Task 1)
- FOUND: commit 3bf7c34 (Task 2)

---
*Phase: 05-public-api*
*Completed: 2026-02-23*
