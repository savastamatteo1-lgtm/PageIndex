# Phase 5: Public API - Research

**Researched:** 2026-02-23
**Domain:** Python library API design, pydantic-settings configuration, package re-exports
**Confidence:** HIGH

## Summary

Phase 5 wraps the existing ingestion pipeline (`pageindex.ingestion.ingest()`), strategy dispatcher (`pageindex.retrieval.search()`), and DB layer (`pageindex.db`) into a single `PageIndex` class that holds config and connection state. The scope is a refactor/façade layer, NOT building new retrieval or ingestion logic. All underlying subsystems already work end-to-end from Phase 1-4.

The primary technical challenge is integrating pydantic-settings for layered configuration (constructor kwargs > env vars > config file) while replacing the existing `ConfigLoader` (SimpleNamespace-based) and the three separate `load_*_config()` functions that each independently read `config.yaml`. The `PageIndex` class becomes the owner of configuration and passes it down to subsystems rather than each subsystem loading its own config file.

**Primary recommendation:** Build a `PageIndexSettings` pydantic-settings model with nested sub-models (llm, supabase, ingestion, retrieval) that replaces the scattered YAML-based config loaders, then implement a `PageIndex` class whose methods delegate to existing functions with the resolved config.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Class-based API: `pi = PageIndex(...)` — single entry point, holds state (DB connections, config, LLM clients)
- Class name is `PageIndex` — matches the package name
- `pi.search(query)` for fused multi-strategy search (uses strategy dispatcher with auto-routing)
- Individual strategy methods also exposed: `pi.search_semantic(query)`, `pi.search_metadata(query)`, `pi.search_tree(query)` for direct access
- `pi.ingest()` accepts both file path (`path='/path/to/doc.md'`) and raw text (`text='...', url='source-url'`)
- `pi.retrieve()` for fetching specific sections/documents
- Use **pydantic-settings** for layered config resolution: constructor kwargs > environment variables > config file
- Environment variable prefix: `PAGEINDEX_` (e.g., `PAGEINDEX_SUPABASE_URL`, `PAGEINDEX_LLM_PROVIDER`)
- Constructor accepts both individual kwargs (`PageIndex(supabase_url='...')`) and a settings object (`PageIndex(settings=MySettings(...))`) — kwargs build a Settings object internally
- If no config is provided at all, **fail immediately** with a clear `ConfigError` listing exactly what's missing — no auto-discovery of config files
- `search()` returns a typed `SearchResponse` dataclass with `.results`, `.query`, `.strategy_used`, `.scores`, `.timing` — transparent and debuggable
- `ingest()` returns an `IngestionResult` dataclass with `.document_id`, `.chunks_created`, `.status`
- Custom exception hierarchy: `PageIndexError` base, with `ConfigError`, `IngestionError`, `SearchError` subtypes — catchable by type
- Search results include raw scores and strategy metadata, not just final ranked results
- `from pageindex import PageIndex, SearchResponse, IngestionResult` — main class plus public types
- Subsystem modules (`pageindex.retrieval`, `pageindex.ingestion`) remain accessible as submodules but are NOT re-exported at top level
- **Clean all legacy**: remove `llm_complete()`/`llm_embed()` aliases from utils.py, old function-based API (`tree_indexer`, etc.), and any unused exports
- **Replace, don't wrap**: the `PageIndex` class replaces the existing function-based logic in `page_index.py` rather than wrapping it
- `run_pageindex.py` migrated to use the new `PageIndex` class — serves as both a usage example and API validation
- Wire `additional_fields` JSONB overflow bucket in ingestion or document it as reserved

