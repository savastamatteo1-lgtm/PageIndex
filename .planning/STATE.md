# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-22)

**Core value:** Given a legal query, find the right documents from a large corpus and extract the precise relevant sections -- combining structured metadata filtering with semantic understanding and reasoning-based retrieval.
**Current focus:** Phase 3: Retrieval Engines

## Current Position

Phase: 3 of 5 (Retrieval Engines)
Plan: 3 of 4 in current phase
Status: Executing Phase 3 plans
Last activity: 2026-02-23 -- Completed 03-03 (Semantic & Description Engines)

Progress: [███████░░░] 75% (Phase 3: 3/4 plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 8
- Average duration: 3min
- Total execution time: 21min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 2 | 6min | 3min |
| 2 | 3 | 8min | 3min |
| 3 | 3 | 7min | 2min |

**Recent Trend:**
- Last 5 plans: 02-02 (3min), 02-03 (2min), 03-01 (3min), 03-02 (2min), 03-03 (2min)
- Trend: Consistent

*Updated after each plan completion*
| Phase 01 P01 | 3min | 2 tasks | 7 files |
| Phase 02 P01 | 3min | 2 tasks | 5 files |
| Phase 02 P02 | 3min | 2 tasks | 4 files |
| Phase 02 P03 | 2min | 2 tasks | 3 files |
| Phase 03 P01 | 3min | 2 tasks | 4 files |
| Phase 03 P02 | 2min | 2 tasks | 3 files |
| Phase 03 P03 | 2min | 2 tasks | 2 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: 5-phase structure derived from 19 requirements across 6 categories
- [Roadmap]: Research recommends LiteLLM for LLM abstraction, Supabase hybrid schema, read-only DB role for SQL safety
- [01-01]: Trees use upsert on doc_id conflict to support re-indexing without manual deletion
- [01-01]: Singleton Supabase client via get_client() -- all DB access goes through pageindex.db.client
- [01-01]: Open text taxonomy with no CHECK/ENUM constraints -- conventions documented in legal_vocabulary.yaml
- [01-02]: Kept existing Gemini_API/ChatGPT_API functions unchanged -- full migration deferred to avoid breaking tree-indexing flow
- [01-02]: count_tokens delegates to LiteLLM with google-genai fallback for resilience
- [01-02]: Lazy imports in utils.py to avoid circular dependencies between utils and llm package
- [01-02]: litellm.drop_params = True set globally to prevent provider-specific param errors
- [02-01]: Recursive splitter uses separator hierarchy (paragraphs > lines > sentences > words) with midpoint fallback
- [02-01]: Vocabulary formatting helpers convert YAML structure to readable prompt sections for LLM injection
- [02-01]: build_tree_path uses DFS with backtracking to construct human-readable node paths
- [02-01]: Module-level caching for load_vocabulary() to avoid repeated disk reads
- [02-02]: Used litellm.completion() directly for metadata extraction to pass response_format for structured JSON
- [02-02]: Embedding text truncation removes words from chunk content end, preserving metadata prefix
- [02-02]: Tree text stripping via deep-copy + recursive key removal before DB storage
- [02-02]: Tenacity retry with exponential backoff (min=1, max=30, 3 attempts) for all LLM/embed calls
- [02-03]: Config override chain: hardcoded defaults -> config.yaml -> explicit function parameters (None-check pattern)
- [02-03]: Rollback looks up document by name after failure rather than tracking doc_id through the call
- [02-03]: ingest_errors.jsonl in append mode so consecutive runs accumulate error history
- [03-01]: Stdlib dataclasses (not pydantic) for retrieval result types -- lightweight, zero dependencies
- [03-01]: Per-engine confidence thresholds with conservative defaults since each engine has different score distributions
- [03-01]: MetadataFilter.from_dict() silently ignores unknown keys and treats None as unset for LLM output resilience
- [03-02]: _FILTER_FIELDS list as single source of truth for both FILTER_JSON_SCHEMA and system prompt -- prevents schema drift (Pitfall 3)
- [03-02]: Used litellm.completion() directly (not provider.complete()) to pass response_format for structured JSON output
- [03-02]: Dual-level retry: tenacity for network/rate-limit errors, validation-loop with LLM feedback for schema failures
- [03-02]: Parties JSONB search uses cast-to-text + ilike per party name (Pitfall 5 from RESEARCH.md)
- [03-03]: embed_query() in semantic.py is standalone and importable by description.py for shared embedding reuse
- [03-03]: DocScore uses REQUIREMENTS.md canonical formula: (1/sqrt(N+1)) * sum(ChunkScore(n)) -- resolves STATE.md blocker
- [03-03]: Chunk multiplier 5x top-K for match_chunks to capture enough document coverage before aggregation
- [03-03]: Backfill uses batch_size=250 with per-document try/except matching ingestion resilience patterns

### Pending Todos

None yet.

### Blockers/Concerns

- [Research]: DocScore aggregation formula inconsistency -- RESOLVED in 03-03: REQUIREMENTS.md formula is canonical
- [Research]: Italian ECLI extraction accuracy unknown -- assess with pilot during Phase 2
- [Research]: Supabase hosted pgvector version may not be 0.8.x -- verify before Phase 3

## Session Continuity

Last session: 2026-02-23
Stopped at: Completed 03-03-PLAN.md
Resume file: .planning/phases/03-retrieval-engines/03-03-SUMMARY.md
