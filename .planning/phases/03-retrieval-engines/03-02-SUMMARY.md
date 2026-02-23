---
phase: 03-retrieval-engines
plan: 02
subsystem: retrieval
tags: [litellm, structured-output, supabase-postgrest, metadata-filtering, tenacity, json-schema]

# Dependency graph
requires:
  - phase: 03-retrieval-engines
    plan: 01
    provides: MetadataFilter dataclass, MetadataResult type, assign_confidence helper, retrieval config module
  - phase: 02-ingestion-pipeline
    provides: load_vocabulary() for Italian legal vocabulary injection
  - phase: 01-schema-llm
    provides: Supabase client singleton, documents table, LLM config
provides:
  - FILTER_JSON_SCHEMA for LiteLLM structured output with strict=True
  - _FILTER_FIELDS single source of truth preventing schema drift (Pitfall 3)
  - build_filter_system_prompt() with Italian legal vocabulary injection
  - build_retry_prompt() for validation failure recovery
  - generate_filters() LLM filter generation with retry-on-validation-failure
  - build_metadata_query() translating MetadataFilter to Supabase PostgREST chains
  - score_metadata_results() scoring documents by filter field match fraction
  - search_metadata() main entry point for metadata retrieval
affects: [03-04-tree-search, 04-strategy-orchestration]

# Tech tracking
tech-stack:
  added: []
  patterns: [single-source-of-truth-filter-fields, retry-with-feedback-on-validation-failure, postgrest-filter-chain-translation]

key-files:
  created:
    - pageindex/retrieval/prompts.py
    - pageindex/retrieval/metadata.py
  modified: []

key-decisions:
  - "_FILTER_FIELDS list as single source of truth for both FILTER_JSON_SCHEMA and system prompt -- prevents schema drift (Pitfall 3)"
  - "Used litellm.completion() directly (not provider.complete()) to pass response_format for structured JSON output"
  - "Tenacity retry on _llm_completion for API-level resilience, separate validation-level retry loop in generate_filters()"
  - "Parties field uses cast-to-text + ilike per party name for JSONB search (Pitfall 5 from RESEARCH.md)"

patterns-established:
  - "Dual-level retry: tenacity for network/rate-limit, loop for validation failures with LLM feedback"
  - "PostgREST filter chain builder: iterate non-None filter fields, apply typed filter methods"
  - "Score-as-fraction pattern: match_count / total_non_null_filters for normalized 0-1 scoring"

requirements-completed: [META-01, META-02, META-03]

# Metrics
duration: 3min
completed: 2026-02-23
---

# Phase 3 Plan 02: Metadata Retrieval Engine Summary

**LLM-powered natural language to structured JSON filter translation with Supabase PostgREST query execution, validation retry with feedback, and filter-fraction scoring**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-23T09:24:25Z
- **Completed:** 2026-02-23T09:27:05Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created filter prompt builder with Italian legal vocabulary injection from legal_vocabulary.yaml, producing a 4483-character system prompt with doc_types, legal_areas, and court_levels
- Built FILTER_JSON_SCHEMA with strict=True and all 8 filter fields as required nullable properties, derived from shared _FILTER_FIELDS definition
- Implemented full metadata retrieval pipeline: LLM filter generation with retry-on-validation-failure, PostgREST query chain translation, filter-fraction scoring, and threshold filtering
- Zero raw SQL throughout -- all database queries use Supabase PostgREST methods (ilike, gte, lte, overlaps, filter)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create filter prompt builder and JSON schema** - `7ddc537` (feat)
2. **Task 2: Create metadata retrieval engine** - `951bdaa` (feat)

## Files Created/Modified
- `pageindex/retrieval/prompts.py` - FILTER_JSON_SCHEMA, build_filter_system_prompt(), build_retry_prompt(), _FILTER_FIELDS single source of truth
- `pageindex/retrieval/metadata.py` - generate_filters(), build_metadata_query(), score_metadata_results(), search_metadata() entry point

## Decisions Made
- Used `_FILTER_FIELDS` list at module top as single source of truth shared between JSON schema and prompt builder, preventing Pitfall 3 (schema drift between prompt and validation)
- Used `litellm.completion()` directly (not `provider.complete()`) to pass `response_format` parameter for structured JSON output, same pattern as ingestion Stage 2
- Separated API-level retry (tenacity on `_llm_completion` for network errors) from validation-level retry (loop in `generate_filters` with feedback prompts)
- Parties JSONB search uses `filter("parties::text", "ilike", ...)` cast-to-text approach per Pitfall 5 from RESEARCH.md

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. Supabase environment variables (SUPABASE_URL, SUPABASE_KEY) must already be set from Phase 1.

## Next Phase Readiness
- Metadata retrieval engine ready for integration in Phase 4 strategy orchestration
- search_metadata() can be called standalone with any natural language query
- FILTER_JSON_SCHEMA and prompts available for testing and tuning
- Score-as-fraction pattern established for metadata engine confidence assignment

## Self-Check: PASSED

All 2 created files verified present. Both task commits (7ddc537, 951bdaa) verified in git log.

---
*Phase: 03-retrieval-engines*
*Completed: 2026-02-23*
