"""Async concurrent tree search engine for multi-document retrieval.

Wraps the existing PageIndex tree search approach for query-based node
selection across multiple documents simultaneously.  Uses ``asyncio.gather``
with a semaphore to limit concurrent LLM calls.

The tree JSON stored in the database has text fields stripped (see
``_strip_text_from_tree`` in ``pageindex.ingestion.stages``).  When text
is needed for context, it is reconstructed from stored chunks matched by
``node_id``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections import defaultdict

from pageindex.db.chunks import get_chunks_by_doc
from pageindex.db.documents import get_document
from pageindex.db.trees import get_tree
from pageindex.llm.provider import get_provider
from pageindex.retrieval.config import (
    TREE_SEARCH_MAX_CONCURRENCY,
    TREE_SEARCH_TOP_N,
    load_retrieval_config,
)
from pageindex.retrieval.models import TreeSearchResult, assign_confidence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: flatten tree nodes
# ---------------------------------------------------------------------------


def _get_tree_nodes(node: dict | list) -> list[dict]:
    """Recursively extract all nodes from a tree structure (DFS).

    Parameters
    ----------
    node : dict | list
        A single tree node (dict with ``title``, ``node_id``, etc.)
        or a list of sibling nodes.

    Returns
    -------
    list[dict]
        Flat list of every node in the tree.  Each entry retains
        ``title``, ``node_id``, ``start_index``, ``end_index``,
        and optionally ``summary``.
    """
    if isinstance(node, list):
        result: list[dict] = []
        for child in node:
            result.extend(_get_tree_nodes(child))
        return result

    if isinstance(node, dict):
        # Extract this node (without children)
        flat_node = {
            "title": node.get("title", ""),
            "node_id": node.get("node_id", ""),
            "start_index": node.get("start_index"),
            "end_index": node.get("end_index"),
        }
        if node.get("summary"):
            flat_node["summary"] = node["summary"]

        result = [flat_node]

        # Recurse into children
        children = node.get("nodes")
        if children:
            result.extend(_get_tree_nodes(children))
        return result

    return []


# ---------------------------------------------------------------------------
# Helper: reconstruct text from chunks
# ---------------------------------------------------------------------------


def _rebuild_node_text(
    doc_id: str,
    node_id: str,
    chunks: list[dict] | None = None,
) -> str:
    """Reconstruct text for a tree node from stored chunks.

    Per Pitfall 6 from RESEARCH.md: tree JSON has text fields stripped by
    ``_strip_text_from_tree`` in ``stages.py`` before storage.  Chunks are
    stored with ``node_id`` linking them back to the tree.

    Parameters
    ----------
    doc_id : str
        Document UUID.
    node_id : str
        The ``node_id`` of the target tree node.
    chunks : list[dict] | None
        Pre-loaded chunks for the document (from ``get_chunks_by_doc``).
        If ``None``, they are loaded from the database.

    Returns
    -------
    str
        Concatenated chunk content for the node, or empty string if no
        matching chunks are found.
    """
    if chunks is None:
        chunks = get_chunks_by_doc(doc_id)

    matching = [c for c in chunks if c.get("node_id") == node_id]

    # Sort by chunk order (if IDs are sequential) to preserve text order
    matching.sort(key=lambda c: c.get("id", 0))

    return " ".join(c.get("content", "") for c in matching).strip()


# ---------------------------------------------------------------------------
# Single-document tree search
# ---------------------------------------------------------------------------


_TREE_SEARCH_SYSTEM_PROMPT = """\
You are an expert at analysing document structure.  You will be given a \
user query and a list of document sections (title, optional summary, and \
a text snippet).  Your job is to identify which sections are most relevant \
to the query.

Return a JSON array of the ``node_id`` values for the relevant sections.
Only include sections that are directly relevant to the query.
If no sections are relevant, return an empty array ``[]``.

Example response:
["0003", "0007", "0012"]

