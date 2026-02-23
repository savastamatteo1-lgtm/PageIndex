---
phase: 06-public-api-wiring-cleanup
plan: 02
subsystem: api
tags: [ingestion, embedding, deprecation, settings-wiring]

# Dependency graph
requires:
  - phase: 06-01
    provides: "PageIndexSettings wired to retrieval and LLM subsystems"
  - phase: 02-03
    provides: "process_single_document orchestrator and stage_embed pipeline"
  - phase: 05-02
    provides: "PageIndex.ingest() facade method with ingestion settings"
provides:
  - "max_embedding_batch flows from PageIndexSettings to stage_embed() batch loop"
  - "additional_fields parameter wired through ingestion pipeline to DB storage"
  - "page_index_md.py deprecation docstring marking legacy status"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Parameter forwarding through orchestrator to stage functions"
    - "Module-level deprecation docstring with sphinx deprecated directive"

key-files:
  created: []
  modified:
    - "pageindex/ingestion/stages.py"
    - "pageindex/api.py"
    - "pageindex/page_index_md.py"

key-decisions:
  - "embed_batch_size defaults to _EMBED_BATCH_SIZE constant for backward compatibility"
  - "additional_fields stored via update_document() after insert_document() to reuse existing DB function"
  - "page_index_md.py preserved with deprecation docstring rather than deleted for backward compatibility"

patterns-established:
  - "Settings forwarding: PageIndexSettings -> PageIndex method -> orchestrator -> stage function"

requirements-completed: []

# Metrics
duration: 2min
completed: 2026-02-23
---

# Phase 6 Plan 02: Ingestion Settings Wiring & Legacy Deprecation Summary

**max_embedding_batch and additional_fields wired from PageIndexSettings through ingestion pipeline, plus deprecation docstring on legacy page_index_md.py**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-23T13:54:00Z
- **Completed:** 2026-02-23T13:56:24Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- max_embedding_batch now flows from IngestionSettings through PageIndex.ingest() to stage_embed() batch loop (closes ISSUE-09)
- additional_fields parameter wired from PageIndex.ingest() through process_single_document() to update_document() for JSONB storage
- page_index_md.py marked as internal legacy with deprecation docstring directing users to PageIndex class

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire max_embedding_batch and additional_fields to ingestion pipeline** - `e87d7b1` (feat)
2. **Task 2: Add deprecation docstring to page_index_md.py** - `28bb05c` (chore)

## Files Created/Modified
- `pageindex/ingestion/stages.py` - Added embed_batch_size param to stage_embed() and process_single_document(), added additional_fields param with update_document() storage
- `pageindex/api.py` - Threaded max_embedding_batch and additional_fields from PageIndex.ingest() to process_single_document()
- `pageindex/page_index_md.py` - Added module-level deprecation docstring marking as internal legacy

## Decisions Made
- embed_batch_size parameter defaults to the existing _EMBED_BATCH_SIZE constant (250) so all existing callers continue to work unchanged
- additional_fields stored via update_document() call after insert_document() rather than passing to insert_document() -- reuses existing DB function and keeps the insert call clean
- page_index_md.py preserved (not deleted) for backward compatibility with run_pageindex.py and external users, per RESEARCH.md Open Question 2

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 7 tech debt items from the v1.0 milestone audit are now addressed across Plans 01 and 02
- Phase 6 (Public API Wiring & Cleanup) is complete
- All PageIndexSettings flow through to their respective subsystems
- The codebase is ready for v1.0 milestone

## Self-Check: PASSED

All files verified present. All commits verified in git log.

---
*Phase: 06-public-api-wiring-cleanup*
*Completed: 2026-02-23*
