"""Documents table operations.

Provides CRUD helpers for the ``documents`` table, which stores Italian
legal document metadata (doc_type, date, authority, ecli, etc.).
"""

from __future__ import annotations

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