### Claude's Discretion
- Internal method organization within the PageIndex class
- Exact pydantic-settings model field names and validation rules
- Whether `retrieve()` takes document_id, URL, or both
- Logging strategy and verbosity
- Exact fields on IngestionResult beyond the confirmed ones

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FOUND-05 | System exposes a Python library API for programmatic integration (`ingest`, `search`, `retrieve` as core operations) | The `PageIndex` class wraps existing `pageindex.ingestion.ingest()`, `pageindex.retrieval.search()`, and `pageindex.db` functions. All underlying capabilities exist. pydantic-settings provides layered config. Custom exception hierarchy and typed return types provide clean API surface. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic-settings | >=2.7.0 | Layered config: env vars + YAML + kwargs | Official Pydantic companion for settings management; supports `YamlConfigSettingsSource`, nested models, `env_prefix`, and custom source priority |
| pydantic | >=2.10.0 | Validation for settings sub-models | Transitive dependency of pydantic-settings; used for nested BaseModel sub-configs |
| pyyaml | 6.0.2 (already installed) | YAML config file parsing | Required by `YamlConfigSettingsSource`; already a project dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| stdlib dataclasses | N/A | Return types (SearchResponse, IngestionResult) | Already used for retrieval models (Phase 3-4); keep for consistency |
| typing | N/A | Type annotations | For overloaded signatures and Union types |
| time | N/A | Timing measurement for SearchResponse.timing | For `search()` elapsed time tracking |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pydantic-settings | dynaconf | More features (multiple environments, Redis/Vault), but heavier; user locked pydantic-settings |
| pydantic-settings | python-decouple | Simpler env-only config; no YAML source or nested validation |
| dataclasses for returns | pydantic BaseModel | Would add validation on return types, but project convention is stdlib dataclasses (Phase 3 decision 03-01) |

**Installation:**
```bash
pip install pydantic-settings>=2.7.0
```
Note: `pydantic` is pulled in transitively. `pyyaml` is already installed.

## Architecture Patterns

### Recommended Project Structure
```
pageindex/
├── __init__.py            # Re-exports: PageIndex, SearchResponse, IngestionResult, exceptions
├── api.py                 # NEW: PageIndex class, PageIndexSettings, return types
├── exceptions.py          # NEW: PageIndexError, ConfigError, IngestionError, SearchError
├── config.yaml            # EXISTING: default configuration values
├── utils.py               # EXISTING: cleaned of llm_complete/llm_embed aliases
├── page_index.py          # EXISTING: tree indexing (still used internally by ingestion)
├── page_index_md.py       # EXISTING: markdown tree indexing
├── db/                    # EXISTING: database layer (unchanged)
├── llm/                   # EXISTING: LLM provider layer (unchanged internally)
├── ingestion/             # EXISTING: ingestion pipeline (unchanged internally)
└── retrieval/             # EXISTING: retrieval engines + strategy dispatcher (unchanged internally)
```

### Pattern 1: pydantic-settings with YAML Source and Custom Priority
**What:** Define `PageIndexSettings(BaseSettings)` with nested sub-models, YAML file source, and custom source priority (init kwargs > env vars > YAML file > defaults).
**When to use:** Always — this is the locked decision for config handling.
**Example:**
```python
# Source: Context7 /pydantic/pydantic-settings — verified HIGH confidence
from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class LLMSettings(BaseModel):
    completion_model: str = "gemini/gemini-2.0-flash"
    embedding_model: str = "gemini/gemini-embedding-001"
    embedding_dimensions: int = 768
    temperature: float = 0


class SupabaseSettings(BaseModel):
    url: str  # No default — MUST be provided
    key: str  # No default — MUST be provided


class IngestionSettings(BaseModel):
    metadata_pages: int = 3
    chunk_max_tokens: int = 800
    chunk_overlap: float = 0.1
    max_workers: int = 1
    max_embedding_batch: int = 250


class RetrievalSettings(BaseModel):
    default_top_k: int = 10
    default_strategy: str = "auto"
    # ... remaining retrieval config fields


class PageIndexSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PAGEINDEX_",
        env_nested_delimiter="__",
        yaml_file="pageindex/config.yaml",  # Or None if user doesn't provide
        yaml_file_encoding="utf-8",
        extra="ignore",
    )

    supabase: SupabaseSettings
    llm: LLMSettings = LLMSettings()
    ingestion: IngestionSettings = IngestionSettings()
    retrieval: RetrievalSettings = RetrievalSettings()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Priority: init kwargs > env vars > YAML config file
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls),
        )
```

### Pattern 2: PageIndex Class as Facade
**What:** Single class that owns settings, initializes subsystems lazily, and delegates to existing functions.
**When to use:** This IS the public API.
**Example:**
```python
import time
from dataclasses import dataclass, field

class PageIndex:
    def __init__(self, *, settings: PageIndexSettings | None = None, **kwargs):
        if settings is not None:
            self._settings = settings
        else:
            # Build settings from kwargs — pydantic-settings validates
            try:
                self._settings = PageIndexSettings(**kwargs)
            except ValidationError as e:
                raise ConfigError(str(e)) from e

        # Initialize subsystems
        self._init_db()
        self._init_llm()

    def search(self, query: str, strategy: str = "auto", limit: int | None = None) -> SearchResponse:
        start = time.perf_counter()
        raw = retrieval_search(query, strategy=strategy, limit=limit)
        elapsed = time.perf_counter() - start
        return SearchResponse(
            results=raw.results,
            query=query,
            strategy_used=raw.strategy,
            scores={...},
            timing=elapsed,
        )

    def ingest(self, *, path: str | None = None, text: str | None = None, url: str | None = None) -> IngestionResult:
        ...

    def retrieve(self, doc_id: str) -> ...:
        ...
```

