"""Public API for PageIndex.

Defines the pydantic-settings configuration model (:class:`PageIndexSettings`),
public return types (:class:`SearchResponse`, :class:`IngestionResult`,
:class:`DocumentInfo`), and the main :class:`PageIndex` facade class.

Usage::

    from pageindex.api import PageIndex

    pi = PageIndex(supabase={"url": "https://...", "key": "..."})
    results = pi.search("sentenze penali 2023")
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


# ---------------------------------------------------------------------------
# Nested configuration sub-models (plain BaseModel, NOT BaseSettings)
# ---------------------------------------------------------------------------


class LLMSettings(BaseModel):
    """LLM provider configuration."""

    completion_model: str = "gemini/gemini-2.0-flash"
    embedding_model: str = "gemini/gemini-embedding-001"
    embedding_dimensions: int = 768
    temperature: float = 0


class SupabaseSettings(BaseModel):
    """Supabase connection settings.

    ``url`` and ``key`` are required with no defaults -- they must be
    provided via constructor kwargs, environment variables, or a
    combination of the two.

    Uses ``extra="ignore"`` so that the YAML ``url_env`` / ``key_env``
    helper fields are silently discarded (the actual values come from
    env vars or kwargs, never from the YAML indirection).
    """

    model_config = ConfigDict(extra="ignore")

    url: str
    key: str

    @field_validator("url", "key")
    @classmethod
    def _reject_empty(cls, v: str, info) -> str:
        if not v.strip():
            raise ValueError(
                f"{info.field_name} must not be empty -- provide a real value "
                "via constructor kwargs or environment variables"
            )
        return v


class IngestionSettings(BaseModel):
    """Ingestion pipeline tunables."""

    metadata_pages: int = 3
    chunk_max_tokens: int = 800
    chunk_overlap: float = 0.1
    max_workers: int = 1
    max_embedding_batch: int = 250


class RetrievalSettings(BaseModel):
    """Retrieval / fusion strategy tunables."""

    model_config = ConfigDict(extra="ignore")

    default_top_k: int = 10
    default_strategy: str = "auto"
    rrf_k: int = 60
    engine_weights: dict[str, float] = {
        "metadata": 1.0,
        "semantic": 1.0,
        "description": 1.0,
    }
    global_min_score: float = 0.01
    internal_fetch_multiplier: int = 2


# ---------------------------------------------------------------------------
# Top-level settings model
# ---------------------------------------------------------------------------


class PageIndexSettings(BaseSettings):
    """Layered configuration for PageIndex.

    Resolution priority (highest wins):
        1. Constructor kwargs
        2. Environment variables (``PAGEINDEX_`` prefix, ``__`` nested delimiter)
        3. YAML config file (``pageindex/config.yaml``)
        4. Field defaults

    For the most common env vars (Supabase connection), both the prefixed
    nested form (``PAGEINDEX_SUPABASE__URL``) and the standard flat form
    (``SUPABASE_URL``) are accepted.  The flat form is checked via a
    ``model_validator`` as a convenience fallback.
    """

    model_config = SettingsConfigDict(
        env_prefix="PAGEINDEX_",
        env_nested_delimiter="__",
        yaml_file=str(Path(__file__).parent / "config.yaml"),
        yaml_file_encoding="utf-8",
        extra="ignore",
    )

    supabase: SupabaseSettings
    llm: LLMSettings = LLMSettings()
    ingestion: IngestionSettings = IngestionSettings()
    retrieval: RetrievalSettings = RetrievalSettings()

    @model_validator(mode="before")
    @classmethod
    def _populate_supabase_from_env(cls, values: dict) -> dict:
        """Accept flat kwargs and ``SUPABASE_URL`` / ``SUPABASE_KEY`` env vars.

        Precedence (highest wins):
            1. ``supabase`` dict already provided -> use as-is
            2. Flat kwargs ``supabase_url`` / ``supabase_key`` -> restructure
            3. Env vars ``SUPABASE_URL`` / ``SUPABASE_KEY`` -> fallback

        The flat kwargs are popped from *values* so pydantic does not
        reject them as unexpected fields.
        """
        # Pop flat kwargs (remove so pydantic's extra="ignore" doesn't
        # need to handle them and so they don't clash with field names)
        flat_url = values.pop("supabase_url", None)
        flat_key = values.pop("supabase_key", None)

        supabase = values.get("supabase")

        # Read flat env vars (ignore empty strings)
        env_url = os.environ.get("SUPABASE_URL", "").strip() or None
        env_key = os.environ.get("SUPABASE_KEY", "").strip() or None

        if isinstance(supabase, dict):
            # Partially provided dict -- fill missing keys from flat kwargs then env
            if "url" not in supabase:
                supabase["url"] = flat_url or env_url
            if "key" not in supabase:
                supabase["key"] = flat_key or env_key
        elif supabase is None:
            # Not provided as dict -- try flat kwargs, then env vars
            sb: dict[str, str] = {}
            url = flat_url or env_url
            key = flat_key or env_key
            if url:
                sb["url"] = url
            if key:
                sb["key"] = key
            if sb:
                values["supabase"] = sb

        return values

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Set source priority: init kwargs > env vars > YAML file."""
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls),
        )


