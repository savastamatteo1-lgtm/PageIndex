---
phase: 01-schema-and-llm-abstraction
plan: 02
subsystem: llm
tags: [litellm, gemini, embedding, provider-abstraction, config]

# Dependency graph
requires:
  - phase: none
    provides: none (first plan in wave 1)
provides:
  - LLMProvider class wrapping LiteLLM for completion/embedding
  - load_llm_config() function reading llm section from config.yaml
  - get_provider() singleton for easy access
  - llm_complete() and llm_embed() convenience functions in utils.py
  - Extended config.yaml with llm and supabase sections
  - litellm and supabase in requirements.txt
affects: [ingestion-pipeline, retrieval-engines, strategy-orchestration]

# Tech tracking
tech-stack:
  added: [litellm>=1.81.0, supabase>=2.28.0]
  patterns: [provider-prefix-model-naming, lazy-import-for-backward-compat, singleton-provider, config-section-extension]

key-files:
  created:
    - pageindex/llm/__init__.py
    - pageindex/llm/provider.py
    - pageindex/llm/config.py
  modified:
    - pageindex/config.yaml
    - pageindex/utils.py
    - requirements.txt

key-decisions:
  - "Kept existing Gemini_API/ChatGPT_API functions unchanged -- full migration deferred to avoid breaking tree-indexing flow"
  - "count_tokens delegates to LiteLLM with google-genai fallback for resilience"
  - "Lazy imports in utils.py to avoid circular dependencies between utils and llm package"
  - "litellm.drop_params = True set globally to prevent provider-specific param errors"

patterns-established:
  - "Provider prefix naming: all model names use provider/ prefix (e.g. gemini/gemini-2.0-flash)"
  - "Lazy import pattern: llm imports inside function bodies in utils.py to prevent circular deps"
  - "Config section extension: new features add YAML sections below existing keys"
  - "Singleton provider: get_provider() returns module-level LLMProvider instance"

requirements-completed: [FOUND-03]

# Metrics
duration: 3min
completed: 2026-02-22
---

# Phase 1 Plan 2: LLM Abstraction Summary

**LiteLLM provider-agnostic wrapper with complete/embed methods, config loader from config.yaml, and backward-compatible utils.py with new llm_complete/llm_embed entry points**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-22T07:58:18Z
- **Completed:** 2026-02-22T08:01:21Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Created pageindex/llm/ package with LLMProvider wrapping LiteLLM for all completion and embedding calls
- Extended config.yaml with llm and supabase sections while preserving existing PageIndex settings
- Added llm_complete() and llm_embed() as recommended entry points for new code in utils.py
- Verified full backward compatibility -- page_index.py and page_index_md.py imports work unchanged

## Task Commits

Each task was committed atomically:

1. **Task 1: Create LLM provider module and config loader** - `102c305` (feat)
2. **Task 2: Refactor utils.py for backward compatibility through LLM abstraction** - `82005da` (feat)

## Files Created/Modified
- `pageindex/llm/__init__.py` - Package init exporting LLMProvider, get_provider, load_llm_config
- `pageindex/llm/provider.py` - LiteLLM wrapper with complete/acomplete/embed/aembed/count_tokens methods
- `pageindex/llm/config.py` - Config loader reading llm section from config.yaml with sensible defaults
- `pageindex/config.yaml` - Extended with llm (completion_model, embedding_model, dimensions, temperature) and supabase sections
- `pageindex/utils.py` - Added module docstring, count_tokens delegation, llm_complete(), llm_embed()
- `requirements.txt` - Added litellm>=1.81.0 and supabase>=2.28.0

## Decisions Made
- Kept existing Gemini_API/ChatGPT_API functions unchanged in this phase. The Gemini_API_with_finish_reason function returns finish_reason metadata that LiteLLM does not expose the same way, and page_index.py depends on this for MAX_TOKENS retry logic. Full migration is a future concern.
- Used lazy imports (inside function bodies) in utils.py when referencing pageindex.llm to prevent circular dependency issues at module load time.
- Set litellm.drop_params = True globally in provider.py to prevent errors when passing provider-specific parameters across different backends.
- count_tokens uses LiteLLM as primary with automatic fallback to google-genai SDK, ensuring it works even if LLM config is not set up.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required

None - no external service configuration required. The LLM abstraction layer reads API keys from environment variables (GEMINI_API_KEY for Gemini, OPENAI_API_KEY for OpenAI, etc.) which are already managed via python-dotenv.

## Next Phase Readiness
- LLM abstraction layer complete -- all subsequent phases can use llm_complete() and llm_embed() for provider-agnostic calls
- Config system extended -- new features can add sections to config.yaml following the established pattern
- Backward compatibility verified -- existing tree-indexing code (page_index.py, page_index_md.py) works unchanged
- Phase 1 Plan 1 (database schema) is the other dependency for Phase 2

## Self-Check: PASSED

- All 7 files verified present on disk
- Commit `102c305` (Task 1) verified in git log
- Commit `82005da` (Task 2) verified in git log

---
*Phase: 01-schema-and-llm-abstraction*
*Completed: 2026-02-22*
