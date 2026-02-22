"""Document trees table operations.

Provides helpers for storing and retrieving the hierarchical tree
structures produced by PageIndex for each document.
"""

from __future__ import annotations

from .client import get_client


def insert_tree(doc_id: str, tree_json: dict) -> dict:
    """Insert or update a tree for a document (upsert on doc_id).

    If a tree already exists for the given *doc_id*, it is replaced.
    This allows re-indexing a document without manual deletion.

    Parameters
    ----------
    doc_id : str
        The UUID of the parent document.
    tree_json : dict
        The full tree structure produced by PageIndex.

    Returns
    -------
    dict
        The inserted or updated row.
    """
    client = get_client()
    response = (
        client.table("document_trees")
        .upsert(
            {"doc_id": doc_id, "tree_json": tree_json},
            on_conflict="doc_id",
        )
        .execute()
    )
    return response.data[0]


def get_tree(doc_id: str) -> dict | None:
    """Retrieve the tree for a document.

    Returns ``None`` if no tree exists for the given *doc_id*.
    """
    client = get_client()
    response = (
        client.table("document_trees")
        .select("*")
        .eq("doc_id", doc_id)
        .execute()
    )
    if response.data:
        return response.data[0]
    return None
