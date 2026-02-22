"""Database access layer for PageIndex Legal Retrieval.

Re-exports key functions from the documents, chunks, and trees modules
for convenient access::

    from pageindex.db import insert_document, match_chunks, get_tree
"""

from .documents import insert_document, get_document, get_document_by_name, list_documents
from .chunks import insert_chunks, match_chunks, get_chunks_by_doc
from .trees import insert_tree, get_tree

__all__ = [
    "insert_document",
    "get_document",
    "get_document_by_name",
    "list_documents",
    "insert_chunks",
    "match_chunks",
    "get_chunks_by_doc",
    "insert_tree",
    "get_tree",
]
