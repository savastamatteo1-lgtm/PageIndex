# Phase 6: Public API Wiring & Cleanup - Research

**Researched:** 2026-02-23
**Domain:** Python API integration, settings threading, legacy cleanup
**Confidence:** HIGH

## Summary

Phase 6 is a pure integration-polish phase with no new requirements -- all 19 v1 requirements are already satisfied. The work consists of 7 discrete tech debt items from the v1.0 milestone audit (ISSUE-05 through ISSUE-09 plus two additional items). Each item has a clear, localized fix in the existing codebase. No external libraries or new architecture patterns are needed.

The changes span 5 source files (`api.py`, `__init__.py`, `utils.py`, `stages.py`, `strategy.py`) plus the removal or marking of one legacy file (`page_index_md.py`). All changes are either config-threading (making existing settings flow to where they are consumed), API surface completion (adding a missing method), or cleanup (fixing docstrings, removing dead parameters, documenting legacy modules).

**Primary recommendation:** Implement all 7 items in a single plan with small, independent tasks. Each fix is self-contained and testable in isolation. The risk is low because all underlying functionality already works -- we are only wiring configuration and fixing surface-level inconsistencies.

## Standard Stack

### Core

No new libraries needed. All changes use existing project dependencies.

| Library | Version | Purpose | Already In Project |
|---------|---------|---------|-------------------|
| pydantic | 2.x | Settings model validation | Yes |
| pydantic-settings | 2.x | Layered config (env, YAML, kwargs) | Yes |
| litellm | >=2.7.0 | Provider-agnostic LLM calls | Yes |

### Supporting

No new supporting libraries required.

### Alternatives Considered

Not applicable -- this phase uses only existing infrastructure.

## Architecture Patterns

### Pattern 1: Settings Threading via Parameter Injection

**What:** Pass `PageIndexSettings` field values as explicit parameters to subsystem functions rather than having subsystems read `config.yaml` directly.

**When to use:** When a `PageIndexSettings` field exists but is not forwarded to the code that should consume it.

**Current state:** `api.py` already demonstrates this pattern for `default_top_k` and `default_strategy` -- it reads from `self._settings.retrieval` and passes to `strategy.search()`. The gap is that `rrf_k`, `engine_weights`, `global_min_score`, and `internal_fetch_multiplier` are NOT forwarded the same way.

**Two viable approaches:**

1. **Direct parameter injection** (recommended): Extend `strategy.search()` to accept optional override params (`rrf_k`, `engine_weights`, etc.) and have `api.py` pass them from `self._settings.retrieval`. Subsystem functions already accept keyword args for config overrides.

2. **Config override dict**: Pass the entire `retrieval` settings dict to `strategy.search()` which merges it with `load_retrieval_config()` defaults. This is simpler but less explicit.

**Evidence from codebase:**
```python
# Current pattern in api.py (already works for top_k):
effective_limit = limit or self._settings.retrieval.default_top_k

# strategy.py already reads from config:
cfg = load_retrieval_config()
fetch_size = limit * cfg.get("internal_fetch_multiplier", 2)
```

The cleanest approach is to have `strategy.search()` accept an optional `retrieval_config` dict override, and have `api.py` pass `self._settings.retrieval.model_dump()`. The strategy module already reads config as a dict -- this just lets the caller pre-populate it.

**Confidence:** HIGH -- pattern already proven in the codebase.

### Pattern 2: Tree-Indexing Model Override via Config Dict

**What:** Pass the `llm.completion_model` from `PageIndexSettings` into the tree-indexing config dict so `stage_tree_index()` uses the user-specified model instead of reading the top-level `model:` key from `config.yaml`.

**Current state:** In `api.py`, `_build_ingestion_config()` returns an empty dict `{}`. The `stage_tree_index()` function merges this with `ingestion_overrides` and passes it to `ConfigLoader().load(merged)`. The `ConfigLoader` reads `config.yaml` top-level keys including `model: "gemini-3.1-pro-preview"`.

**Fix:** Include `"model": self._settings.llm.completion_model` in the dict returned by `_build_ingestion_config()`. Since `ConfigLoader.load()` merges user overrides on top of YAML defaults (`{**self._default_dict, **user_dict}`), the user-provided model will take precedence.

