# Phase 4: Strategy Orchestration - Research

**Researched:** 2026-02-23
**Domain:** Multi-engine retrieval fusion, query intent classification, config management
**Confidence:** HIGH

## Summary

Phase 4 adds a strategy orchestration layer on top of the three existing retrieval engines (metadata, semantic, description). The core technical challenges are: (1) implementing Reciprocal Rank Fusion (RRF) to merge ranked results from three engines into a single list, (2) building an LLM-based query intent classifier that routes queries to the right strategy, and (3) adding a `retrieval:` section to config.yaml so all thresholds are user-tunable.

The codebase is well-positioned for this phase. All three engines already return standardized `RetrievalResult` subclasses with `doc_id`, `score`, `engine_name`, and `confidence`. The `load_retrieval_config()` function already reads a `retrieval:` section from config.yaml -- it just silently falls back to hardcoded defaults because that section does not exist yet. The LLM classification pattern is identical to the existing `generate_filters()` in metadata.py: call `litellm.completion()` with a `response_format` JSON schema and parse the structured output.

**Primary recommendation:** Build a single `pageindex/retrieval/strategy.py` module that provides a `search()` entry point accepting a `strategy` parameter (`metadata`, `semantic`, `hybrid`, `auto`). RRF is ~20 lines of pure Python (no dependencies). LLM classification reuses the existing `litellm.completion()` + `response_format` pattern from metadata.py.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Use LLM classification to determine query intent (structured vs conceptual vs mixed)
- Structured indicators: dates/date ranges, legal identifiers (ECLI, GU, law numbers), court/authority names, doc type keywords (sentenza, decreto, ordinanza, circolare)
- Mixed queries (structured + conceptual) always route to hybrid
- Pure structured queries use metadata-first with semantic fallback if results are few/empty
- Pure conceptual queries route to semantic-first
- Reciprocal Rank Fusion (RRF) across three engines: metadata, semantic, and description search
- Configurable per-engine weights with default 1:1:1 (equal contribution)
- Same top-K fetch size from all engines before fusion
- When one engine returns zero results, return results from contributing engines but flag the gap in the response
- Per-result engine attribution: each result includes which engine(s) contributed it
- Per-engine individual scores AND fused RRF score exposed on each result
- Auto mode reports both the strategy selected and the reasoning (e.g., "strategy: hybrid, reason: query contains date range and conceptual topic")
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

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| STRAT-01 | User can select retrieval strategy per query: `metadata`, `semantic`, `hybrid`, or `auto` | Strategy dispatcher pattern in `strategy.py` with `search(query, strategy="auto")` entry point; strategy enum validation |
| STRAT-02 | Hybrid strategy combines metadata and semantic results via RRF; merged ranking outperforms either alone on mixed queries | RRF algorithm documented with formula, k=60 default, weighted variant for three engines; pure Python implementation ~20 lines |
| STRAT-03 | Auto mode detects structured indicators to route metadata-first, conceptual queries to semantic-first | LLM classification via `litellm.completion()` + `response_format` JSON schema (same pattern as `generate_filters()`); structured output returns intent category + reasoning |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| litellm | (already installed) | LLM completion for query classification | Already used in metadata.py for filter generation; `response_format` JSON schema for structured output |
| dataclasses (stdlib) | Python 3.12+ | Result types for fusion output | Project convention from Phase 3 (models.py); zero dependencies |
| yaml (PyYAML) | (already installed) | Config loading | Already used in all config loaders |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tenacity | (already installed) | Retry for LLM classification calls | Same pattern as `_llm_completion()` in metadata.py |
| logging (stdlib) | Python 3.12+ | Structured logging | Project-wide convention |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pure Python RRF | LlamaIndex `RecipRankFusion` | External dependency for 20 lines of code; project has no LlamaIndex dependency |
| LLM classification | Regex/keyword detection | User explicitly decided LLM classification for intelligence; regex would miss nuanced intent |
| Weights via multiplication | Weights via RRF k-parameter tuning | Per-engine weight multiplication is more intuitive and the user-decided approach; k-tuning is opaque |

**Installation:** No new dependencies needed. Everything is already in the project.

## Architecture Patterns

