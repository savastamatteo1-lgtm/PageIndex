"""Custom exception hierarchy for the PageIndex public API.

Provides typed exceptions so users can catch specific failure modes:

    try:
        pi = PageIndex(...)
    except ConfigError:
        ...  # missing or invalid configuration
    except IngestionError:
        ...  # document processing failed
    except SearchError:
        ...  # search operation failed
    except PageIndexError:
        ...  # any PageIndex error
"""


class PageIndexError(Exception):
    """Base exception for all PageIndex errors."""


class ConfigError(PageIndexError):
    """Raised when configuration is invalid or missing."""


class IngestionError(PageIndexError):
    """Raised when document ingestion fails."""


class SearchError(PageIndexError):
    """Raised when a search operation fails."""