**Evidence from codebase:**
```python
# stages.py stage_tree_index():
merged = {**config, **ingestion_overrides}
opts = ConfigLoader().load(merged)
result = page_index_main(pipeline.pdf_path, opt=opts)

# ConfigLoader.load():
merged = {**self._default_dict, **user_dict}
return config(**merged)
```

The `model` key is a valid top-level `config.yaml` key (line 2: `model: "gemini-3.1-pro-preview"`), so `ConfigLoader._validate_keys()` will accept it without error.

**Confidence:** HIGH -- direct code path analysis confirms this works.

### Pattern 3: Flat-Kwargs Constructor Support via model_validator

**What:** Allow `PageIndex(supabase_url="...", supabase_key="...")` as a convenience alternative to `PageIndex(supabase={"url": "...", "key": "..."})`.

**Current state:** `PageIndexSettings` has a `model_validator(mode="before")` that already handles flat `SUPABASE_URL`/`SUPABASE_KEY` env vars. The same approach can be extended to handle `supabase_url` and `supabase_key` kwargs.

**Two approaches:**

1. **Extend model_validator** (recommended): Add logic in `_populate_supabase_from_env` to check for `supabase_url` and `supabase_key` top-level keys in the `values` dict and restructure them into `supabase: {"url": ..., "key": ...}`.

2. **Fix docstrings only**: Remove the flat-kwargs examples from docstrings and only document the nested-dict syntax. Simpler but worse developer experience.

**The success criterion says "works correctly OR docstring updated"** -- approach 1 is strictly better because it makes the documented API work as expected.

**Confidence:** HIGH -- pydantic `model_validator(mode="before")` is the standard pattern for this.

### Anti-Patterns to Avoid

- **Breaking ConfigLoader validation:** When passing `model` in the tree-indexing config dict, ensure only valid top-level `config.yaml` keys are included. Adding `llm` or `retrieval` keys would trigger `ConfigLoader._validate_keys()` ValueError.

- **Silently dropping settings:** The current `additional_fields` parameter is an example of this anti-pattern. The fix should either wire it through or remove it to prevent user confusion.

- **Duplicating config sources:** Don't create a second config path for retrieval settings. The strategy module should accept overrides via parameters, not by having `api.py` modify `config.yaml` on disk.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Settings validation | Custom kwarg parsing | pydantic `model_validator(mode="before")` | Already in place, handles type coercion and error messages |
| Config merging | Dict merge + key validation | `ConfigLoader.load()` for tree config; dict merge for retrieval | Both patterns already proven in codebase |

**Key insight:** Every fix in this phase uses existing infrastructure. No new patterns needed.

## Common Pitfalls

### Pitfall 1: ConfigLoader Key Validation Breaks on New Keys

**What goes wrong:** `ConfigLoader._validate_keys()` raises `ValueError` if the passed dict contains keys not in `config.yaml`. This was the ISSUE-01 crash that Phase 3.1 fixed for ingestion keys.
**Why it happens:** The config dict passed to `stage_tree_index()` must only contain valid top-level `config.yaml` keys.
**How to avoid:** When building the tree config dict in `_build_ingestion_config()`, only include keys that exist in the top-level of `config.yaml`: `model`, `toc_check_page_num`, `max_page_num_each_node`, `max_token_num_each_node`, `if_add_node_id`, `if_add_node_summary`, `if_add_doc_description`, `if_add_node_text`.
**Warning signs:** `ValueError: Unknown config keys` at runtime.

### Pitfall 2: Retrieval Config Override Scope

**What goes wrong:** If the retrieval config override is applied globally (modifying the YAML-loaded dict in place), it affects all subsequent calls, not just the current PageIndex instance.
**Why it happens:** `load_retrieval_config()` reads from disk and returns a new dict each time, but if you cache or mutate the result, changes persist.
**How to avoid:** Pass config overrides as function parameters, not by modifying module-level state. The `strategy.search()` function should merge overrides with `load_retrieval_config()` result on each call.
**Warning signs:** Settings from one `PageIndex` instance leaking to another.