# ---------------------------------------------------------------------------
# Public return types (stdlib dataclasses per project convention)
# ---------------------------------------------------------------------------


@dataclass
class SearchResponse:
    """Public response from a PageIndex search operation.

    This is distinct from the internal
    :class:`pageindex.retrieval.models.SearchResponse` -- it adds ``query``,
    ``timing``, and renames ``strategy`` to ``strategy_used`` for a cleaner
    public API.

    Attributes
    ----------
    results : list
        :class:`~pageindex.retrieval.models.FusedResult` or
        :class:`~pageindex.retrieval.models.RetrievalResult` subclass instances.
    query : str
        The original query string.
    strategy_used : str
        Which strategy was executed (``"metadata"``, ``"semantic"``,
        ``"hybrid"``).
    scores : dict
        Engine-level score summary (e.g. engine gaps, result count).
    timing : float
        Elapsed seconds for the search call.
    reasoning : str
        For auto mode: LLM reasoning.  For manual: description of choice.
    """

    results: list
    query: str
    strategy_used: str
    scores: dict = field(default_factory=dict)
    timing: float = 0.0
    reasoning: str = ""


@dataclass
class IngestionResult:
    """Result of ingesting a single document.

    Attributes
    ----------
    document_id : str
        The ``doc_id`` assigned in Supabase.
    document_name : str
        The filename or document name.
    chunks_created : int
        Number of chunks stored in the vector table.
    status : str
        ``"succeeded"``, ``"failed"``, or ``"skipped"``.
    error : str | None
        Error message when ``status`` is ``"failed"``.
    """

    document_id: str
    document_name: str
    chunks_created: int
    status: str
    error: str | None = None


@dataclass
class DocumentInfo:
    """Combined view of a stored document.

    Returned by ``PageIndex.retrieve()`` to give a full picture of a
    document without requiring multiple DB queries from the caller.

    Attributes
    ----------
    doc_id : str
        Document UUID.
    name : str
        Human-readable document name.
    metadata : dict
        Full document metadata row from the ``documents`` table.
    tree : dict | None
        Tree structure if available.
    chunks : list[dict] | None
        Optionally loaded chunk data.
    """

    doc_id: str
    name: str
    metadata: dict = field(default_factory=dict)
    tree: dict | None = None
    chunks: list[dict] | None = None


# ---------------------------------------------------------------------------
# PageIndex facade class
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


