# pageindex.retrieval -- Multi-strategy document retrieval engines.

from .metadata import search_metadata
from .semantic import search_semantic, embed_query
from .description import search_description, backfill_description_embeddings
from .tree_search import tree_search, tree_search_sync
from .models import (
    RetrievalResult,
    MetadataResult,
    SemanticResult,
    DescriptionResult,
    TreeSearchResult,
    MetadataFilter,
)