### Pitfall 3: additional_fields Wiring Requires Pipeline Signature Change

**What goes wrong:** `process_single_document()` does not have an `additional_fields` parameter. Adding it requires changes to both `stages.py` and `api.py`.
**Why it happens:** The parameter was added to `PageIndex.ingest()` but never propagated.
**How to avoid:** Either wire it through (add param to `process_single_document()`, call `update_document()` with it after `insert_document()`), or remove it from `ingest()` signature. Removing is simpler and avoids user confusion. The `additional_fields` JSONB column can be populated via direct DB operations for power users.
**Warning signs:** Users passing `additional_fields` and finding them silently ignored.

### Pitfall 4: page_index_md.py Wild Import

**What goes wrong:** `page_index_md.py` line 7 has `from .utils import *` -- removing or modifying this file could break test imports if tests import from `page_index_md`.
**Why it happens:** Legacy file predating the PageIndex class API.
**How to avoid:** Check for imports of `page_index_md` across the codebase before removing. If used only as a `__main__` script, it can be safely deleted. If imported elsewhere, add a deprecation docstring instead.
**Warning signs:** `ImportError` after removal.

## Code Examples

### Fix 1: Flat-kwargs support in PageIndexSettings

```python
# In PageIndexSettings._populate_supabase_from_env (api.py):
@model_validator(mode="before")
@classmethod
def _populate_supabase_from_env(cls, values: dict) -> dict:
    # Handle flat kwargs: supabase_url, supabase_key
    flat_url = values.pop("supabase_url", None)
    flat_key = values.pop("supabase_key", None)

    supabase = values.get("supabase")

    if isinstance(supabase, dict):
        if "url" not in supabase and flat_url:
            supabase["url"] = flat_url
        if "key" not in supabase and flat_key:
            supabase["key"] = flat_key
    elif supabase is None:
        sb = {}
        if flat_url:
            sb["url"] = flat_url
        if flat_key:
            sb["key"] = flat_key
        # ... also check env vars (existing logic) ...
```

### Fix 2: Retrieval config threading

```python
# In strategy.py search():
def search(
    query: str,
    strategy: str = "auto",
    limit: int | None = None,
    model: str | None = None,
    retrieval_overrides: dict | None = None,  # NEW
) -> SearchResponse:
    cfg = load_retrieval_config()
    if retrieval_overrides:
        cfg.update(retrieval_overrides)
    # ... rest of function uses cfg as before ...

# In api.py search():
internal = strategy_search(
    query,
    strategy=strategy,
    limit=effective_limit,
    retrieval_overrides=self._settings.retrieval.model_dump(),  # NEW
)
```

### Fix 3: Tree-indexing model override

```python
# In api.py _build_ingestion_config():
def _build_ingestion_config(self) -> dict:
    return {"model": self._settings.llm.completion_model}
```

### Fix 4: search_description on PageIndex

```python
# In api.py PageIndex class:
def search_description(
    self, query: str, *, limit: int | None = None
) -> list:
    from pageindex.exceptions import SearchError
    from pageindex.retrieval.description import search_description as _search_desc

    effective_limit = limit or self._settings.retrieval.default_top_k
    try:
        return _search_desc(query, limit=effective_limit)
    except Exception as exc:
        raise SearchError(f"Description search failed: {exc}") from exc
```

### Fix 5: max_embedding_batch threading

```python
# In stages.py stage_embed(), replace hardcoded _EMBED_BATCH_SIZE usage:
def stage_embed(
    pipeline: DocumentPipeline,
    llm_provider: LLMProvider,
    embed_batch_size: int = 250,  # NEW parameter
) -> None:
    # ... existing code ...
    for i in range(0, len(embedding_texts), embed_batch_size):  # was _EMBED_BATCH_SIZE
        batch = embedding_texts[i : i + embed_batch_size]

# In api.py ingest(), pass the setting:
pipeline = process_single_document(
    pdf_path=path,
    llm_provider=get_provider(),
    config=config,
    metadata_pages=self._settings.ingestion.metadata_pages,
    chunk_max_tokens=self._settings.ingestion.chunk_max_tokens,
    chunk_overlap=self._settings.ingestion.chunk_overlap,
    max_embedding_batch=self._settings.ingestion.max_embedding_batch,  # NEW
)
```

