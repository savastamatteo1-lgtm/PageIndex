"""PageIndex -- multi-document retrieval for Italian legal documents.

Public API::

    from pageindex import PageIndex, SearchResponse, IngestionResult

    # Flat kwargs (convenience):
    pi = PageIndex(supabase_url='...', supabase_key='...')
    # Nested dict (explicit):
    pi = PageIndex(supabase={"url": "...", "key": "..."})

    results = pi.search("sentenze della Corte di Cassazione 2020")
    print(results.strategy_used, results.timing)

Subsystem modules remain accessible as submodule imports::

    from pageindex.retrieval import search_semantic
    from pageindex.ingestion import ingest
    from pageindex.db import get_document
"""

# Public API class and return types
from .api import (
    PageIndex,
    SearchResponse,
    IngestionResult,
    DocumentInfo,
    DeepSearchResult,
    DeepSearchResponse,
)

# Exception hierarchy
from .exceptions import PageIndexError, ConfigError, IngestionError, SearchError

# Settings (for advanced users who want to pre-build settings)
from .api import PageIndexSettings

__all__ = [
    "PageIndex",
    "PageIndexSettings",
    "SearchResponse",
    "DeepSearchResult",
    "DeepSearchResponse",
    "IngestionResult",
    "DocumentInfo",
    "PageIndexError",
    "ConfigError",
    "IngestionError",
    "SearchError",
]
