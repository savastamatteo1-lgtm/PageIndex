"""Semantic search engine with DocScore aggregation.

Embeds a query via :func:`embed_query`, performs vector similarity search
against stored chunk embeddings via the ``match_chunks`` RPC, and aggregates
chunk-level similarities into document-level **DocScores** using the canonical
formula::

    DocScore = (1 / sqrt(N + 1)) * sum(ChunkScore(n))

where *N* is the number of matching chunks for a document.  The ``1/sqrt(N+1)``
factor normalises by chunk count to prevent long-document bias while still
rewarding broad relevance.

:func:`embed_query` is a standalone helper so that callers (e.g. the
description engine) can reuse the same query embedding without recomputing it.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict

from pageindex.db.chunks import match_chunks
from pageindex.db.documents import get_document
from pageindex.llm.provider import get_provider
from pageindex.retrieval.config import (
    DEFAULT_TOP_K,
    DOCSCORE_MIN_THRESHOLD,
)
from pageindex.retrieval.models import SemanticResult, assign_confidence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Query embedding (reusable across engines)
# ---------------------------------------------------------------------------


def embed_query(query: str) -> list[float]:
    """Embed a single query string and return the vector.

    Uses :func:`~pageindex.llm.provider.get_provider` to obtain an
    :class:`~pageindex.llm.provider.LLMProvider` and calls ``embed([query])``.
    The resulting embedding can be shared with other engines (e.g. description
    search) since all engines use the same embedding model and dimensions.

    Parameters
    ----------
    query : str
        Natural-language search query.

    Returns
    -------
    list[float]
        768-dimensional embedding vector.
    """
    provider = get_provider()
    embeddings = provider.embed([query])
    return embeddings[0]


# ---------------------------------------------------------------------------
# DocScore aggregation
# ---------------------------------------------------------------------------


def compute_doc_scores(chunk_results: list[dict]) -> list[dict]:
    """Aggregate chunk similarities into document-level DocScores.

    Groups chunks by ``doc_id`` and computes:

    .. math::

        \\text{DocScore} = \\frac{1}{\\sqrt{N+1}} \\sum_{n=1}^{N} \\text{ChunkScore}(n)

    This is the canonical formula from REQUIREMENTS.md (confirmed canonical per
    RESEARCH.md Open Question 2).

    Parameters
    ----------
    chunk_results : list[dict]
        Raw results from ``match_chunks`` RPC.  Each dict must have keys
        ``doc_id`` (str) and ``similarity`` (float).

    Returns
    -------
    list[dict]
        Sorted (descending) list of dicts with keys: ``doc_id`` (str),
        ``score`` (float), ``chunk_count`` (int).
    """
    doc_chunks: dict[str, list[float]] = defaultdict(list)
    for chunk in chunk_results:
        doc_chunks[chunk["doc_id"]].append(chunk["similarity"])

    doc_scores: list[dict] = []
    for doc_id, similarities in doc_chunks.items():
        n = len(similarities)
        raw_sum = sum(similarities)
        doc_score = (1 / math.sqrt(n + 1)) * raw_sum
        doc_scores.append({
            "doc_id": doc_id,
            "score": doc_score,
            "chunk_count": n,
        })

    return sorted(doc_scores, key=lambda x: x["score"], reverse=True)


# ---------------------------------------------------------------------------
# Semantic search entry point
# ---------------------------------------------------------------------------


def search_semantic(
    query: str,
    limit: int | None = None,
    query_embedding: list[float] | None = None,
    match_threshold: float | None = None,
) -> list[SemanticResult]:
    """Search documents by semantic similarity with DocScore aggregation.

    Parameters
    ----------
    query : str
        Natural-language search query.
    limit : int | None
        Maximum number of documents to return.  Falls back to
        :data:`~pageindex.retrieval.config.DEFAULT_TOP_K`.
    query_embedding : list[float] | None
        Pre-computed query embedding.  When ``None``, computed via
        :func:`embed_query`.  Pass this to avoid redundant embedding calls
        when the same query is used across multiple engines.
    match_threshold : float | None
        Minimum chunk-level cosine similarity.  Falls back to the
        ``match_chunks`` RPC default of 0.7.

    Returns
    -------
    list[SemanticResult]
        Documents ranked by DocScore, each with ``engine_name="semantic"``,
        ``confidence`` label, and ``chunk_count``.
    """
    # Resolve defaults
    effective_limit = limit if limit is not None else DEFAULT_TOP_K
    effective_threshold = match_threshold if match_threshold is not None else 0.7

    # Compute or reuse query embedding
    if query_embedding is None:
        query_embedding = embed_query(query)

    # Request more chunks than top-K since multiple chunks map to same doc
    chunk_multiplier = 5
    chunks = match_chunks(
        query_embedding=query_embedding,
        match_threshold=effective_threshold,
        match_count=effective_limit * chunk_multiplier,
    )

    if not chunks:
        logger.info("Semantic search: no chunks matched (threshold=%.2f)", effective_threshold)
        return []

    # Aggregate to document-level scores
    scored_docs = compute_doc_scores(chunks)

    # Filter by minimum DocScore threshold
    scored_docs = [d for d in scored_docs if d["score"] >= DOCSCORE_MIN_THRESHOLD]

    # Take top-K
    scored_docs = scored_docs[:effective_limit]

    # Fetch full metadata and build result objects
    results: list[SemanticResult] = []
    for doc in scored_docs:
        doc_row = get_document(doc["doc_id"])
        if doc_row is None:
            logger.warning("Semantic search: document %s not found, skipping", doc["doc_id"])
            continue
        results.append(
            SemanticResult(
                doc_id=doc["doc_id"],
                score=doc["score"],
                metadata=doc_row,
                engine_name="semantic",
                confidence=assign_confidence(doc["score"], "semantic"),
                chunk_count=doc["chunk_count"],
            )
        )

    logger.info(
        "Semantic search: %d results (from %d chunks, threshold=%.2f)",
        len(results),
        len(chunks),
        effective_threshold,
    )
    return results
