"""Chunks table operations and vector similarity search.

Provides helpers for inserting text chunks (with optional vector
embeddings) and performing semantic search via the ``match_chunks``
RPC function.
"""

from __future__ import annotations

from .client import get_client


def insert_chunks(chunks: list[dict]) -> list[dict]:
    """Batch-insert chunks and return the inserted rows.

    Parameters
    ----------
    chunks : list[dict]
        Each dict must contain ``doc_id`` (str) and ``content`` (str).
        Optional keys: ``embedding`` (list[float]), ``node_id`` (str),
        ``metadata`` (dict).

    Returns
    -------
    list[dict]
        The inserted rows.
    """
    rows = []
    for chunk in chunks:
        row: dict = {
            "doc_id": chunk["doc_id"],
            "content": chunk["content"],
        }
        if chunk.get("embedding") is not None:
            row["embedding"] = chunk["embedding"]
        if chunk.get("node_id") is not None:
            row["node_id"] = chunk["node_id"]
        if chunk.get("metadata") is not None:
            row["metadata"] = chunk["metadata"]
        rows.append(row)

    client = get_client()
    response = client.table("chunks").insert(rows).execute()
    return response.data


def get_chunks_by_doc(doc_id: str) -> list[dict]:
    """Return all chunks belonging to a document.

    Parameters
    ----------
    doc_id : str
        The UUID of the parent document.

    Returns
    -------
    list[dict]
        List of chunk rows.
    """
    client = get_client()
    response = client.table("chunks").select("*").eq("doc_id", doc_id).execute()
    return response.data


def match_chunks(
    query_embedding: list[float],
    match_threshold: float = 0.7,
    match_count: int = 20,
) -> list[dict]:
    """Perform vector similarity search via the ``match_chunks`` RPC.

    Parameters
    ----------
    query_embedding : list[float]
        Query vector (must match the dimension of stored embeddings).
    match_threshold : float
        Minimum cosine similarity to include (default 0.7).
    match_count : int
        Maximum number of results to return (default 20).

    Returns
    -------
    list[dict]
        Matching chunks with keys: chunk_id, doc_id, content, metadata,
        similarity.
    """
    client = get_client()
    response = client.rpc(
        "match_chunks",
        {
            "query_embedding": query_embedding,
            "match_threshold": match_threshold,
            "match_count": match_count,
        },
    ).execute()
    return response.data