### Pattern 3: Custom Exception Hierarchy
**What:** Base exception + typed subtypes for different failure modes.
**When to use:** All public API error paths.
**Example:**
```python
class PageIndexError(Exception):
    """Base exception for all PageIndex errors."""

class ConfigError(PageIndexError):
    """Raised when configuration is invalid or missing."""

class IngestionError(PageIndexError):
    """Raised when document ingestion fails."""

class SearchError(PageIndexError):
    """Raised when a search operation fails."""
```

### Anti-Patterns to Avoid
- **Wrapping instead of replacing:** CONTEXT says "replace, don't wrap." The `PageIndex` class should not delegate to the old `page_index()` function call from `page_index.py`. Ingestion already has its own pipeline — `PageIndex.ingest()` should call `pageindex.ingestion.ingest()` or `process_single_document()` directly.
- **Leaking config loaders:** With `PageIndexSettings` as the single config owner, the existing `load_llm_config()`, `load_retrieval_config()`, and `load_ingestion_config()` should either accept settings objects or be wired to use the PageIndex instance's settings. Do NOT leave two parallel config paths.
- **Importing everything at package level:** Only import `PageIndex`, `SearchResponse`, `IngestionResult`, and exceptions in `__init__.py`. Subsystem internals stay as submodule imports.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Layered config (env + file + kwargs) | Custom config merger with priority logic | pydantic-settings `BaseSettings` with `settings_customise_sources` | Handles type coercion, nested env vars, validation, error messages for free |
| Env var parsing with prefixes | Custom `os.environ.get()` calls with prefix logic | `SettingsConfigDict(env_prefix="PAGEINDEX_")` | Handles nested delimiter, type parsing, optional/required fields automatically |
| YAML config loading | Custom YAML reader + dict merge | `YamlConfigSettingsSource` | Built-in pydantic-settings source; handles nested structures correctly |
| Config validation errors | Custom error messages for missing fields | pydantic ValidationError caught and re-raised as ConfigError | Pydantic produces detailed error messages listing ALL missing/invalid fields at once |

**Key insight:** pydantic-settings does ALL the config work — env var parsing, YAML loading, type validation, nested model construction, priority ordering. The only custom code needed is the `settings_customise_sources` override to set priority order and the `ConfigError` wrapper for user-friendly messages.

## Common Pitfalls

### Pitfall 1: Dual Config Paths
**What goes wrong:** The existing codebase has three separate `load_*_config()` functions (in `llm/config.py`, `ingestion/pipeline.py`, `retrieval/config.py`), each independently reading `config.yaml`. If the `PageIndex` class introduces a fourth config path via pydantic-settings while the old loaders still exist, config changes won't propagate consistently.
**Why it happens:** Natural to "just add" the new config path without updating existing ones.
**How to avoid:** The `PageIndex` class must pass its resolved settings DOWN to subsystems. Either (a) modify `search()`, `ingest()`, etc. to accept config parameters, or (b) have `PageIndex.__init__()` set module-level state (like replacing the `_provider_instance` singleton in `llm/provider.py`) so existing config loaders are bypassed.
**Warning signs:** Tests pass with env vars but fail when using constructor kwargs, or vice versa.

### Pitfall 2: Supabase Client Singleton Conflicts
**What goes wrong:** `pageindex.db.client.get_client()` currently reads `SUPABASE_URL` and `SUPABASE_KEY` directly from `os.environ`. If the user provides these via constructor kwargs (`PageIndex(supabase_url='...')`), the singleton won't pick them up.
**Why it happens:** The singleton pattern in `db/client.py` caches the first client created. Constructor-provided URLs arrive after the module-level singleton may already be initialized.
**How to avoid:** Either (a) have `PageIndex.__init__()` set `os.environ` from the resolved settings before any DB access, or (b) modify `get_client()` to accept optional URL/key params and reset the singleton when new values are provided. Option (a) is simpler and doesn't change the DB layer contract.
**Warning signs:** Second `PageIndex` instance with different Supabase URL still uses the first URL.