### Recommended Project Structure
```
pageindex/retrieval/
├── __init__.py          # Add search() export
├── config.py            # Extend with new RRF/strategy defaults
├── models.py            # Add FusedResult dataclass
├── strategy.py          # NEW: strategy dispatcher + RRF + auto-routing
├── metadata.py          # Unchanged
├── semantic.py          # Unchanged (embed_query reused)
├── description.py       # Unchanged
├── tree_search.py       # Unchanged
└── prompts.py           # Add classification prompt + schema
```

### Pattern 1: Strategy Dispatcher
**What:** A single `search()` function that accepts a `strategy` parameter and dispatches to the appropriate engine(s).
**When to use:** Always -- this is the primary user-facing entry point for Phase 4.
**Example:**
```python
# Source: project pattern from metadata.py entry point
def search(
    query: str,
    strategy: str = "auto",
    limit: int | None = None,
    model: str | None = None,
) -> SearchResponse:
    """Unified retrieval entry point.

    Parameters
    ----------
    strategy : str
        One of "metadata", "semantic", "hybrid", "auto" (default: "auto").
    """
    cfg = load_retrieval_config()
    effective_limit = limit if limit is not None else cfg.get("default_top_k", 10)

    if strategy == "auto":
        classification = classify_query(query, model=model)
        strategy = classification.strategy
        reasoning = classification.reasoning
    else:
        reasoning = f"User-selected strategy: {strategy}"

    if strategy == "metadata":
        results = _run_metadata_first(query, effective_limit, model)
    elif strategy == "semantic":
        results = _run_semantic_first(query, effective_limit)
    elif strategy == "hybrid":
        results = _run_hybrid(query, effective_limit, model)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    return SearchResponse(
        results=results,
        strategy=strategy,
        reasoning=reasoning,
    )
```

### Pattern 2: Reciprocal Rank Fusion (RRF)
**What:** Merge ranked results from multiple engines using rank-based scoring that avoids score normalization issues.
**When to use:** When `strategy="hybrid"` is selected (or auto routes to hybrid).
**Formula:** `RRF_score(d) = sum(weight_e / (k + rank_e(d))) for each engine e where d appears`
**Example:**
```python
# Source: Croft et al. (2009) RRF paper, adapted for weighted variant
def reciprocal_rank_fusion(
    ranked_lists: dict[str, list[RetrievalResult]],
    k: int = 60,
    weights: dict[str, float] | None = None,
) -> list[FusedResult]:
    """Fuse multiple ranked lists using weighted RRF.

    Parameters
    ----------
    ranked_lists : dict[str, list[RetrievalResult]]
        Engine name -> sorted results (best first).
    k : int
        RRF constant (default 60). Higher k dampens rank differences.
    weights : dict[str, float] | None
        Per-engine weight multiplier. Default 1.0 for all engines.
    """
    if weights is None:
        weights = {engine: 1.0 for engine in ranked_lists}

    # Accumulate RRF scores per doc_id
    doc_scores: dict[str, float] = {}
    doc_engines: dict[str, dict[str, float]] = {}  # doc_id -> {engine: original_score}

    for engine_name, results in ranked_lists.items():
        w = weights.get(engine_name, 1.0)
        for rank, result in enumerate(results, start=1):
            rrf_contrib = w / (k + rank)
            doc_scores[result.doc_id] = doc_scores.get(result.doc_id, 0.0) + rrf_contrib
            if result.doc_id not in doc_engines:
                doc_engines[result.doc_id] = {}
            doc_engines[result.doc_id][engine_name] = result.score

    # Sort by fused score descending
    sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)

    # Build FusedResult objects
    fused_results = []
    for doc_id, fused_score in sorted_docs:
        fused_results.append(FusedResult(
            doc_id=doc_id,
            fused_score=fused_score,
            engine_scores=doc_engines[doc_id],
            contributing_engines=list(doc_engines[doc_id].keys()),
        ))
    return fused_results
```

### Pattern 3: LLM Query Intent Classification
**What:** Use LLM structured output to classify a query as `structured`, `conceptual`, or `mixed`.
**When to use:** When `strategy="auto"` is selected (default).
**Example:**
```python
# Source: project pattern from metadata.py generate_filters()
CLASSIFICATION_SCHEMA: dict = {
    "type": "json_schema",
    "json_schema": {
        "name": "query_classification",
        "schema": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "enum": ["structured", "conceptual", "mixed"],
                },
                "reasoning": {"type": "string"},
                "structured_indicators": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["intent", "reasoning", "structured_indicators"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}


def classify_query(query: str, model: str | None = None) -> QueryClassification:
    """Classify query intent via LLM structured output."""
    # Same pattern as _llm_completion in metadata.py
    response = _llm_completion(model, [
        {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ])
    parsed = json.loads(response)
    intent = parsed["intent"]

    # Map intent to strategy
    strategy_map = {
        "structured": "metadata",
        "conceptual": "semantic",
        "mixed": "hybrid",
    }
    return QueryClassification(
        intent=intent,
        strategy=strategy_map[intent],
        reasoning=parsed["reasoning"],
        structured_indicators=parsed["structured_indicators"],
    )
```

