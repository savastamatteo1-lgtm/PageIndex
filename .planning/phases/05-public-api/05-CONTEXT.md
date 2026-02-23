# Phase 5: Public API - Context

**Gathered:** 2026-02-23
**Status:** Ready for planning

<domain>
## Phase Boundary

A clean Python library API that exposes all PageIndex capabilities (`ingest`, `search`, `retrieve`) through a typed `PageIndex` class importable from the `pageindex` package. A new user can install, configure, ingest a document, and search with fewer than 10 lines of Python. Includes tech debt cleanup of legacy function-based API and unused aliases.

</domain>

<decisions>
## Implementation Decisions

### API Surface Design
- Class-based API: `pi = PageIndex(...)` — single entry point, holds state (DB connections, config, LLM clients)
- Class name is `PageIndex` — matches the package name
- `pi.search(query)` for fused multi-strategy search (uses strategy dispatcher with auto-routing)
- Individual strategy methods also exposed: `pi.search_semantic(query)`, `pi.search_metadata(query)`, `pi.search_tree(query)` for direct access
- `pi.ingest()` accepts both file path (`path='/path/to/doc.md'`) and raw text (`text='...', url='source-url'`)
- `pi.retrieve()` for fetching specific sections/documents

### Configuration Handling
- Use **pydantic-settings** for layered config resolution: constructor kwargs > environment variables > config file
- Environment variable prefix: `PAGEINDEX_` (e.g., `PAGEINDEX_SUPABASE_URL`, `PAGEINDEX_LLM_PROVIDER`)
- Constructor accepts both individual kwargs (`PageIndex(supabase_url='...')`) and a settings object (`PageIndex(settings=MySettings(...))`) — kwargs build a Settings object internally
- If no config is provided at all, **fail immediately** with a clear `ConfigError` listing exactly what's missing — no auto-discovery of config files

### Return Types & Errors
- `search()` returns a typed `SearchResponse` dataclass with `.results`, `.query`, `.strategy_used`, `.scores`, `.timing` — transparent and debuggable
- `ingest()` returns an `IngestionResult` dataclass with `.document_id`, `.chunks_created`, `.status`
- Custom exception hierarchy: `PageIndexError` base, with `ConfigError`, `IngestionError`, `SearchError` subtypes — catchable by type
- Search results include raw scores and strategy metadata, not just final ranked results

### Package Exports & Cleanup
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

</decisions>

<specifics>
## Specific Ideas

- User explicitly wants pydantic-settings for config — not a custom config loader. This gives automatic env var parsing, type validation, and layered precedence
- The <10 lines goal from the roadmap should be the north star for API ergonomics
- Migrating `run_pageindex.py` to the class serves as a real-world validation that the API works end-to-end
- Search transparency matters: users should see which strategy was used, what scores came back, and timing info

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-public-api*
*Context gathered: 2026-02-23*