### Pitfall 3: Breaking tree_indexer Internals
**What goes wrong:** The CONTEXT says "clean all legacy" and "replace, don't wrap." But `page_index.py` functions (`page_index_main`, `tree_parser`, etc.) are still NEEDED by the ingestion pipeline (`stages.py` calls `page_index_main`). Aggressively cleaning `page_index.py` would break ingestion.
**Why it happens:** Misreading "replace" as "delete." The old *public API surface* (`page_index()` function, star exports from `__init__.py`) is what gets replaced. Internal machinery stays.
**How to avoid:** Only remove the public-facing function `page_index()` at the bottom of `page_index.py` and the star-import in `__init__.py`. Keep `page_index_main()` as an internal function since the ingestion pipeline depends on it. Remove `llm_complete()` and `llm_embed()` from `utils.py` — these are unused aliases.
**Warning signs:** `ImportError` from `pageindex.ingestion.stages` after cleanup.

### Pitfall 4: pydantic-settings env_nested_delimiter with Supabase Fields
**What goes wrong:** With `env_prefix="PAGEINDEX_"` and `env_nested_delimiter="__"`, the env var for `supabase.url` becomes `PAGEINDEX_SUPABASE__URL` (double underscore). Users expect `PAGEINDEX_SUPABASE_URL` (single underscore).
**Why it happens:** The delimiter `__` splits `SUPABASE__URL` into `supabase.url`, but `SUPABASE_URL` would be interpreted as a top-level field `supabase_url`.
**How to avoid:** Use `validation_alias` or `AliasChoices` on the nested fields to accept both `PAGEINDEX_SUPABASE_URL` (flat) and `PAGEINDEX_SUPABASE__URL` (nested). Alternatively, use `env_nested_delimiter="__"` consistently and document that nested env vars use double underscore. The simpler approach: keep Supabase URL/key as top-level fields in settings (not nested), since they're the most commonly set env vars.
**Warning signs:** Users set `PAGEINDEX_SUPABASE_URL` and get a validation error about missing `supabase.url`.

### Pitfall 5: SearchResponse Field Naming Mismatch
**What goes wrong:** The CONTEXT specifies `SearchResponse` with `.strategy_used` and `.timing`, but the existing `pageindex.retrieval.models.SearchResponse` has `.strategy` and no `.timing`. If the public API uses the same class name with different fields, imports become ambiguous.
**Why it happens:** The CONTEXT describes the *public API* return type; the existing `SearchResponse` is an internal type.
**How to avoid:** Create a NEW `SearchResponse` in `api.py` (or rename the public one to avoid collision). The public `SearchResponse` wraps the internal one and adds `.query`, `.timing`, and renames `.strategy` to `.strategy_used`. Keep the internal `retrieval.models.SearchResponse` unchanged to avoid breaking retrieval internals.
**Warning signs:** Import conflicts between `pageindex.SearchResponse` and `pageindex.retrieval.models.SearchResponse`.

### Pitfall 6: additional_fields JSONB Not Wired in Ingestion
**What goes wrong:** The `additional_fields` JSONB column exists in the schema (migration 001) and is listed in `_METADATA_COLUMNS` in `documents.py`, but the ingestion pipeline (`stages.py`) never populates it. The CONTEXT says "wire it or document as reserved."
**Why it happens:** The column was designed as a future overflow bucket but was never integrated into the metadata extraction LLM prompt.
**How to avoid:** For this phase, document it as reserved with a clear docstring/comment. The column is available for user-provided extra metadata via `PageIndex.ingest(additional_fields={...})` but NOT auto-extracted by the LLM pipeline. This is the simpler path — wiring it into LLM extraction would require prompt changes in the ingestion module.
**Warning signs:** User passes `additional_fields` to `ingest()` but it silently gets dropped.

## Code Examples

Verified patterns from official sources:

### pydantic-settings YAML Source with Custom Priority
```python
# Source: Context7 /pydantic/pydantic-settings — verified HIGH confidence
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        yaml_file='config.yaml',
        yaml_file_encoding='utf-8',
        env_prefix='PAGEINDEX_',
        env_nested_delimiter='__',
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,       # 1st priority: constructor kwargs
            env_settings,        # 2nd priority: environment variables
            YamlConfigSettingsSource(settings_cls),  # 3rd priority: YAML file
        )
```