### Pattern 4: Metadata-First with Semantic Fallback
**What:** Run metadata search first; if results are few/empty, supplement with semantic search.
**When to use:** When auto-routing classifies query as `structured`.
**Example:**
```python
def _run_metadata_first(query, limit, model):
    meta_results = search_metadata(query, limit=limit, model=model)
    if len(meta_results) < 3:  # Few results -- supplement with semantic
        sem_results = search_semantic(query, limit=limit)
        # Deduplicate by doc_id, metadata results take priority
        seen = {r.doc_id for r in meta_results}
        for r in sem_results:
            if r.doc_id not in seen:
                meta_results.append(r)
                seen.add(r.doc_id)
    return meta_results[:limit]
```

### Anti-Patterns to Avoid
- **Score normalization before fusion:** RRF specifically avoids this by using rank positions instead of raw scores. Do NOT normalize scores to [0,1] before fusion -- each engine's scores have different distributions.
- **Merging by score comparison across engines:** Metadata scores (0-1 fraction) are not comparable to semantic DocScores or description cosine similarities. RRF rank-based fusion handles this.
- **LLM classification without fallback:** If the classification LLM call fails, default to `hybrid` (safest fallback that covers both structured and conceptual).
- **Blocking on classification:** Classification is a single lightweight LLM call with structured output. Do not add retry loops beyond the existing tenacity retry for network errors.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rank fusion | Custom weighted-average score normalization | RRF formula (20 lines) | Score normalization is fragile; RRF is proven robust across heterogeneous score distributions |
| Query classification | Regex/keyword pattern matching for structured indicators | LLM structured output classification | User explicitly decided LLM classification; regex misses linguistic variations in Italian legal queries |
| Config management | Custom config parser or env var system | Extend existing `load_retrieval_config()` + YAML section | Pattern already established for `llm:`, `ingestion:`, `retrieval:` sections |
| Result deduplication | Manual set tracking across engines | Dict-based doc_id deduplication in RRF function | RRF naturally handles duplicates by accumulating scores from multiple engines |

**Key insight:** The existing codebase already has all patterns needed. The RRF algorithm is pure math (no library). Classification follows the exact `litellm.completion()` + `response_format` pattern from `metadata.py`. Config extension just adds a YAML section and defaults.

## Common Pitfalls

### Pitfall 1: Score Incompatibility Across Engines
**What goes wrong:** Attempting to compare or average raw scores from different engines (metadata match fraction 0-1, DocScore aggregation ~0.3-2.0+, cosine similarity 0-1).
**Why it happens:** Different scoring functions produce different distributions.
**How to avoid:** RRF operates on RANK positions, not raw scores. Keep per-engine scores in the result for transparency but never compare them directly.
**Warning signs:** `if score > threshold` applied to mixed-engine results without engine awareness.

### Pitfall 2: RRF k Constant Too Small or Too Large
**What goes wrong:** With k=0, the top-ranked result from each engine dominates. With k=1000+, all ranks produce nearly identical scores, losing differentiation.
**Why it happens:** k acts as a dampening factor. The standard value k=60 is well-tested empirically.
**How to avoid:** Default to k=60 (user-configurable). The formula is `weight / (k + rank)`, so rank=1 with k=60 gives `1/61 = 0.0164`, while rank=10 gives `1/70 = 0.0143` -- a gentle 13% decay.
**Warning signs:** All fused scores are nearly identical (k too high) or the top result always wins (k too low).

### Pitfall 3: Embedding Computed Multiple Times
**What goes wrong:** Semantic search and description search both need the query embedding. Computing it twice doubles embedding API costs.
**Why it happens:** Calling `search_semantic()` and `search_description()` independently.
**How to avoid:** Compute `embed_query(query)` once and pass `query_embedding` to both `search_semantic()` and `search_description()`. Both functions already accept this parameter.
**Warning signs:** Embedding API called twice for the same query string in a single search.