### Fix 6: additional_fields decision

```python
# Option A (recommended): Remove parameter, simplify signature
def ingest(
    self,
    *,
    path: str | None = None,
    text: str | None = None,
    url: str | None = None,
    # additional_fields removed -- use update_document() for custom fields
) -> IngestionResult:

# Option B: Wire through to pipeline
pipeline = process_single_document(
    pdf_path=path,
    ...,
    additional_fields=additional_fields,  # needs signature change in stages.py
)
```

### Fix 7: page_index_md.py cleanup

```python
# Add deprecation docstring at top of page_index_md.py:
"""INTERNAL LEGACY MODULE -- Markdown-based tree indexer.

.. deprecated::
    This module is a legacy implementation for Markdown files.
    New code should use :class:`pageindex.PageIndex` for PDF ingestion
    and retrieval. This module is not part of the public API.
"""
```

## State of the Art

Not applicable -- this phase involves no new technology decisions. All changes use patterns already established in the codebase.

## Codebase Analysis: Issue-by-Issue Breakdown

### ISSUE-05: Constructor flat-kwargs (Success Criterion 1)

**Files affected:** `pageindex/api.py` (model_validator), `pageindex/__init__.py` (docstring), `pageindex/utils.py` (docstring)

**Current state:** `PageIndexSettings._populate_supabase_from_env` handles env vars (`SUPABASE_URL`, `SUPABASE_KEY`) but not kwargs (`supabase_url`, `supabase_key`). The `__init__.py` and `utils.py` docstrings show the flat-kwargs form.

**Fix scope:** Add `supabase_url`/`supabase_key` handling in the model_validator. Also update docstrings to show both forms.

**Lines to modify:**
- `api.py:134-167` -- extend model_validator
- `__init__.py:7` -- fix docstring example
- `utils.py:11` -- fix docstring example

### ISSUE-06: RetrievalSettings fields not wired (Success Criterion 2)

**Files affected:** `pageindex/api.py` (search method), `pageindex/retrieval/strategy.py` (search function)

**Current state:** `strategy.search()` reads config from `load_retrieval_config()` which reads `config.yaml`. The `PageIndexSettings.retrieval` fields are never passed to `strategy.search()`.

**Fix scope:** Add `retrieval_overrides` parameter to `strategy.search()` and pass settings from `api.py`.

**Lines to modify:**
- `api.py:396-401` -- pass overrides to strategy_search
- `strategy.py:360-438` -- accept and merge overrides
- `strategy.py:293-352` -- `_run_hybrid` uses `cfg` dict which will now include overrides

### ISSUE-07: Tree-indexing model bypass (Success Criterion 3)

**Files affected:** `pageindex/api.py` (`_build_ingestion_config`)

**Current state:** `_build_ingestion_config()` returns `{}`. The `ConfigLoader` fills in `model` from `config.yaml` top-level `model: "gemini-3.1-pro-preview"`.

**Fix scope:** Return `{"model": self._settings.llm.completion_model}` from `_build_ingestion_config()`.

**Lines to modify:**
- `api.py:583-592` -- single line change in `_build_ingestion_config`

### ISSUE-08: search_description not on PageIndex (Success Criterion 4)

**Files affected:** `pageindex/api.py`

**Current state:** `PageIndex` has `search_semantic()`, `search_metadata()`, `search_tree()` but no `search_description()`.

**Fix scope:** Add `search_description()` method following the exact same pattern as the other three.

**Lines to modify:**
- `api.py` -- add new method after `search_tree()` (around line 499)

### ISSUE-09: max_embedding_batch hardcoded (Success Criterion 5)

**Files affected:** `pageindex/ingestion/stages.py`, `pageindex/api.py`

**Current state:** `_EMBED_BATCH_SIZE = 250` is hardcoded at `stages.py:232`. `IngestionSettings.max_embedding_batch` exists but is never read by `stage_embed()`.

**Fix scope:** Add `embed_batch_size` parameter to `stage_embed()` and `process_single_document()`. Pass value from `api.py`.

