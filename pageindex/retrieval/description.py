"""Description search engine with backfill utility.

Searches documents by comparing the query embedding against pre-embedded
document descriptions via the ``match_descriptions`` RPC function.  This is
a fast, lightweight discovery mechanism -- no per-query LLM cost, just a
single embedding call for the query followed by a cosine similarity lookup.

The :func:`backfill_description_embeddings` utility embeds descriptions for
documents ingested before the ``description_embedding`` column was added.
"""

from __future__ import annotations

import logging

from pageindex.db.client import get_client
from pageindex.db.documents import get_document
from pageindex.llm.provider import get_provider
from pageindex.retrieval.config import (
    DEFAULT_TOP_K,
    DESCRIPTION_MIN_THRESHOLD,
)
from pageindex.retrieval.models import DescriptionResult, assign_confidence
from pageindex.retrieval.semantic import embed_query

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Description search entry point
# ---------------------------------------------------------------------------


def search_description(
    query: str,
    limit: int | None = None,
    query_embedding: list[float] | None = None,
) -> list[DescriptionResult]:
    """Search documents by embedding similarity against descriptions.

    Uses the ``match_descriptions`` RPC (created in migration 003) to compare
    the query embedding against pre-embedded ``description_embedding`` vectors
    on the ``documents`` table.

    Parameters
    ----------
    query : str
        Natural-language search query.
    limit : int | None
        Maximum number of documents to return.  Falls back to
        :data:`~pageindex.retrieval.config.DEFAULT_TOP_K`.
    query_embedding : list[float] | None
        Pre-computed query embedding.  When ``None``, computed via
        :func:`~pageindex.retrieval.semantic.embed_query`.  Pass this to share
        the same embedding between semantic and description engines.

    Returns
    -------
    list[DescriptionResult]
        Documents ranked by description similarity, each with
        ``engine_name="description"`` and the matched description text.
    """
    # Resolve defaults
    effective_limit = limit if limit is not None else DEFAULT_TOP_K

    # Compute or reuse query embedding
    if query_embedding is None:
        query_embedding = embed_query(query)

    # Call match_descriptions RPC
    client = get_client()
    response = client.rpc(
        "match_descriptions",
        {
            "query_embedding": query_embedding,
            "match_threshold": DESCRIPTION_MIN_THRESHOLD,
            "match_count": effective_limit,
        },
    ).execute()

    rpc_results = response.data
    if not rpc_results:
        logger.info("Description search: no descriptions matched (threshold=%.2f)", DESCRIPTION_MIN_THRESHOLD)
        return []

    # Build result objects with full document metadata
    results: list[DescriptionResult] = []
    for row in rpc_results:
        doc_row = get_document(row["doc_id"])
        if doc_row is None:
            logger.warning("Description search: document %s not found, skipping", row["doc_id"])
            continue
        results.append(
            DescriptionResult(
                doc_id=row["doc_id"],
                score=row["similarity"],
                metadata=doc_row,
                engine_name="description",
                confidence=assign_confidence(row["similarity"], "description"),
                doc_description=row.get("doc_description", ""),
            )
        )

    logger.info(
        "Description search: %d results (threshold=%.2f)",
        len(results),
        DESCRIPTION_MIN_THRESHOLD,
    )
    return results


# ---------------------------------------------------------------------------
# Backfill utility
# ---------------------------------------------------------------------------


def backfill_description_embeddings(batch_size: int = 250) -> dict:
    """Embed descriptions for documents missing ``description_embedding``.

    Queries for all documents that have a non-null ``doc_description`` but
    a null ``description_embedding``, then batch-embeds the descriptions
    and updates each row.

    Parameters
    ----------
    batch_size : int
        Number of descriptions to embed per LLM call (default 250, matching
        Gemini API batch limits used in the ingestion pipeline).

    Returns
    -------
    dict
        Summary with keys ``backfilled`` (int) and ``errors`` (int).
    """
    client = get_client()

    # Find documents needing backfill
    response = (
        client.table("documents")
        .select("doc_id, doc_description")
        .is_("description_embedding", "null")
        .not_.is_("doc_description", "null")
        .execute()
    )

    docs = response.data
    if not docs:
        logger.info("Backfill: no documents need description embedding")
        return {"backfilled": 0, "errors": 0}

    total = len(docs)
    logger.info("Backfill: %d documents need description embeddings", total)

    provider = get_provider()
    backfilled = 0
    errors = 0

    # Process in batches
    for i in range(0, total, batch_size):
        batch = docs[i : i + batch_size]
        descriptions = [d["doc_description"] for d in batch]

        try:
            embeddings = provider.embed(descriptions)
        except Exception:
            logger.exception(
                "Backfill: failed to embed batch %d-%d, skipping",
                i,
                i + len(batch),
            )
            errors += len(batch)
            continue

        # Update each document with its embedding
        for doc, embedding in zip(batch, embeddings):
            try:
                client.table("documents").update(
                    {"description_embedding": embedding}
                ).eq("doc_id", doc["doc_id"]).execute()
                backfilled += 1
            except Exception:
                logger.exception(
                    "Backfill: failed to update doc %s", doc["doc_id"]
                )
                errors += 1

        logger.info("Backfilled %d/%d description embeddings", backfilled, total)

    logger.info(
        "Backfill complete: %d backfilled, %d errors (of %d total)",
        backfilled,
        errors,
        total,
    )
    return {"backfilled": backfilled, "errors": errors}