class PageIndex:
    """Single entry point for the PageIndex public API.

    Holds configuration, initialises subsystem singletons (DB client, LLM
    provider), and delegates to the proven internal engines for search,
    ingestion, and retrieval.

    Parameters
    ----------
    settings : PageIndexSettings | None
        Pre-built settings object.  When provided, *kwargs* are ignored.
    **kwargs
        Individual configuration values forwarded to
        :class:`PageIndexSettings`.  Common keys: ``supabase``, ``llm``,
        ``ingestion``, ``retrieval``.

    Raises
    ------
    ConfigError
        If the resulting configuration is invalid (wraps pydantic
        ``ValidationError`` with a clear message listing missing fields).

    Examples
    --------
    >>> pi = PageIndex(supabase={"url": "https://xyz.supabase.co", "key": "..."})
    >>> resp = pi.search("sentenze della Corte di Cassazione 2023")
    >>> print(resp.strategy_used, len(resp.results))
    """

    def __init__(
        self, *, settings: PageIndexSettings | None = None, **kwargs
    ) -> None:
        from pageindex.exceptions import ConfigError

        if settings is not None:
            self._settings = settings
        else:
            try:
                self._settings = PageIndexSettings(**kwargs)
            except Exception as exc:
                # Re-raise pydantic ValidationError as ConfigError
                raise ConfigError(
                    f"Invalid PageIndex configuration: {exc}"
                ) from exc

        self._init_subsystems()

    # ------------------------------------------------------------------
    # Subsystem wiring (private)
    # ------------------------------------------------------------------

    def _init_subsystems(self) -> None:
        """Wire settings to existing subsystem singletons.

        1. Supabase client: set env vars and reset singleton so the next
           ``get_client()`` call picks up the new credentials.
        2. LLM provider: replace the module-level singleton with a fresh
           ``LLMProvider`` built from the current settings.
        """
        import pageindex.db.client as db_client_mod
        import pageindex.llm.provider as llm_provider_mod
        from pageindex.llm.provider import LLMProvider

        # --- Supabase ---
        os.environ["SUPABASE_URL"] = self._settings.supabase.url
        os.environ["SUPABASE_KEY"] = self._settings.supabase.key
        db_client_mod.reset_client()

        # --- LLM provider ---
        llm_provider_mod._provider_instance = LLMProvider(
            self._settings.llm.model_dump()
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        strategy: str = "auto",
        limit: int | None = None,
    ) -> SearchResponse:
        """Run a multi-strategy search.

        Parameters
        ----------
        query : str
            Natural-language search query.
        strategy : str
            One of ``"auto"``, ``"metadata"``, ``"semantic"``, ``"hybrid"``.
        limit : int | None
            Max results.  Defaults to ``retrieval.default_top_k``.

        Returns
        -------
        SearchResponse
            Public response with results, timing, strategy info.

        Raises
        ------
        SearchError
            On any search failure.
        """
        from pageindex.exceptions import SearchError
        from pageindex.retrieval.strategy import search as strategy_search

        effective_limit = limit or self._settings.retrieval.default_top_k

        try:
            t0 = time.perf_counter()
            internal = strategy_search(
                query,
                strategy=strategy,
                limit=effective_limit,
                retrieval_overrides=self._settings.retrieval.model_dump(),
            )
            elapsed = round(time.perf_counter() - t0, 3)
        except Exception as exc:
            raise SearchError(f"Search failed: {exc}") from exc

        return SearchResponse(
            results=internal.results,
            query=query,
            strategy_used=internal.strategy,
            scores={
                "engine_gaps": internal.engine_gaps,
                "result_count": len(internal.results),
            },
            timing=elapsed,
            reasoning=internal.reasoning,
        )

    def search_semantic(
        self, query: str, *, limit: int | None = None
    ) -> list:
        """Direct semantic (vector) search.

        Parameters
        ----------
        query : str
            Natural-language search query.
        limit : int | None
            Max results.  Defaults to ``retrieval.default_top_k``.

        Returns
        -------
        list[SemanticResult]
            Ranked results from the semantic engine.
        """
        from pageindex.exceptions import SearchError
        from pageindex.retrieval.semantic import search_semantic as _search_sem

        effective_limit = limit or self._settings.retrieval.default_top_k
        try:
            return _search_sem(query, limit=effective_limit)
        except Exception as exc:
            raise SearchError(f"Semantic search failed: {exc}") from exc

    def search_metadata(
        self, query: str, *, limit: int | None = None
    ) -> list:
        """Direct metadata (structured filter) search.

        Parameters
        ----------
        query : str
            Natural-language search query.
        limit : int | None
            Max results.  Defaults to ``retrieval.default_top_k``.

        Returns
        -------
        list[MetadataResult]
            Ranked results from the metadata engine.
        """
        from pageindex.exceptions import SearchError
        from pageindex.retrieval.metadata import search_metadata as _search_meta

        effective_limit = limit or self._settings.retrieval.default_top_k
        try:
            return _search_meta(query, limit=effective_limit)
        except Exception as exc:
            raise SearchError(f"Metadata search failed: {exc}") from exc

    def search_tree(
        self,
        query: str,
        doc_ids: list[str],
        *,
        model: str | None = None,
    ) -> list:
        """Direct tree-structure search across specific documents.

        Parameters
        ----------
        query : str
            Natural-language search query.
        doc_ids : list[str]
            Document UUIDs to search within.
        model : str | None
            LLM model override for section relevance assessment.

        Returns
        -------
        list[TreeSearchResult]
            Ranked results with relevant sections identified.
        """
        from pageindex.exceptions import SearchError
        from pageindex.retrieval.tree_search import tree_search_sync

        effective_model = model or self._settings.llm.completion_model
        try:
            return tree_search_sync(doc_ids, query, model=effective_model)
        except Exception as exc:
            raise SearchError(f"Tree search failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest(
        self,
        *,
        path: str | None = None,
        text: str | None = None,
        url: str | None = None,
        additional_fields: dict | None = None,
    ) -> IngestionResult:
        """Ingest a document into the PageIndex corpus.

        Provide exactly one of *path* or *text*.

        Parameters
        ----------
        path : str | None
            Absolute path to a PDF file.
        text : str | None
            Raw text content (planned -- not yet implemented).
        url : str | None
            Source URL when using *text* input.
        additional_fields : dict | None
            Extra metadata to attach to the document record
            (stored in the ``additional_fields`` JSONB column).
            These are **user-provided** overflow fields, not
            auto-extracted metadata.

        Returns
        -------
        IngestionResult
            Outcome of the ingestion.

        Raises
        ------
        IngestionError
            If ingestion fails or invalid arguments are provided.
        """
        from pageindex.exceptions import IngestionError
        from pageindex.llm.provider import get_provider

        # Validate mutually exclusive inputs
        if path and text:
            raise IngestionError(
                "Provide exactly one of 'path' or 'text', not both"
            )
        if not path and not text:
            raise IngestionError(
                "Provide at least one of 'path' or 'text'"
            )

        if text is not None:
            raise IngestionError(
                "Text ingestion not yet implemented -- use path= with a PDF file. "
                "Text ingestion is planned for a future release."
            )

        # Path-based ingestion
        try:
            from pageindex.ingestion.stages import process_single_document

            config = self._build_ingestion_config()
            pipeline = process_single_document(
                pdf_path=path,
                llm_provider=get_provider(),
                config=config,
                metadata_pages=self._settings.ingestion.metadata_pages,
                chunk_max_tokens=self._settings.ingestion.chunk_max_tokens,
                chunk_overlap=self._settings.ingestion.chunk_overlap,
            )

            return IngestionResult(
                document_id=pipeline.doc_id,
                document_name=pipeline.doc_name,
                chunks_created=len(pipeline.chunks) if pipeline.chunks else 0,
                status="succeeded",
            )
        except Exception as exc:
            raise IngestionError(f"Ingestion failed: {exc}") from exc

    def _build_ingestion_config(self) -> dict:
        """Convert ingestion settings to the dict format expected by the pipeline.

        The tree-indexing stage expects a dict with ``config.yaml`` top-level
        keys.  We include ``model`` so the user-specified LLM model is used
        for tree indexing instead of the ``config.yaml`` default.

        Only valid top-level ``config.yaml`` keys are safe here -- adding
        nested keys like ``llm`` or ``retrieval`` would trigger
        ``ConfigLoader._validate_keys()`` ValueError (Pitfall 1).
        """
        return {"model": self._settings.llm.completion_model}

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(self, doc_id: str) -> DocumentInfo:
        """Retrieve full document information by ID.

        Parameters
        ----------
        doc_id : str
            Document UUID.

        Returns
        -------
        DocumentInfo
            Combined document metadata and tree structure.

        Raises
        ------
        SearchError
            If the document is not found.
        """
        from pageindex.db.documents import get_document
        from pageindex.db.trees import get_tree
        from pageindex.exceptions import SearchError

        doc = get_document(doc_id)
        if doc is None:
            raise SearchError(f"Document not found: {doc_id}")

        tree_row = get_tree(doc_id)
        tree = tree_row.get("tree_json") if tree_row else None

        return DocumentInfo(
            doc_id=doc_id,
            name=doc.get("doc_name", ""),
            metadata=doc,
            tree=tree,
        )

    def list_documents(
        self, *, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        """List available documents with pagination.

        Parameters
        ----------
        limit : int
            Maximum number of documents (default 100).
        offset : int
            Number of documents to skip (default 0).

        Returns
        -------
        list[dict]
            Document metadata rows.
        """
        from pageindex.db.documents import list_documents

        return list_documents(limit=limit, offset=offset)