**Lines to modify:**
- `stages.py:232` -- keep constant as default
- `stages.py:242-327` -- add parameter to `stage_embed()`
- `stages.py:401-469` -- add parameter to `process_single_document()`, pass to `stage_embed()`
- `api.py:561-572` -- pass `max_embedding_batch` setting

### Tech Debt: additional_fields silently dropped (Success Criterion 6)

**Files affected:** `pageindex/api.py`

**Current state:** `ingest()` accepts `additional_fields` parameter but never passes it to `process_single_document()`. The DB layer (`documents.py`) supports `additional_fields` in `_METADATA_COLUMNS`.

**Recommended fix:** Wire it through. Add `additional_fields` param to `process_single_document()`, then call `update_document(pipeline.doc_id, {"additional_fields": additional_fields})` after the initial `insert_document()` or include it in the insert call. Alternatively, remove the param if the feature is not needed.

**Lines to modify (if wiring):**
- `stages.py:401-469` -- add `additional_fields` param to `process_single_document()`
- `stages.py:448` -- include in `insert_document()` metadata dict
- `api.py:565` -- pass `additional_fields` to `process_single_document()`

**Lines to modify (if removing):**
- `api.py:511` -- remove from `ingest()` signature
- `api.py:525-529` -- remove from docstring

### Tech Debt: page_index_md.py orphan (Success Criterion 7)

**Files affected:** `pageindex/page_index_md.py`

**Current state:** 338-line legacy file for Markdown-based tree indexing. Uses `from .utils import *` wild import. Has a `__main__` block. Not imported by any other module in the pipeline.

**Fix scope:** Either delete the file or add a deprecation docstring marking it as internal/legacy.

**Removal safety check needed:** Verify no imports of `page_index_md` exist in the project outside the file itself.

## Open Questions

1. **additional_fields: wire or remove?**
   - What we know: The param exists in `ingest()`, the DB column exists, but nothing connects them.
   - What's unclear: Whether users need this feature in v1 or if it can wait for v2.
   - Recommendation: Wire it through -- the implementation is simple (add to `insert_document()` call) and the column already exists. Removing a documented parameter is a worse developer experience than wiring an existing one.

2. **page_index_md.py: delete or deprecation notice?**
   - What we know: The file is not imported by any pipeline code. It has a `__main__` block for standalone use.
   - What's unclear: Whether any external users depend on `from pageindex.page_index_md import md_to_tree`.
   - Recommendation: Add deprecation docstring rather than deleting. This is safer for any external users and the file is harmless as-is. The success criterion says "removed OR documented as internal legacy."

3. **Should batch `ingest()` in pipeline.py also get the retrieval/model threading?**
   - What we know: `pipeline.py:ingest()` uses `get_provider()` singleton which is already reset by `PageIndex._init_subsystems()`. Tree config is hardcoded in pipeline.py line 226-230.
   - What's unclear: Whether pipeline.py batch ingestion should also support model override.
   - Recommendation: Out of scope for Phase 6. The `pipeline.py:ingest()` is a lower-level function for batch processing -- users who need model override can use `PageIndex.ingest()` which calls `process_single_document()` directly and will get the fix.

## Sources

### Primary (HIGH confidence)

- Direct codebase analysis of all affected files (read and analyzed in this research session)
- `v1.0-MILESTONE-AUDIT.md` -- definitive list of 7 tech debt items
- `ROADMAP.md` Phase 6 -- success criteria and scope definition
- `STATE.md` -- accumulated decisions and patterns from Phases 1-5

### Secondary (MEDIUM confidence)

- pydantic v2 `model_validator` behavior -- verified against training knowledge but not against Context7 (standard, well-documented feature)

### Tertiary (LOW confidence)

None -- all findings based on direct codebase analysis.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, all existing infrastructure
- Architecture: HIGH -- patterns directly observed in codebase, fixes are localized
- Pitfalls: HIGH -- pitfalls identified from past issues (ISSUE-01 in Phase 3.1) and code analysis

**Research date:** 2026-02-23
**Valid until:** Indefinite (internal codebase analysis, not dependent on external library versions)
