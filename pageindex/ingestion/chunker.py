"""Tree-aware recursive text chunker for the ingestion pipeline.

Provides:
- ``chunk_leaf_nodes()``   -- chunk a document's leaf nodes respecting tree boundaries
- ``recursive_split()``    -- hand-rolled recursive text splitter with overlap
- ``build_tree_path()``    -- DFS through tree_json to build a human-readable path
- ``build_embedding_text()`` -- prepend metadata + tree path to chunk content
"""

from __future__ import annotations

from typing import Callable

from .models import ChunkData

# Separator hierarchy: paragraphs -> lines -> sentences -> words
SEPARATORS: list[str] = ["\n\n", "\n", ". ", " "]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def chunk_leaf_nodes(
    leaf_nodes: list[dict],
    page_list_or_pdf_path,
    tree_json: dict,
    max_tokens: int = 800,
    overlap_ratio: float = 0.1,
    count_tokens_fn: Callable[[str], int] | None = None,
) -> list[ChunkData]:
    """Chunk a document at tree leaf node boundaries.

    Iterates over leaf nodes produced by ``get_leaf_nodes(tree_json)``.
    For each leaf, if the text fits within *max_tokens* it becomes a single
    ``ChunkData``; otherwise it is recursively split into overlapping
    sub-chunks.

    Parameters
    ----------
    leaf_nodes : list[dict]
        Leaf nodes from ``get_leaf_nodes()``. Each must have at least
        ``node_id``, ``start_index``, ``end_index``. May have ``text``
        (when ``if_add_node_text='yes'``).
    page_list_or_pdf_path : str or list
        Either the path to the source PDF (str) for text extraction via
        ``get_text_of_pages``, or a list of pre-extracted page texts.
    tree_json : dict
        The full tree structure for path resolution.
    max_tokens : int
        Maximum token count per chunk (default 800).
    overlap_ratio : float
        Fraction of overlap between consecutive sub-chunks (default 0.1).
    count_tokens_fn : callable (str) -> int, optional
        Token counting function. **Required** -- raises ``ValueError`` if
        ``None``.

    Returns
    -------
    list[ChunkData]
        Ordered list of chunks with traceability back to tree nodes.
    """
    if count_tokens_fn is None:
        raise ValueError("count_tokens_fn is required")

    chunks: list[ChunkData] = []

    for leaf in leaf_nodes:
        node_id = leaf.get("node_id", "")
        title = leaf.get("title", "")
        start_page = leaf.get("start_index", 1)
        end_page = leaf.get("end_index", 1)

        # --- Get leaf text ---------------------------------------------------
        text = leaf.get("text") or leaf.get("content")
        if not text:
            # Fallback: extract text from PDF pages
            if isinstance(page_list_or_pdf_path, str):
                # Lazy import to avoid circular dependency
                from pageindex.utils import get_text_of_pages

                text = get_text_of_pages(
                    page_list_or_pdf_path, start_page, end_page, tag=False
                )
            else:
                # page_list_or_pdf_path is a list of page texts
                text = " ".join(
                    page_list_or_pdf_path[i]
                    for i in range(start_page - 1, min(end_page, len(page_list_or_pdf_path)))
                )

        if not text or not text.strip():
            continue

        # --- Build tree path --------------------------------------------------
        tree_path = build_tree_path(tree_json, node_id)

        # --- Token check and split if necessary --------------------------------
        token_count = count_tokens_fn(text)
        base_metadata = {
            "title": title,
            "start_page": start_page,
            "end_page": end_page,
        }

        if token_count <= max_tokens:
            chunks.append(
                ChunkData(
                    content=text,
                    node_id=node_id,
                    tree_path=tree_path,
                    metadata={**base_metadata, "sub_chunk_index": None},
                )
            )
        else:
            sub_texts = recursive_split(
                text, max_tokens, overlap_ratio, count_tokens_fn
            )
            for i, sub_text in enumerate(sub_texts):
                chunks.append(
                    ChunkData(
                        content=sub_text,
                        node_id=node_id,
                        tree_path=tree_path,
                        metadata={**base_metadata, "sub_chunk_index": i},
                    )
                )

    return chunks


def recursive_split(
    text: str,
    max_tokens: int,
    overlap_ratio: float,
    count_tokens_fn: Callable[[str], int],
) -> list[str]:
    """Recursively split *text* into chunks that fit within *max_tokens*.

    Uses a separator hierarchy (paragraphs -> lines -> sentences -> words).
    Overlap is added between consecutive chunks via ``_add_overlap``.

    Parameters
    ----------
    text : str
        The text to split.
    max_tokens : int
        Maximum token count per chunk.
    overlap_ratio : float
        Fraction of the previous chunk to prepend as overlap.
    count_tokens_fn : callable (str) -> int
        Token counting function.

    Returns
    -------
    list[str]
        List of text chunks, each within *max_tokens*.
    """
    if count_tokens_fn(text) <= max_tokens:
        return [text]

    # Try each separator level
    for separator in SEPARATORS:
        segments = text.split(separator)
        if len(segments) <= 1:
            continue

        chunks: list[str] = []
        current = ""
        for segment in segments:
            candidate = current + separator + segment if current else segment
            if count_tokens_fn(candidate) <= max_tokens:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                # If a single segment exceeds max_tokens, it will be caught
                # in the next iteration or handled by the midpoint fallback
                current = segment

        if current:
            chunks.append(current)

        if len(chunks) > 1:
            # Recursively split any oversized chunks
            final: list[str] = []
            for chunk in chunks:
                if count_tokens_fn(chunk) > max_tokens:
                    final.extend(
                        recursive_split(chunk, max_tokens, overlap_ratio, count_tokens_fn)
                    )
                else:
                    final.append(chunk)
            return _add_overlap(final, overlap_ratio, count_tokens_fn)

    # Fallback: no separator worked -- split at character midpoint and recurse
    mid = len(text) // 2
    left = recursive_split(text[:mid], max_tokens, overlap_ratio, count_tokens_fn)
    right = recursive_split(text[mid:], max_tokens, overlap_ratio, count_tokens_fn)
    return left + right


