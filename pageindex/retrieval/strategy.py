"""Strategy dispatcher with RRF fusion and LLM-based auto-routing.

Provides a single :func:`search` entry point that handles four strategies:

- ``metadata`` -- metadata-first with semantic fallback if results are few
- ``semantic`` -- pure semantic (DocScore) search
- ``hybrid`` -- RRF fusion across metadata, semantic, and description engines
- ``auto`` -- LLM classifies query intent and selects the best strategy

The hybrid strategy uses Reciprocal Rank Fusion (RRF) to merge ranked lists
from heterogeneous engines without score normalisation.  Per-engine weights
and the RRF constant *k* are configurable via ``config.yaml``.

Public API
----------
- :func:`search` -- unified retrieval entry point
- :func:`classify_query` -- LLM query intent classification
- :func:`reciprocal_rank_fusion` -- weighted RRF across ranked lists
"""

from __future__ import annotations

import json
import logging

import litellm
from tenacity import retry, stop_after_attempt, wait_random_exponential

from .metadata import search_metadata
from .semantic import search_semantic, embed_query
from .description import search_description
from .config import load_retrieval_config
from .models import FusedResult, SearchResponse, QueryClassification, assign_confidence
from .prompts import CLASSIFICATION_SCHEMA, CLASSIFICATION_SYSTEM_PROMPT
from pageindex.llm.config import load_llm_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid strategies
# ---------------------------------------------------------------------------

_VALID_STRATEGIES = {"metadata", "semantic", "hybrid", "auto"}

# ---------------------------------------------------------------------------
# 1. LLM helper for classification
# ---------------------------------------------------------------------------