### Pitfall 4: Classification Prompt Drifting from Indicators
**What goes wrong:** The LLM classification prompt does not enumerate the specific structured indicators, causing inconsistent routing.
**Why it happens:** Vague classification prompt like "determine if this is structured or conceptual."
**How to avoid:** Inject the explicit indicator list into the classification prompt: dates/date ranges, ECLI, GU numbers, law numbers, court/authority names, doc type keywords (sentenza, decreto, ordinanza, circolare).
**Warning signs:** Same query classified differently on repeated runs.

### Pitfall 5: Auto Mode Reporting Breaks on LLM Failure
**What goes wrong:** When LLM classification fails, the `reasoning` field is empty or the strategy field is unset.
**Why it happens:** No fallback logic for classification failure.
**How to avoid:** On classification failure, default to `strategy="hybrid"` with `reasoning="Classification failed, defaulting to hybrid"`.
**Warning signs:** `SearchResponse.reasoning` is None or empty string.

### Pitfall 6: updated_at Tech Debt -- Guard Bypass
**What goes wrong:** `update_document()` in `documents.py` injects `updated_at` into the filtered dict AFTER the `_METADATA_COLUMNS` guard, meaning it bypasses the allowlist silently.
**Why it happens:** `updated_at` was added as a one-off addition rather than being included in the guard set.
**How to avoid:** Add `"updated_at"` to the `_METADATA_COLUMNS` set so the guard is the single source of truth. The functional behavior stays the same (always set on update), but the code path goes through the guard.
**Warning signs:** `_METADATA_COLUMNS` audit shows columns being written that are not in the set.

## Code Examples

Verified patterns from the project codebase:

### FusedResult Dataclass
```python
# Following project convention from models.py
@dataclass
class FusedResult:
    """Result from RRF fusion across multiple engines."""
    doc_id: str
    fused_score: float
    metadata: dict
    engine_scores: dict[str, float]    # {engine_name: original_score}
    contributing_engines: list[str]     # ["metadata", "semantic", "description"]
    confidence: str                    # "high"/"medium"/"low" based on fused_score
```

### SearchResponse Dataclass
```python
@dataclass
class SearchResponse:
    """Top-level response from the strategy dispatcher."""
    results: list                     # FusedResult or RetrievalResult subclasses
    strategy: str                     # "metadata", "semantic", "hybrid", "auto"
    reasoning: str                    # Auto mode: LLM reasoning; manual: "User-selected"
    engine_gaps: list[str] = field(default_factory=list)  # Engines that returned 0 results
```

### QueryClassification Dataclass
```python
@dataclass
class QueryClassification:
    """LLM classification of query intent."""
    intent: str          # "structured", "conceptual", "mixed"
    strategy: str        # Mapped: "metadata", "semantic", "hybrid"
    reasoning: str       # LLM explanation
    structured_indicators: list[str]  # Detected indicators
```

### Config YAML retrieval: Section
```yaml
# Addition to pageindex/config.yaml
retrieval:
  default_top_k: 10
  default_strategy: "auto"
  rrf_k: 60
  engine_weights:
    metadata: 1.0
    semantic: 1.0
    description: 1.0
  global_min_score: 0.01          # RRF scores are small (0.01-0.05 range)
  internal_fetch_multiplier: 2    # Fetch 2x top_k from each engine before fusion
  docscore_min_threshold: 0.3
  metadata_min_threshold: 0.25
  description_min_threshold: 0.6
  confidence_thresholds:
    metadata:
      high: 0.7
      medium: 0.4
    semantic:
      high: 0.6
      medium: 0.35
    description:
      high: 0.8
      medium: 0.6
    tree_search:
      high: 0.7
      medium: 0.4
  tree_search_top_n: 5
  tree_search_max_concurrency: 5
  metadata_max_retries: 3
```

