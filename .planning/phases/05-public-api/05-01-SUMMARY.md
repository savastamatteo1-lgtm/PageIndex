---
phase: 05-public-api
plan: 01
subsystem: api
tags: [pydantic-settings, config, exceptions, dataclasses, typed-api]

# Dependency graph
requires:
  - phase: 03-retrieval
    provides: "Retrieval result types (RetrievalResult, FusedResult, SearchResponse) and config defaults"
  - phase: 04-strategy-orchestration
    provides: "Strategy dispatcher SearchResponse and engine_gaps pattern"
provides:
  - "PageIndexSettings pydantic-settings model with layered config (kwargs > env > YAML)"
  - "Custom exception hierarchy: PageIndexError, ConfigError, IngestionError, SearchError"
  - "Public return types: SearchResponse, IngestionResult, DocumentInfo dataclasses"
  - "pydantic-settings dependency in requirements.txt"
affects: [05-02-PLAN, 05-03-PLAN]

# Tech tracking
tech-stack:
  added: [pydantic-settings>=2.7.0]
  patterns: [pydantic-settings-yaml-source, custom-source-priority, nested-env-delimiter, model-validator-env-fallback]

key-files:
  created:
    - pageindex/exceptions.py
    - pageindex/api.py
  modified:
    - requirements.txt

key-decisions:
  - "SupabaseSettings uses extra=ignore to discard YAML url_env/key_env indirection fields"
  - "model_validator(mode=before) accepts flat SUPABASE_URL/SUPABASE_KEY env vars as fallback"
  - "field_validator rejects empty strings on required Supabase url/key fields"
  - "RetrievalSettings uses extra=ignore to handle extra YAML fields (thresholds etc.) not in settings model"

patterns-established:
  - "Layered config: constructor kwargs > PAGEINDEX_ env vars > config.yaml > field defaults"
  - "Public return types use stdlib dataclasses (not pydantic) per Phase 3 convention"
  - "Exception hierarchy: PageIndexError base with ConfigError/IngestionError/SearchError subtypes"

requirements-completed: [FOUND-05]

# Metrics
duration: 5min
completed: 2026-02-23
---

# Phase 5 Plan 1: Foundation Types Summary

**pydantic-settings PageIndexSettings with YAML/env/kwargs layered config, custom exception hierarchy, and public SearchResponse/IngestionResult/DocumentInfo dataclasses**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-23T12:56:41Z
- **Completed:** 2026-02-23T13:01:45Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- PageIndexSettings with 4 nested sub-models (LLM, Supabase, Ingestion, Retrieval) replacing scattered load_*_config() functions
- Custom priority chain via settings_customise_sources: init kwargs > env vars > YAML config > defaults
- Flat SUPABASE_URL/SUPABASE_KEY env var fallback via model_validator for ergonomic config
- Three public return dataclasses (SearchResponse, IngestionResult, DocumentInfo) distinct from internal types

## Task Commits

Each task was committed atomically:

1. **Task 1: Create exception hierarchy and pydantic-settings model** - `6d10b68` (feat)
2. **Task 2: Create public return types** - `4dd45cc` (feat)

## Files Created/Modified
- `pageindex/exceptions.py` - Custom exception hierarchy (PageIndexError, ConfigError, IngestionError, SearchError)
- `pageindex/api.py` - PageIndexSettings model + SearchResponse, IngestionResult, DocumentInfo dataclasses
- `requirements.txt` - Added pydantic-settings>=2.7.0

## Decisions Made
- **SupabaseSettings extra="ignore"**: The YAML config.yaml has supabase.url_env and supabase.key_env (env var names, not actual values). Using extra="ignore" silently discards these while actual values come from env vars or kwargs.
- **Empty-string rejection**: The project .env file has SUPABASE_URL= (empty). Added field_validator to reject empty strings on required fields so empty env vars correctly trigger validation errors.
- **RetrievalSettings extra="ignore"**: The YAML retrieval section contains additional fields (confidence_thresholds, docscore_min_threshold, etc.) not modeled in the settings since they're loaded by existing config.py. Using extra="ignore" prevents validation errors from these extra YAML keys.
- **model_validator for flat env vars**: Checks os.environ for SUPABASE_URL/SUPABASE_KEY as fallback, only using non-empty values. This lets users use the standard Supabase env var names instead of PAGEINDEX_SUPABASE__URL.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Rejected empty-string Supabase env vars**
- **Found during:** Task 1 (PageIndexSettings verification)
- **Issue:** The project .env file sets SUPABASE_URL= and SUPABASE_KEY= (empty strings). python-dotenv loads these at import time, so os.environ["SUPABASE_URL"] exists but is empty. Without validation, SupabaseSettings(url='', key='') would succeed silently.
- **Fix:** Added field_validator("url", "key") that rejects empty/whitespace-only strings. Also updated model_validator to strip and ignore empty env var values.
- **Files modified:** pageindex/api.py
- **Verification:** PageIndexSettings() with no real env vars correctly raises ValidationError mentioning supabase fields
- **Committed in:** 6d10b68 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential for correctness -- empty env vars would silently create broken config. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All foundation types ready for Plan 02 (PageIndex class facade) to import and use
- PageIndexSettings provides the config object that PageIndex.__init__ will construct
- Exception hierarchy ready for wrapping pydantic ValidationError as ConfigError
- Return types ready for PageIndex.search() and PageIndex.ingest() to return

## Self-Check: PASSED

- FOUND: pageindex/exceptions.py
- FOUND: pageindex/api.py
- FOUND: 05-01-SUMMARY.md
- FOUND: commit 6d10b68 (Task 1)
- FOUND: commit 4dd45cc (Task 2)

---
*Phase: 05-public-api*
*Completed: 2026-02-23*