@retry(wait=wait_random_exponential(min=1, max=30), stop=stop_after_attempt(3))
def _llm_completion(model: str, messages: list[dict]) -> str:
    """Call LiteLLM completion with classification ``response_format``.

    Network errors and rate limits are retried via tenacity (up to 3
    attempts with exponential backoff).

    Parameters
    ----------
    model : str
        LLM model identifier (e.g. ``"gemini/gemini-2.0-flash"``).
    messages : list[dict]
        Chat messages (system + user).

    Returns
    -------
    str
        Raw JSON string from the LLM response.
    """
    response = litellm.completion(
        model=model,
        messages=messages,
        response_format=CLASSIFICATION_SCHEMA,
        temperature=0,
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# 2. Query intent classification
# ---------------------------------------------------------------------------


def classify_query(
    query: str, model: str | None = None
) -> QueryClassification:
    """Classify query intent via LLM structured output.

    Maps the LLM's intent label to a retrieval strategy:

    - ``structured`` -> ``metadata``
    - ``conceptual`` -> ``semantic``
    - ``mixed`` -> ``hybrid``

    On **any** failure (JSON parse error, key error, LLM failure), returns a
    safe fallback defaulting to ``hybrid`` with explanatory reasoning.  This
    avoids the anti-pattern of auto mode breaking on classification errors
    (RESEARCH Pitfall 5).

    Parameters
    ----------
    query : str
        Natural-language search query.
    model : str | None
        LLM model.  When ``None`` resolves from ``config.yaml``.

    Returns
    -------
    QueryClassification
        Classification result with intent, strategy, reasoning, and
        structured indicators.
    """
    if model is None:
        model = load_llm_config().get(
            "completion_model", "gemini/gemini-2.0-flash"
        )

    strategy_map = {
        "structured": "metadata",
        "conceptual": "semantic",
        "mixed": "hybrid",
    }

    try:
        raw = _llm_completion(
            model,
            [
                {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
        )
        parsed = json.loads(raw)
        intent = parsed["intent"]
        return QueryClassification(
            intent=intent,
            strategy=strategy_map[intent],
            reasoning=parsed["reasoning"],
            structured_indicators=parsed.get("structured_indicators", []),
        )
    except Exception:
        logger.warning(
            "Query classification failed, defaulting to hybrid",
            exc_info=True,
        )
        return QueryClassification(
            intent="mixed",
            strategy="hybrid",
            reasoning="Classification failed, defaulting to hybrid",
            structured_indicators=[],
        )


# ---------------------------------------------------------------------------
# 3. Reciprocal Rank Fusion
# ---------------------------------------------------------------------------


def reciprocal_rank_fusion(
    ranked_lists: dict[str, list],
    k: int = 60,
    weights: dict[str, float] | None = None,
) -> list[FusedResult]:
    """Fuse multiple ranked lists using weighted Reciprocal Rank Fusion.

    Each result is scored as ``weight / (k + rank)`` from each contributing
    engine, then scores are summed across engines.  This avoids the pitfall
    of comparing raw scores across heterogeneous engines (Pitfall 1).

    Parameters
    ----------
    ranked_lists : dict[str, list]
        Engine name -> sorted results (best first).  Each result must have
        ``doc_id``, ``score``, and ``metadata`` attributes.
    k : int
        RRF constant (default 60).  Higher values flatten rank differences.
    weights : dict[str, float] | None
        Per-engine weight multiplier.  Default ``1.0`` for all engines.

    Returns
    -------
    list[FusedResult]
        Fused results sorted by ``fused_score`` descending, each with
        ``engine_scores``, ``contributing_engines``, and ``confidence``.
    """
    if weights is None:
        weights = {engine: 1.0 for engine in ranked_lists}

    # Accumulate RRF scores per doc_id
    doc_rrf_scores: dict[str, float] = {}
    doc_engine_scores: dict[str, dict[str, float]] = {}
    doc_metadata: dict[str, dict] = {}

    for engine_name, results in ranked_lists.items():
        w = weights.get(engine_name, 1.0)
        for rank, result in enumerate(results, start=1):
            rrf_contrib = w / (k + rank)
            doc_id = result.doc_id

            doc_rrf_scores[doc_id] = (
                doc_rrf_scores.get(doc_id, 0.0) + rrf_contrib
            )

            if doc_id not in doc_engine_scores:
                doc_engine_scores[doc_id] = {}
            doc_engine_scores[doc_id][engine_name] = result.score

            # Keep metadata from the first engine that contributes the doc_id
            if doc_id not in doc_metadata:
                doc_metadata[doc_id] = getattr(result, "metadata", {})

    # Sort by fused score descending
    sorted_docs = sorted(
        doc_rrf_scores.items(), key=lambda x: x[1], reverse=True
    )

    # Build FusedResult objects
    fused_results: list[FusedResult] = []
    for doc_id, fused_score in sorted_docs:
        engines = doc_engine_scores[doc_id]
        fused_results.append(
            FusedResult(
                doc_id=doc_id,
                fused_score=fused_score,
                metadata=doc_metadata.get(doc_id, {}),
                engine_scores=engines,
                contributing_engines=list(engines.keys()),
                confidence=assign_confidence(fused_score, "hybrid"),
            )
        )
    return fused_results


# ---------------------------------------------------------------------------
# 4. Per-strategy runners
# ---------------------------------------------------------------------------


def _run_metadata_first(
    query: str, limit: int, model: str | None
) -> tuple[list, list[str]]:
    """Run metadata search, supplementing with semantic if results are few.

    Per RESEARCH Pattern 4 and CONTEXT locked decisions: pure structured
    queries route to metadata-first; if the result count is below
    ``metadata_fallback_threshold``, semantic search supplements the results.
    Deduplication by ``doc_id`` gives priority to metadata results.

    Returns
    -------
    tuple[list, list[str]]
        ``(results, engine_gaps)`` -- gaps is always empty for single-engine
        modes.
    """
    cfg = load_retrieval_config()
    fallback_threshold = cfg.get("metadata_fallback_threshold", 3)

    meta_results = search_metadata(query, limit=limit, model=model)

    if len(meta_results) < fallback_threshold:
        logger.info(
            "Metadata-first: %d results (< %d), supplementing with semantic",
            len(meta_results),
            fallback_threshold,
        )
        sem_results = search_semantic(query, limit=limit)
        # Deduplicate -- metadata results take priority
        seen = {r.doc_id for r in meta_results}
        for r in sem_results:
            if r.doc_id not in seen:
                meta_results.append(r)
                seen.add(r.doc_id)

    return meta_results[:limit], []


def _run_semantic_first(
    query: str, limit: int
) -> tuple[list, list[str]]:
    """Run pure semantic search.

    Per CONTEXT locked decisions: pure conceptual queries route to
    semantic-first with no fallback needed.

    Returns
    -------
    tuple[list, list[str]]
        ``(results, engine_gaps)`` -- gaps is always empty for single-engine
        modes.
    """
    results = search_semantic(query, limit=limit)
    return results, []


def _run_hybrid(
    query: str, limit: int, model: str | None
) -> tuple[list[FusedResult], list[str]]:
    """Run all three engines and fuse results via RRF.

    Per CONTEXT locked decisions (all locked):

    - Same top-K fetch size from all engines (``internal_fetch_multiplier``)
    - Query embedding computed ONCE and shared (Pitfall 3 avoidance)
    - Configurable per-engine weights (default 1:1:1)
    - Engine gaps tracked and exposed in :class:`SearchResponse`
    - Global minimum score cutoff applied after fusion

    Returns
    -------
    tuple[list[FusedResult], list[str]]
        ``(fused_results, engine_gaps)`` where engine_gaps lists engine names
        that returned zero results.
    """
    cfg = load_retrieval_config()
    fetch_size = limit * cfg.get("internal_fetch_multiplier", 2)

    # Compute query embedding ONCE (Pitfall 3)
    query_emb = embed_query(query)

    # Run all three engines
    meta_results = search_metadata(query, limit=fetch_size, model=model)
    sem_results = search_semantic(
        query, limit=fetch_size, query_embedding=query_emb
    )
    desc_results = search_description(
        query, limit=fetch_size, query_embedding=query_emb
    )

    # Build ranked lists and track engine gaps
    ranked_lists: dict[str, list] = {
        "metadata": meta_results,
        "semantic": sem_results,
        "description": desc_results,
    }
    engine_gaps: list[str] = [
        name for name, results in ranked_lists.items() if len(results) == 0
    ]

    if engine_gaps:
        logger.info("Engine gaps in hybrid search: %s", engine_gaps)

    # RRF fusion
    fused_results = reciprocal_rank_fusion(
        ranked_lists,
        k=cfg.get("rrf_k", 60),
        weights=cfg.get("engine_weights"),
    )

    # Filter by global minimum score
    global_min = cfg.get("global_min_score", 0.01)
    fused_results = [r for r in fused_results if r.fused_score >= global_min]

    # Truncate to requested limit
    return fused_results[:limit], engine_gaps


# ---------------------------------------------------------------------------
# 5. Main entry point
# ---------------------------------------------------------------------------


def search(
    query: str,
    strategy: str = "auto",
    limit: int | None = None,
    model: str | None = None,
) -> SearchResponse:
    """Unified retrieval entry point with strategy dispatch.

    Routes the query to the appropriate engine(s) based on the selected
    strategy.  When ``strategy="auto"`` (the default), LLM classification
    determines the best approach.

    Parameters
    ----------
    query : str
        Natural-language search query.
    strategy : str
        One of ``"metadata"``, ``"semantic"``, ``"hybrid"``, ``"auto"``
        (default ``"auto"``).
    limit : int | None
        Maximum number of results.  When ``None`` uses ``default_top_k``
        from ``config.yaml``.
    model : str | None
        LLM model for filter generation / classification.  When ``None``
        uses the config default.

    Returns
    -------
    SearchResponse
        Results with strategy name, reasoning, and engine gap information.

    Raises
    ------
    ValueError
        If *strategy* is not one of the valid options.
    """
    if strategy not in _VALID_STRATEGIES:
        raise ValueError(
            f"Unknown strategy: {strategy!r}. "
            f"Valid strategies: {sorted(_VALID_STRATEGIES)}"
        )

    cfg = load_retrieval_config()
    effective_limit = (
        limit if limit is not None else cfg.get("default_top_k", 10)
    )

    # Resolve auto strategy
    if strategy == "auto":
        classification = classify_query(query, model=model)
        effective_strategy = classification.strategy
        reasoning = classification.reasoning
        logger.info(
            "Auto strategy selected: %s (intent: %s)",
            effective_strategy,
            classification.intent,
        )
    else:
        effective_strategy = strategy
        reasoning = f"User-selected strategy: {strategy}"

    # Dispatch to the appropriate runner
    if effective_strategy == "metadata":
        results, engine_gaps = _run_metadata_first(
            query, effective_limit, model
        )
    elif effective_strategy == "semantic":
        results, engine_gaps = _run_semantic_first(query, effective_limit)
    elif effective_strategy == "hybrid":
        results, engine_gaps = _run_hybrid(query, effective_limit, model)
    else:
        # Should not reach here given validation above, but defensive
        raise ValueError(f"Unknown resolved strategy: {effective_strategy!r}")

    return SearchResponse(
        results=results,
        strategy=effective_strategy,
        reasoning=reasoning,
        engine_gaps=engine_gaps,
    )
