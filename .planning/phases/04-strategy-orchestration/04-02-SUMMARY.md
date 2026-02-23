---
phase: 04-strategy-orchestration
plan: 02
subsystem: retrieval
tags: [rrf, fusion, strategy-dispatcher, query-classification, litellm, hybrid-search]

# Dependency graph
requires:
  - phase: 04-strategy-orchestration
    provides: "FusedResult, SearchResponse, QueryClassification dataclasses in models.py; RRF/strategy config in config.py"
  - phase: 03-retrieval-engines
    provides: "search_metadata, search_semantic, search_description, embed_query engine functions; RetrievalResult subclasses"
provides:
  - "retrieval: search() unified entry point with 4 strategies (metadata, semantic, hybrid, auto)"
  - "retrieval: classify_query() LLM intent classification with hybrid fallback"
  - "retrieval: reciprocal_rank_fusion() weighted RRF across ranked lists"
  - "retrieval: CLASSIFICATION_SYSTEM_PROMPT and CLASSIFICATION_SCHEMA for query intent"
affects: [05-integration-testing]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Strategy dispatcher with per-strategy runners", "LLM classification with safe fallback to hybrid", "RRF fusion with configurable k and weights", "Single query embedding shared across engines"]

key-files:
  created:
    - "pageindex/retrieval/strategy.py"
  modified:
    - "pageindex/retrieval/prompts.py"
    - "pageindex/retrieval/__init__.py"
    - "pageindex/retrieval/config.py"

key-decisions:
  - "Classification failure defaults to hybrid strategy -- safest fallback covering both structured and conceptual"
  - "Query embedding computed once in _run_hybrid and passed to both semantic and description engines (Pitfall 3 avoidance)"
  - "Hybrid confidence thresholds set to high=0.03, medium=0.015 reflecting small RRF score range (~0.01-0.05)"

patterns-established:
  - "Strategy dispatch via _run_*() private functions returning (results, engine_gaps) tuples"
  - "classify_query() wraps all LLM errors in try/except with fallback -- never propagates classification failures"
  - "RRF accumulates per-doc scores from all engines, preserves metadata from first contributing engine"

requirements-completed: [STRAT-01, STRAT-02, STRAT-03]

# Metrics
duration: 3min
completed: 2026-02-23
---

# Phase 4 Plan 02: Strategy Dispatcher Summary

**Strategy dispatcher with RRF fusion across 3 engines, LLM query classification, and search() unified entry point supporting metadata/semantic/hybrid/auto strategies**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-23T11:54:00Z
- **Completed:** 2026-02-23T11:56:39Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created strategy.py with search() entry point that dispatches to metadata, semantic, or hybrid strategies based on user selection or LLM auto-classification
- Implemented weighted Reciprocal Rank Fusion (RRF) producing FusedResult objects with engine attribution (contributing_engines, engine_scores) and confidence labels
- Added CLASSIFICATION_SYSTEM_PROMPT with Italian legal structured indicators (ECLI, GU, sentenza, decreto, etc.) and CLASSIFICATION_SCHEMA for LLM structured output
- Hybrid mode computes query embedding once and shares it between semantic and description engines (Pitfall 3 avoidance)
- Engine gaps tracked and exposed in SearchResponse when any engine returns zero results
- Classification failure gracefully defaults to hybrid with explanatory reasoning (Pitfall 5 avoidance)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add classification prompt and JSON schema to prompts.py** - `9cca995` (feat)
2. **Task 2: Create strategy dispatcher with RRF fusion and auto-routing** - `fce34bf` (feat)

**Plan metadata:** (pending final commit)

## Files Created/Modified
- `pageindex/retrieval/strategy.py` - Strategy dispatcher: search(), classify_query(), reciprocal_rank_fusion(), _run_metadata_first(), _run_semantic_first(), _run_hybrid()
- `pageindex/retrieval/prompts.py` - Added CLASSIFICATION_SYSTEM_PROMPT and CLASSIFICATION_SCHEMA for query intent classification
- `pageindex/retrieval/__init__.py` - Re-exports search(), FusedResult, SearchResponse, QueryClassification
- `pageindex/retrieval/config.py` - Added hybrid confidence thresholds (high: 0.03, medium: 0.015)

## Decisions Made
- Classification failure defaults to hybrid strategy -- safest fallback that covers both structured and conceptual, avoiding broken auto mode (RESEARCH Pitfall 5)
- Query embedding computed once in _run_hybrid() and passed to both search_semantic() and search_description() via query_embedding kwarg -- both engines already support this parameter from Phase 3
- Hybrid confidence thresholds set to high=0.03, medium=0.015 reflecting the small RRF score range (~0.01-0.05); tunable via config.yaml

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added hybrid confidence thresholds to config.py**
- **Found during:** Task 2
- **Issue:** Plan specified adding "hybrid" entry to CONFIDENCE_THRESHOLDS but this was naturally part of Task 2's RRF implementation requiring confidence labels for fused results
- **Fix:** Added `"hybrid": {"high": 0.03, "medium": 0.015}` to CONFIDENCE_THRESHOLDS dict in config.py
- **Files modified:** pageindex/retrieval/config.py
- **Verification:** assign_confidence() correctly labels RRF fused scores
- **Committed in:** fce34bf (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Essential for correctness -- hybrid RRF results need confidence labels. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 4 is now complete: all strategy orchestration infrastructure and dispatcher logic is in place
- search() is the unified entry point for all retrieval, importable from pageindex.retrieval
- Ready for Phase 5: integration testing can verify end-to-end search across all 4 strategies
- No blockers

## Self-Check: PASSED

All 4 modified/created files exist. Both task commits (9cca995, fce34bf) verified in git log. SUMMARY.md created.

---
*Phase: 04-strategy-orchestration*
*Completed: 2026-02-23*