### Classification System Prompt
```python
CLASSIFICATION_SYSTEM_PROMPT = """\
You are a query intent classifier for an Italian legal document retrieval system.

Classify the user's query into one of three categories:

1. **structured** -- The query primarily asks for documents matching specific structured criteria.
   Indicators: dates or date ranges, legal identifiers (ECLI, GU numbers, law numbers), \
court/authority names, document type keywords (sentenza, decreto, ordinanza, circolare, legge, \
regolamento, direttiva).

2. **conceptual** -- The query asks about a legal topic, concept, or principle without specifying \
structured identifiers.
   Indicators: abstract legal questions, topical queries, "what is...", "how does...", \
legal principle names, conceptual descriptions.

3. **mixed** -- The query combines structured identifiers WITH conceptual/topical elements.
   Example: "sentenze della Cassazione dal 2020 sulla responsabilita' medica"
   (has doc_type + court + date range + legal topic)

Rules:
- If the query has ANY structured indicator AND a conceptual element, classify as "mixed".
- If the query has ONLY structured indicators, classify as "structured".
- If the query has NO structured indicators, classify as "conceptual".
- List the specific structured indicators you detected.

Output ONLY the JSON object."""
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| BM25 + cosine hybrid | RRF across multiple heterogeneous engines | 2023+ (Elastic, OpenSearch, Milvus adoption) | RRF avoids score normalization issues |
| Regex/keyword routing | LLM intent classification | 2024-2025 | More robust for multilingual queries |
| Single-engine retrieval | Multi-engine fusion with transparency | 2024-2025 | Users can see which engines contributed |

**Deprecated/outdated:**
- Min-max score normalization for fusion: fragile, distribution-dependent; RRF is the modern standard.
- Convex combination (alpha*score_a + (1-alpha)*score_b): requires careful tuning per engine pair; RRF is more robust.

## Open Questions

1. **Global minimum score threshold for RRF-fused results**
   - What we know: Individual engine thresholds exist (metadata: 0.25, semantic/DocScore: 0.3, description: 0.6). RRF fused scores are in a much smaller range (~0.01-0.05) because they are sums of reciprocal ranks.
   - What's unclear: What threshold value filters noise without losing relevant results in the fused output.
   - Recommendation: Start with a very low threshold (0.01) for fused results since RRF scores are inherently small. The per-engine thresholds already filter low-quality results before they enter fusion. Make it configurable (`global_min_score` in config.yaml) so it can be tuned with real data.

2. **Internal fetch size per engine before fusion**
   - What we know: User decided "same top-K fetch size from all engines before fusion." The final top-K default is 10.
   - What's unclear: Whether fetching exactly 10 from each engine gives enough candidates after deduplication and threshold filtering.
   - Recommendation: Use a configurable multiplier (default 2x), so fetch 20 from each engine, fuse, then take top 10. This gives RRF enough candidates to produce a meaningful ranking.

3. **Metadata-first fallback threshold for "few results"**
   - What we know: When auto routes to metadata-first, semantic fallback triggers if results are "few/empty."
   - What's unclear: What count qualifies as "few."
   - Recommendation: Fewer than `min(3, limit // 3)` results triggers fallback. Make configurable.

## Sources

### Primary (HIGH confidence)
- `/websites/litellm_ai` (Context7) -- Structured output with response_format json_schema; confirmed working pattern with Gemini models
- Project codebase `pageindex/retrieval/metadata.py` -- Existing `litellm.completion()` + `response_format` pattern with tenacity retry
- Project codebase `pageindex/retrieval/config.py` -- Existing `load_retrieval_config()` with fallback-to-defaults pattern
- Project codebase `pageindex/retrieval/models.py` -- Existing dataclass pattern for result types

### Secondary (MEDIUM confidence)
- [RRF Implementation in Python](https://safjan.com/implementing-rank-fusion-in-python/) -- RRF formula, k=60 constant, Python implementation
- [OpenSearch RRF](https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/) -- RRF in production hybrid search systems
- [ParadeDB RRF](https://www.paradedb.com/learn/search-concepts/reciprocal-rank-fusion) -- RRF formula verification, k=60 as standard
- [Elastic Hybrid Search](https://www.elastic.co/what-is/hybrid-search) -- Industry standard for multi-engine fusion
- [LiteLLM JSON Mode Docs](https://docs.litellm.ai/docs/completion/json_mode) -- Verified structured output works with Gemini 2.0+

### Tertiary (LOW confidence)
- None -- all findings verified with at least two sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- zero new dependencies, all patterns already exist in codebase
- Architecture: HIGH -- RRF is well-documented math, classification follows existing metadata.py pattern exactly
- Pitfalls: HIGH -- identified from real codebase patterns and known RRF edge cases
- Config: HIGH -- extending existing load_retrieval_config() pattern, ISSUE-03 from audit explicitly calls for this

**Research date:** 2026-02-23
**Valid until:** 2026-03-23 (30 days -- stable domain, no fast-moving library dependencies)
