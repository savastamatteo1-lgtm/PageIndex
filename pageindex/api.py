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
    tree_indexing_model: str | None = None
    num_retries: int = 10


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
class DeepSearchResult:
    """A single document result from the two-stage deep search pipeline.

    Combines the document-level score from Stage 1 (multi-strategy search)
    with the section-level detail from Stage 2 (tree search), using a
    geometric mean to produce a combined score.

    Attributes
    ----------
    doc_id : str
        Document UUID.
    combined_score : float
        Geometric mean of the normalised Stage 1 score and tree search score.
    doc_score : float
        Original (raw) document-level score from Stage 1.
    tree_score : float
        Tree search relevance score (fraction of relevant sections).
    sections : list[dict]
        Relevant sections identified by tree search, each with
        ``title``, ``start_page``, ``end_page``, ``node_id``.
    metadata : dict
        Full document metadata from the ``documents`` table.
    confidence : str
        ``"high"``, ``"medium"``, or ``"low"`` based on combined_score.
    """

    doc_id: str
    combined_score: float
    doc_score: float
    tree_score: float
    sections: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    confidence: str = "low"


@dataclass
class DeepSearchResponse:
    """Response from the two-stage deep search pipeline.

    Attributes
    ----------
    results : list[DeepSearchResult]
        Documents that passed both stages, ranked by combined score.
    query : str
        The original query string.
    stage1_count : int
        Number of documents returned by Stage 1 (before tree filtering).
    filtered_count : int
        Number of documents that had relevant tree sections (= len(results)).
    timing : float
        Total elapsed seconds for both stages.
    strategy_used : str
        Strategy used in Stage 1.
    """

    results: list[DeepSearchResult]
    query: str
    stage1_count: int = 0
    filtered_count: int = 0
    timing: float = 0.0
    strategy_used: str = ""


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
        strategy: str | None = None,
        limit: int | None = None,
    ) -> SearchResponse:
        """Run a multi-strategy search.

        Parameters
        ----------
        query : str
            Natural-language search query.
        strategy : str | None
            One of ``"auto"``, ``"metadata"``, ``"semantic"``, ``"hybrid"``.
            Defaults to ``retrieval.default_strategy`` (typically ``"auto"``).
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
        effective_strategy = strategy or self._settings.retrieval.default_strategy

        try:
            t0 = time.perf_counter()
            internal = strategy_search(
                query,
                strategy=effective_strategy,
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
        top_n: int | None = None,
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
        top_n : int | None
            Maximum number of documents to search.  When ``None``, falls
            back to the ``tree_search_top_n`` config value.

        Returns
        -------
        list[TreeSearchResult]
            Ranked results with relevant sections identified.
        """
        from pageindex.exceptions import SearchError
        from pageindex.retrieval.tree_search import tree_search_sync

        effective_model = model or self._settings.llm.completion_model
        try:
            return tree_search_sync(
                doc_ids, query, model=effective_model, top_n=top_n
            )
        except Exception as exc:
            raise SearchError(f"Tree search failed: {exc}") from exc

    def search_description(
        self, query: str, *, limit: int | None = None
    ) -> list:
        """Direct description (embedding similarity) search.

        Parameters
        ----------
        query : str
            Natural-language search query.
        limit : int | None
            Max results.  Defaults to ``retrieval.default_top_k``.

        Returns
        -------
        list[DescriptionResult]
            Ranked results from the description engine.
        """
        from pageindex.exceptions import SearchError
        from pageindex.retrieval.description import search_description as _search_desc

        effective_limit = limit or self._settings.retrieval.default_top_k
        try:
            return _search_desc(query, limit=effective_limit)
        except Exception as exc:
            raise SearchError(f"Description search failed: {exc}") from exc

    def search_deep(
        self,
        query: str,
        *,
        strategy: str | None = None,
        limit: int | None = None,
        model: str | None = None,
    ) -> DeepSearchResponse:
        """Two-stage deep search: document discovery → section-level filtering.

        **Stage 1** runs :meth:`search` to find the top candidate documents.
        **Stage 2** runs :meth:`search_tree` on those candidates to identify
        relevant sections within each document.  Documents where tree search
        finds no relevant sections are filtered out.

        Scores are combined using a geometric mean of the normalised Stage 1
        score and the tree search score, ensuring that a document must perform
        well on *both* stages to rank high.

        Parameters
        ----------
        query : str
            Natural-language search query.
        strategy : str | None
            Stage 1 strategy (forwarded to :meth:`search`).
        limit : int | None
            Max Stage 1 results (forwarded to :meth:`search`).
        model : str | None
            LLM model for Stage 2 tree search.

        Returns
        -------
        DeepSearchResponse
            Combined results with section-level detail.

        Raises
        ------
        SearchError
            On any search failure.
        """
        import math

        from pageindex.exceptions import SearchError
        from pageindex.retrieval.models import FusedResult, RetrievalResult

        t0 = time.perf_counter()

        # ------ Stage 1: document discovery ------
        try:
            stage1 = self.search(query, strategy=strategy, limit=limit)
        except Exception as exc:
            raise SearchError(f"Deep search Stage 1 failed: {exc}") from exc

        if not stage1.results:
            elapsed = round(time.perf_counter() - t0, 3)
            return DeepSearchResponse(
                results=[],
                query=query,
                stage1_count=0,
                filtered_count=0,
                timing=elapsed,
                strategy_used=stage1.strategy_used,
            )

        # Extract doc_ids and raw scores from Stage 1
        doc_scores_map: dict[str, float] = {}
        doc_metadata_map: dict[str, dict] = {}
        for r in stage1.results:
            if isinstance(r, FusedResult):
                doc_scores_map[r.doc_id] = r.fused_score
                doc_metadata_map[r.doc_id] = r.metadata
            elif isinstance(r, RetrievalResult):
                doc_scores_map[r.doc_id] = r.score
                doc_metadata_map[r.doc_id] = r.metadata

        doc_ids = list(doc_scores_map.keys())
        stage1_count = len(doc_ids)

        # Normalise Stage 1 scores to 0-1 via min-max
        raw_scores = list(doc_scores_map.values())
        s_min = min(raw_scores)
        s_max = max(raw_scores)
        score_range = s_max - s_min
        if score_range > 0:
            norm_scores = {
                did: (sc - s_min) / score_range
                for did, sc in doc_scores_map.items()
            }
        else:
            # All scores identical -- normalise to 1.0
            norm_scores = {did: 1.0 for did in doc_scores_map}

        # ------ Stage 2: tree search for section detail ------
        try:
            tree_results = self.search_tree(
                query, doc_ids, model=model, top_n=len(doc_ids)
            )
        except Exception as exc:
            raise SearchError(f"Deep search Stage 2 failed: {exc}") from exc

        # Build lookup: doc_id -> tree result
        tree_map = {tr.doc_id: tr for tr in tree_results}

        # ------ Combine scores and filter ------
        from pageindex.retrieval.models import assign_confidence

        combined: list[DeepSearchResult] = []
        for doc_id in doc_ids:
            tr = tree_map.get(doc_id)
            if tr is None or not tr.sections:
                # No relevant sections found -- filter out
                continue

            norm_s1 = norm_scores[doc_id]
            tree_score = tr.score
            # Geometric mean: both stages must contribute
            combined_score = math.sqrt(norm_s1 * tree_score)

            combined.append(DeepSearchResult(
                doc_id=doc_id,
                combined_score=round(combined_score, 6),
                doc_score=doc_scores_map[doc_id],
                tree_score=tree_score,
                sections=tr.sections,
                metadata=doc_metadata_map.get(doc_id, {}),
                confidence=assign_confidence(combined_score, "deep_search"),
            ))

        # Sort by combined score descending
        combined.sort(key=lambda r: r.combined_score, reverse=True)

        elapsed = round(time.perf_counter() - t0, 3)
        return DeepSearchResponse(
            results=combined,
            query=query,
            stage1_count=stage1_count,
            filtered_count=len(combined),
            timing=elapsed,
            strategy_used=stage1.strategy_used,
        )

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
                embed_batch_size=self._settings.ingestion.max_embedding_batch,
                additional_fields=additional_fields,
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
        return {}

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
