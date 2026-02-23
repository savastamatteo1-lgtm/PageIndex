# Phase 4: Strategy Orchestration - Context

**Gathered:** 2026-02-23
**Status:** Ready for planning

<domain>
## Phase Boundary

User-selectable retrieval strategy per query (`metadata`, `semantic`, `hybrid`, `auto`) with intelligent routing and hybrid fusion across metadata, semantic, and description engines. Includes `retrieval:` config section and tech debt fix for `updated_at` column guard bypass. Tree search remains a separate post-retrieval step, not part of the strategy orchestration.

</domain>

<decisions>
## Implementation Decisions

### Auto-detection logic
- Use LLM classification to determine query intent (structured vs conceptual vs mixed)
- Structured indicators: dates/date ranges, legal identifiers (ECLI, GU, law numbers), court/authority names, doc type keywords (sentenza, decreto, ordinanza, circolare)
- Mixed queries (structured + conceptual) always route to hybrid
- Pure structured queries use metadata-first with semantic fallback if results are few/empty
- Pure conceptual queries route to semantic-first

### Hybrid fusion behavior
- Reciprocal Rank Fusion (RRF) across three engines: metadata, semantic, and description search
- Configurable per-engine weights with default 1:1:1 (equal contribution)
- Same top-K fetch size from all engines before fusion
- When one engine returns zero results, return results from contributing engines but flag the gap in the response

### Result transparency
- Per-result engine attribution: each result includes which engine(s) contributed it
- Per-engine individual scores AND fused RRF score exposed on each result
- Auto mode reports both the strategy selected and the reasoning (e.g., "strategy: hybrid, reason: query contains date range and conceptual topic")

### Config & thresholds
- `retrieval:` section in config.yaml with tunable parameters
- Global minimum score cutoff to filter low-confidence results (regardless of engine)
- Default top-K: 10 results
- RRF constant (k): configurable with default 60
- Default strategy: `auto` when caller does not specify

### Claude's Discretion
- LLM prompt design for query intent classification
- Exact global minimum score threshold value
- Internal fetch size per engine before fusion (pre top-K)
- `updated_at` tech debt fix approach

</decisions>

<specifics>
## Specific Ideas

- Auto mode should feel intelligent — LLM classifies query intent rather than just pattern-matching
- Maximum transparency: results should expose full scoring breakdown for debugging and trust-building
- Hybrid includes description search as a lightweight third signal, not just metadata + semantic

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-strategy-orchestration*
*Context gathered: 2026-02-23*