Return ONLY the JSON array, no other text."""


async def _search_single_tree(
    doc_id: str,
    query: str,
    model: str,
) -> list[dict]:
    """Search a single document's tree for sections relevant to *query*.

    Parameters
    ----------
    doc_id : str
        Document UUID.
    query : str
        The user's search query.
    model : str
        LLM model name for the relevance call.

    Returns
    -------
    list[dict]
        Each dict has ``title``, ``start_page``, ``end_page``, ``node_id``.
    """
    tree_row = get_tree(doc_id)
    if tree_row is None:
        return []

    tree_json = tree_row.get("tree_json")
    if not tree_json:
        return []

    # Flatten tree into nodes
    all_nodes = _get_tree_nodes(tree_json)
    if not all_nodes:
        return []

    # Load chunks once for text reconstruction
    chunks = get_chunks_by_doc(doc_id)

    # Build section descriptions for the LLM
    section_descs: list[str] = []
    for node in all_nodes:
        nid = node.get("node_id", "")
        title = node.get("title", "Untitled")
        summary = node.get("summary", "")
        start = node.get("start_index", "?")
        end = node.get("end_index", "?")

        # Reconstruct a text snippet (first ~500 chars) for context
        text_snippet = _rebuild_node_text(doc_id, nid, chunks)
        if text_snippet and len(text_snippet) > 500:
            text_snippet = text_snippet[:500] + "..."

        desc = f"- node_id: {nid} | title: {title} | pages: {start}-{end}"
        if summary:
            desc += f"\n  summary: {summary}"
        if text_snippet:
            desc += f"\n  text: {text_snippet}"
        section_descs.append(desc)

    sections_text = "\n".join(section_descs)

    messages = [
        {"role": "system", "content": _TREE_SEARCH_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Query: {query}\n\n"
                f"Document sections:\n{sections_text}"
            ),
        },
    ]

    provider = get_provider()
    try:
        response = await provider.acomplete(messages)
    except Exception:
        logger.warning(
            "LLM call failed for tree search on doc %s", doc_id, exc_info=True
        )
        return []

    # Parse response -- expect a JSON array of node_ids
    try:
        relevant_ids = json.loads(response)
        if not isinstance(relevant_ids, list):
            relevant_ids = []
    except (json.JSONDecodeError, TypeError):
        logger.warning(
            "Could not parse LLM tree search response for doc %s: %s",
            doc_id,
            response[:200] if response else "(empty)",
        )
        return []

    # Build result sections for relevant nodes
    relevant_set = set(str(rid) for rid in relevant_ids)
    node_map = {n["node_id"]: n for n in all_nodes if n.get("node_id")}

    sections: list[dict] = []
    for nid in relevant_ids:
        nid_str = str(nid)
        node = node_map.get(nid_str)
        if node:
            sections.append(
                {
                    "title": node.get("title", ""),
                    "start_page": node.get("start_index"),
                    "end_page": node.get("end_index"),
                    "node_id": nid_str,
                }
            )

    return sections


# ---------------------------------------------------------------------------
# Concurrent multi-document tree search
# ---------------------------------------------------------------------------


async def _search_with_semaphore(
    sem: asyncio.Semaphore,
    doc_id: str,
    query: str,
    model: str,
) -> tuple[str, list[dict]]:
    """Run single tree search behind a semaphore for concurrency control."""
    async with sem:
        sections = await _search_single_tree(doc_id, query, model)
        return (doc_id, sections)


async def tree_search(
    doc_ids: list[str],
    query: str,
    model: str | None = None,
) -> list[TreeSearchResult]:
    """Concurrent tree search across multiple documents.

    Runs ``_search_single_tree`` on the top *N* documents simultaneously,
    limited by ``TREE_SEARCH_MAX_CONCURRENCY``.

    Parameters
    ----------
    doc_ids : list[str]
        Document UUIDs to search (truncated to ``TREE_SEARCH_TOP_N``).
    query : str
        The user's search query.
    model : str | None
        LLM model for tree search.  Falls back to retrieval config then
        to the default completion model.

    Returns
    -------
    list[TreeSearchResult]
        Results sorted by score descending.
    """
    # Load config for defaults
    cfg = load_retrieval_config()
    top_n = cfg.get("tree_search_top_n", TREE_SEARCH_TOP_N)
    max_concurrency = cfg.get("tree_search_max_concurrency", TREE_SEARCH_MAX_CONCURRENCY)

    # Truncate to top N documents
    doc_ids = doc_ids[:top_n]

    # Resolve model
    if model is None:
        model = cfg.get("tree_search_model") or get_provider().completion_model

    sem = asyncio.Semaphore(max_concurrency)

    tasks = [
        _search_with_semaphore(sem, doc_id, query, model)
        for doc_id in doc_ids
    ]

    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[TreeSearchResult] = []
    for result in raw_results:
        if isinstance(result, Exception):
            logger.warning("Tree search task failed: %s", result)
            continue
        if result is None:
            continue

        doc_id, sections = result
        if not sections:
            continue

        # Fetch document metadata
        doc_row = get_document(doc_id)
        metadata = doc_row if doc_row else {}

        # Score: fraction of tree nodes that were found relevant
        tree_row = get_tree(doc_id)
        total_nodes = 1  # fallback
        if tree_row and tree_row.get("tree_json"):
            total_nodes = max(len(_get_tree_nodes(tree_row["tree_json"])), 1)

        score = len(sections) / total_nodes

        results.append(
            TreeSearchResult(
                doc_id=doc_id,
                score=score,
                metadata=metadata,
                engine_name="tree_search",
                confidence=assign_confidence(score, "tree_search"),
                sections=sections,
            )
        )

    # Sort by score descending
    results.sort(key=lambda r: r.score, reverse=True)
    return results


# ---------------------------------------------------------------------------
# Sync convenience wrapper
# ---------------------------------------------------------------------------


def tree_search_sync(
    doc_ids: list[str],
    query: str,
    model: str | None = None,
) -> list[TreeSearchResult]:
    """Synchronous wrapper around :func:`tree_search`.

    Handles the case where an event loop is already running by dispatching
    to a new thread.

    Parameters
    ----------
    doc_ids : list[str]
        Document UUIDs to search.
    query : str
        The user's search query.
    model : str | None
        LLM model name override.

    Returns
    -------
    list[TreeSearchResult]
        Results sorted by score descending.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already in an async context -- run in a new thread to avoid deadlock
        result_container: list[TreeSearchResult] = []
        exception_container: list[Exception] = []

        def _run() -> None:
            try:
                result_container.extend(
                    asyncio.run(tree_search(doc_ids, query, model))
                )
            except Exception as exc:
                exception_container.append(exc)

        thread = threading.Thread(target=_run)
        thread.start()
        thread.join()

        if exception_container:
            raise exception_container[0]
        return result_container

    return asyncio.run(tree_search(doc_ids, query, model))
