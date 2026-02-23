"""Documents table operations.

Provides CRUD helpers for the ``documents`` table, which stores Italian
legal document metadata (doc_type, date, authority, ecli, etc.).
"""

from __future__ import annotations

from datetime import datetime, timezone

from .client import get_client

# Columns that accept direct values from the metadata dict.
_METADATA_COLUMNS = {
    "doc_type",
    "date",
    "authority",
    "ecli",
    "gu_number",
    "legal_area",
    "parties",
    "court_level",
    "cross_references",
    "additional_fields",
    "doc_description",
    "description_embedding",
    "ingestion_status",
    "needs_review",
    "updated_at",
}


def insert_document(doc_name: str, metadata: dict | None = None) -> dict:
    """Insert a new document and return the full inserted row.

    Parameters
    ----------
    doc_name : str
        Document filename or identifier (required).
    metadata : dict, optional
        Flat dict whose keys correspond to document column names
        (doc_type, date, authority, ecli, gu_number, legal_area,
        parties, court_level, cross_references, additional_fields,
        doc_description).  ``None`` values are filtered out so that
        database defaults apply.

    Returns
    -------
    dict
        The inserted row including the generated ``doc_id``.
    """
    row: dict = {"doc_name": doc_name}
    if metadata:
        for key, value in metadata.items():
            if key in _METADATA_COLUMNS and value is not None:
                row[key] = value
    client = get_client()
    response = client.table("documents").insert(row).execute()
    return response.data[0]


def get_document(doc_id: str) -> dict | None:
    """Retrieve a single document by UUID.

    Returns ``None`` if no document matches the given *doc_id*.
    """
    client = get_client()
    response = client.table("documents").select("*").eq("doc_id", doc_id).execute()
    if response.data:
        return response.data[0]
    return None


def get_document_by_name(doc_name: str) -> dict | None:
    """Retrieve a document by its ``doc_name``.

    Returns the first match or ``None``.
    """
    client = get_client()
    response = (
        client.table("documents")
        .select("*")
        .eq("doc_name", doc_name)
        .limit(1)
        .execute()
    )
    if response.data:
        return response.data[0]
    return None


def list_documents(limit: int = 100, offset: int = 0) -> list[dict]:
    """List documents with pagination.

    Parameters
    ----------
    limit : int
        Maximum number of documents to return (default 100).
    offset : int
        Number of documents to skip (default 0).

    Returns
    -------
    list[dict]
        List of document rows.
    """
    client = get_client()
    response = (
        client.table("documents")
        .select("*")
        .range(offset, offset + limit - 1)
        .execute()
    )
    return response.data


def update_document(doc_id: str, updates: dict) -> dict:
    """Update an existing document row and return the updated row.

    Filters the *updates* dict through ``_METADATA_COLUMNS`` to prevent
    writing to arbitrary columns.  Automatically sets ``updated_at`` to
    the current UTC timestamp.

    Parameters
    ----------
    doc_id : str
        UUID of the document to update.
    updates : dict
        Column-value pairs to update.  Only keys present in
        ``_METADATA_COLUMNS`` are applied; others are silently ignored.

    Returns
    -------
    dict
        The updated document row.
    """
    filtered: dict = {}
    for key, value in updates.items():
        if key in _METADATA_COLUMNS:
            filtered[key] = value

    # Always set updated_at to current timestamp
    filtered["updated_at"] = datetime.now(timezone.utc).isoformat()

    client = get_client()
    response = (
        client.table("documents")
        .update(filtered)
        .eq("doc_id", doc_id)
        .execute()
    )
    return response.data[0]


def delete_document(doc_id: str) -> None:
    """Delete a document and its related data (via ON DELETE CASCADE).

    The ``document_trees`` and ``chunks`` tables have foreign keys with
    ``ON DELETE CASCADE``, so related rows are automatically removed.

    Parameters
    ----------
    doc_id : str
        UUID of the document to delete.
    """
    client = get_client()
    client.table("documents").delete().eq("doc_id", doc_id).execute()