### pydantic-settings Nested Environment Variables
```python
# Source: Context7 /pydantic/pydantic-settings — verified HIGH confidence
import os
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

class LLMConfig(BaseModel):
    completion_model: str = "gemini/gemini-2.0-flash"
    embedding_model: str = "gemini/gemini-embedding-001"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix='PAGEINDEX_',
        env_nested_delimiter='__',
    )
    llm: LLMConfig = LLMConfig()

# Set env var: PAGEINDEX_LLM__COMPLETION_MODEL=openai/gpt-4o
os.environ['PAGEINDEX_LLM__COMPLETION_MODEL'] = 'openai/gpt-4o'
settings = Settings()
print(settings.llm.completion_model)  # Output: openai/gpt-4o
```

### Fail-Fast Config Validation
```python
# Application pattern — not from external source
from pydantic import ValidationError

class PageIndex:
    def __init__(self, *, settings=None, **kwargs):
        try:
            if settings is not None:
                self._settings = settings
            else:
                self._settings = PageIndexSettings(**kwargs)
        except ValidationError as e:
            # Extract missing field names for a clear error message
            missing = [err['loc'] for err in e.errors() if err['type'] == 'missing']
            raise ConfigError(
                f"Missing required configuration: {missing}. "
                "Provide via constructor kwargs or PAGEINDEX_* environment variables."
            ) from e
```