def build_tree_path(tree_json: dict | list, target_node_id: str) -> str:
    """Build a human-readable path from root to a tree node.

    Performs DFS through *tree_json* to locate the node whose ``node_id``
    matches *target_node_id*, collecting titles along the way.

    Parameters
    ----------
    tree_json : dict or list
        The tree structure produced by ``page_index_main()``.
    target_node_id : str
        The ``node_id`` to search for.

    Returns
    -------
    str
        ``" > "``-separated path of node titles (e.g.
        ``"Article 4 > Section 2 > Paragraph 3"``), or ``""`` if the
        node is not found.
    """
    if not target_node_id:
        return ""

    path: list[str] = []
    if _dfs_find_path(tree_json, target_node_id, path):
        return " > ".join(path)
    return ""


def build_embedding_text(chunk: ChunkData, doc_metadata: dict) -> str:
    """Build the full text to embed for a chunk.

    Prepends a metadata block and the tree path to the chunk content,
    following the contextual embedding strategy from CONTEXT.md.

    Layout::

        Title: ...
        Type: ...
        Date: ...
        Court: ...
        Legal Area: ...
        ECLI: ...
        Description: ...

        Section: Article 4 > Section 2

        [chunk content]

    Parameters
    ----------
    chunk : ChunkData
        The chunk to embed.
    doc_metadata : dict
        Document-level metadata. Expected keys: ``doc_name``, ``doc_type``,
        ``date``, ``authority``, ``legal_area`` (list), ``ecli``,
        ``doc_description``.

    Returns
    -------
    str
        The complete text for embedding.
    """
    legal_area = doc_metadata.get("legal_area")
    if isinstance(legal_area, list):
        legal_area_str = ", ".join(legal_area)
    else:
        legal_area_str = str(legal_area) if legal_area else ""

    meta_block = (
        f"Title: {doc_metadata.get('doc_name', '')}\n"
        f"Type: {doc_metadata.get('doc_type', '')}\n"
        f"Date: {doc_metadata.get('date', '')}\n"
        f"Court: {doc_metadata.get('authority', '')}\n"
        f"Legal Area: {legal_area_str}\n"
        f"ECLI: {doc_metadata.get('ecli', '')}\n"
        f"Description: {doc_metadata.get('doc_description', '')}\n"
    )

    return f"{meta_block}\nSection: {chunk.tree_path}\n\n{chunk.content}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _dfs_find_path(
    node: dict | list, target_node_id: str, path: list[str]
) -> bool:
    """DFS helper that populates *path* with titles on the way to *target_node_id*.

    Returns ``True`` if the target was found (and *path* is populated).
    """
    if isinstance(node, list):
        for child in node:
            if _dfs_find_path(child, target_node_id, path):
                return True
        return False

    if isinstance(node, dict):
        title = node.get("title", "")
        current_node_id = node.get("node_id", "")

        # Push current title onto path
        if title:
            path.append(title)

        # Check if this is the target
        if current_node_id == target_node_id:
            return True

        # Recurse into children
        children = node.get("nodes", [])
        if children:
            if _dfs_find_path(children, target_node_id, path):
                return True

        # Backtrack: this node is not on the path to the target
        if title:
            path.pop()

    return False


def _add_overlap(
    chunks: list[str], overlap_ratio: float, count_tokens_fn: Callable[[str], int]
) -> list[str]:
    """Add overlap between consecutive chunks.

    Takes trailing words from the previous chunk and prepends them to the
    next chunk, controlled by *overlap_ratio*.
    """
    if len(chunks) <= 1 or overlap_ratio <= 0:
        return chunks

    result: list[str] = [chunks[0]]
    for i in range(1, len(chunks)):
        prev_tokens = count_tokens_fn(chunks[i - 1])
        overlap_tokens = int(prev_tokens * overlap_ratio)
        if overlap_tokens <= 0:
            result.append(chunks[i])
            continue

        # Take trailing words from the previous chunk as a prefix
        prev_words = chunks[i - 1].split()
        overlap_words: list[str] = []
        token_count = 0
        for word in reversed(prev_words):
            word_tokens = count_tokens_fn(word)
            if token_count + word_tokens > overlap_tokens:
                break
            overlap_words.insert(0, word)
            token_count += word_tokens

        prefix = " ".join(overlap_words)
        result.append(prefix + " " + chunks[i] if prefix else chunks[i])

    return result