### Timing Wrapper for Search
```python
# Application pattern
import time
from dataclasses import dataclass

@dataclass
class SearchResponse:
    results: list
    query: str
    strategy_used: str
    scores: dict
    timing: float  # seconds

def search(self, query, strategy="auto", limit=None):
    start = time.perf_counter()
    raw = retrieval_search(query, strategy=strategy, limit=limit)
    elapsed = time.perf_counter() - start
    return SearchResponse(
        results=raw.results,
        query=query,
        strategy_used=raw.strategy,
        scores={"engine_gaps": raw.engine_gaps},
        timing=round(elapsed, 3),
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `ConfigLoader` + `SimpleNamespace` | pydantic-settings `BaseSettings` with YAML source | pydantic-settings 2.0+ (2023) | Type-safe config with env var parsing, validation, nested models |
| Manual `os.environ.get()` for each var | `env_prefix` + `env_nested_delimiter` | pydantic-settings 2.0+ | Single declaration covers all env vars automatically |
| Separate `load_*_config()` per subsystem | Unified settings model passed from API class | This phase | Single source of truth for all configuration |
| Star imports (`from .page_index import *`) | Explicit `__all__` with named exports | Python packaging best practice | Predictable public API surface |

**Deprecated/outdated:**
- `llm_complete()` / `llm_embed()` in utils.py: Unused aliases that were "recommended for new code" but never adopted by any module. Safe to remove.
- `config` alias (SimpleNamespace): Imported at top of utils.py as `from types import SimpleNamespace as config`. Used only by `ConfigLoader`. Will be replaced by pydantic-settings.
- `ChatGPT_API` / `ChatGPT_API_async` aliases: These are aliases for `Gemini_API` / `Gemini_API_async` used by `page_index.py` internally. Must NOT be removed since `page_index.py` tree-indexing functions reference them and are still called by ingestion.

## Existing Codebase Inventory (Critical for Planning)

### What the PageIndex Class Must Wrap

| Operation | Existing Function | Location | Interface |
|-----------|-------------------|----------|-----------|
| search (fused) | `search()` | `pageindex/retrieval/strategy.py` | `search(query, strategy, limit, model) -> SearchResponse` |
| search_semantic | `search_semantic()` | `pageindex/retrieval/semantic.py` | `search_semantic(query, limit, query_embedding) -> list[SemanticResult]` |
| search_metadata | `search_metadata()` | `pageindex/retrieval/metadata.py` | `search_metadata(query, limit, model) -> list[MetadataResult]` |
| search_tree | `tree_search_sync()` | `pageindex/retrieval/tree_search.py` | `tree_search_sync(doc_ids, query, model) -> list[TreeSearchResult]` |
| ingest (directory) | `ingest()` | `pageindex/ingestion/pipeline.py` | `ingest(directory, max_workers, ...) -> dict` |
| ingest (single) | `process_single_document()` | `pageindex/ingestion/stages.py` | `process_single_document(pdf_path, llm_provider, config, ...) -> DocumentPipeline` |
| retrieve (document) | `get_document()` | `pageindex/db/documents.py` | `get_document(doc_id) -> dict \| None` |
| retrieve (tree) | `get_tree()` | `pageindex/db/trees.py` | `get_tree(doc_id) -> dict \| None` |
| retrieve (chunks) | `get_chunks_by_doc()` | `pageindex/db/chunks.py` | `get_chunks_by_doc(doc_id) -> list[dict]` |
| list documents | `list_documents()` | `pageindex/db/documents.py` | `list_documents(limit, offset) -> list[dict]` |

### Singletons That Need Wiring

| Singleton | Location | Current Init | PageIndex Wiring |
|-----------|----------|--------------|------------------|
| Supabase client | `db/client.py` | `os.environ["SUPABASE_URL"]` + `os.environ["SUPABASE_KEY"]` | Set env vars from settings before first DB access |
| LLM provider | `llm/provider.py` | `_provider_instance` from `load_llm_config()` reading `config.yaml` | Replace singleton with instance built from `PageIndexSettings.llm` |
| Gemini client | `utils.py` | `genai.Client(api_key=GOOGLE_API_KEY)` at module import | Still needed for tree indexing; `GOOGLE_API_KEY` env var must be set |

### Files That Need Cleanup

| File | What to Remove | What to Keep |
|------|----------------|--------------|
| `utils.py` | `llm_complete()`, `llm_embed()` functions | Everything else (tree indexing helpers, `ConfigLoader`, legacy LLM functions used by `page_index.py`) |
| `__init__.py` | `from .page_index import *`, `from .page_index_md import md_to_tree` | New explicit exports: `PageIndex`, `SearchResponse`, `IngestionResult`, exceptions |
| `run_pageindex.py` | Current `from pageindex import *` and `config(...)` usage | Rewrite using `PageIndex(...)` class |

### additional_fields Status

The `additional_fields` JSONB column:
- **Schema:** Exists in `documents` table (migration 001), default `'{}'::jsonb`
- **DB layer:** Listed in `_METADATA_COLUMNS` in `documents.py` — accepted by `insert_document()` and `update_document()`
- **Ingestion pipeline:** NOT populated — `stages.py` never passes `additional_fields` to the DB
- **Recommendation:** Accept it as an optional parameter in `PageIndex.ingest()` and pass through to the DB. Document it as a user-provided overflow bucket, not auto-extracted by the LLM.

## Open Questions

1. **Config file path resolution**
   - What we know: pydantic-settings `YamlConfigSettingsSource` needs a file path; current code uses `Path(__file__).parent / "config.yaml"` (relative to package)
   - What's unclear: Should the public API accept a config file path parameter? The CONTEXT says "fail immediately if no config" but doesn't specify how the YAML file is located
   - Recommendation: Default to the package-bundled `config.yaml` for defaults. Accept optional `config_path` kwarg in `PageIndex()` constructor. If user provides no config at all and required fields (supabase URL/key) are missing, fail with ConfigError.

2. **retrieve() method scope**
   - What we know: CONTEXT says `pi.retrieve()` for "fetching specific sections/documents." Claude's discretion on whether it takes doc_id, URL, or both.
   - What's unclear: Should it return document metadata, tree structure, chunks, or all of the above?
   - Recommendation: `retrieve(doc_id)` returns a combined view: document metadata + tree structure + optionally chunks. This covers the "get me everything about document X" use case. Could also support `retrieve(doc_name=...)` by name lookup.

3. **SearchResponse naming collision**
   - What we know: Internal `pageindex.retrieval.models.SearchResponse` has `.strategy` and `.results`. Public API needs `.query`, `.strategy_used`, `.timing`.
   - What's unclear: Should we rename the internal type or create a new public type?
   - Recommendation: Create a new public `SearchResponse` in `api.py` that wraps/extends the internal one. Import the internal one as `_InternalSearchResponse` where needed. The public type lives at `pageindex.SearchResponse` via `__init__.py`.

## Sources

### Primary (HIGH confidence)
- Context7 `/pydantic/pydantic-settings` — YAML source configuration, custom source priority, nested env vars, `SettingsConfigDict` options
- Direct codebase inspection of all files in `pageindex/` package — verified interfaces, singletons, imports, and dependencies

### Secondary (MEDIUM confidence)
- pydantic-settings documentation patterns for `settings_customise_sources` override
- Python packaging best practices for `__init__.py` explicit exports

### Tertiary (LOW confidence)
- None — all findings verified from primary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pydantic-settings is a locked user decision; verified with Context7
- Architecture: HIGH — all existing subsystem interfaces inspected directly in codebase
- Pitfalls: HIGH — identified from actual codebase analysis (singleton patterns, naming collisions, import chains)

**Research date:** 2026-02-23
**Valid until:** 2026-03-23 (stable domain; no fast-moving external dependencies)
