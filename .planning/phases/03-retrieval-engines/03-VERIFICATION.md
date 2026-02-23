---
phase: 03-retrieval-engines
verified: 2026-02-23T10:00:00Z
status: passed
score: 18/18 must-haves verified
re_verification: false
human_verification:
  - test: "End-to-end metadata search against live Supabase corpus"
    expected: "search_metadata('sentenze della Corte di Cassazione dal 2020') returns MetadataResult list with parsed_filters and scored documents"
    why_human: "Requires live Supabase connection, LiteLLM API key, and an ingested corpus"
  - test: "End-to-end semantic search with DocScore ranking"
    expected: "search_semantic('responsabilita civile') returns SemanticResult list ordered by DocScore, with chunk_count > 0"
    why_human: "Requires live Supabase match_chunks RPC and embedded corpus"
  - test: "Description search with backfill"
    expected: "backfill_description_embeddings() runs on documents missing description_embedding, then search_description('contratto appalto') returns DescriptionResult list"
    why_human: "Requires migration 003 applied to Supabase and documents with doc_description populated"
  - test: "Tree search concurrent execution"
    expected: "tree_search(['doc-id-1', 'doc-id-2', 'doc-id-3'], 'clausole penali') runs concurrently and returns TreeSearchResult with sections containing title, start_page, end_page, node_id"
    why_human: "Requires live documents with document_trees entries and LLM API for section relevance"
  - test: "Migration 003 applies cleanly to Supabase"
    expected: "All DDL statements execute without error: pg_trgm extension, four GIN indexes, description_embedding column, HNSW index, match_descriptions RPC, GRANT EXECUTE"
    why_human: "Requires live Supabase project with pgvector already enabled"
---

# Phase 3: Retrieval Engines Verification Report

**Phase Goal:** All four retrieval strategies (metadata, semantic, tree search, description) work independently against the ingested corpus
**Verified:** 2026-02-23T10:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | Uniform result type with common base fields (doc_id, score, metadata, engine_name, confidence) | VERIFIED | `RetrievalResult` dataclass at `models.py:26-49`; all subclasses inherit these five fields |
| 2  | Engine-specific result types extend base (MetadataResult+parsed_filters, TreeSearchResult+sections) | VERIFIED | `MetadataResult`, `SemanticResult`, `DescriptionResult`, `TreeSearchResult` at `models.py:57-87` each add engine-specific fields |
| 3  | Tunable retrieval parameters centralized in one config module | VERIFIED | `config.py` exports `DEFAULT_TOP_K`, `DOCSCORE_MIN_THRESHOLD`, `METADATA_MIN_THRESHOLD`, `DESCRIPTION_MIN_THRESHOLD`, `CONFIDENCE_THRESHOLDS`, `TREE_SEARCH_TOP_N`, `TREE_SEARCH_MAX_CONCURRENCY`, `METADATA_MAX_RETRIES`, `load_retrieval_config()` |
| 4  | documents table has description_embedding vector(768) column and match_descriptions RPC | VERIFIED | `003_retrieval.sql:50,72-98`: `ALTER TABLE documents ADD COLUMN IF NOT EXISTS description_embedding vector(768)` and full `match_descriptions` PL/pgSQL function |
| 5  | pg_trgm GIN indexes exist on doc_type, authority, court_level, ecli | VERIFIED | `003_retrieval.sql:30-40`: four `CREATE INDEX ... USING GIN (col gin_trgm_ops)` statements |
| 6  | User can search by natural language query translated to structured JSON filters (no raw SQL) | VERIFIED | `metadata.py:54-138`: `_llm_completion` passes `FILTER_JSON_SCHEMA` as `response_format`; `build_metadata_query` uses PostgREST chain only; grep confirms zero raw SQL strings |
| 7  | LLM-generated filters validated against MetadataFilter schema before query execution | VERIFIED | `metadata.py:119-128`: `MetadataFilter.from_dict(parsed)` validation inside retry loop before `build_metadata_query` call |
| 8  | On validation failure, system retries with feedback up to 2 retries (3 total attempts) | VERIFIED | `metadata.py:101` `for attempt in range(1, METADATA_MAX_RETRIES + 1)` with `build_retry_prompt` on failure; `METADATA_MAX_RETRIES=3` in config |
| 9  | Full metadata schema with Italian vocabulary injected into LLM prompt | VERIFIED | `prompts.py:164-200`: `build_filter_system_prompt()` calls `load_vocabulary()` and formats `_FILTER_FIELDS` descriptions; runtime verified: prompt length=4483, contains 'doc_type' and 'sentenza' |
| 10 | Parsed filter JSON returned alongside matched documents for transparency | VERIFIED | `metadata.py:356`: `MetadataResult(..., parsed_filters=parsed_filters_dict)` |
| 11 | User can search by semantic similarity with DocScore aggregation and ranking | VERIFIED | `semantic.py:116-198`: `search_semantic` embeds query, calls `match_chunks`, calls `compute_doc_scores`, filters by `DOCSCORE_MIN_THRESHOLD`, returns `SemanticResult` list |
| 12 | DocScore = (1/sqrt(N+1)) * sum(ChunkScore(n)) -- canonical formula | VERIFIED | `semantic.py:101`: `doc_score = (1 / math.sqrt(n + 1)) * raw_sum`; runtime test confirms `doc_a=0.981, doc_b=0.672` matching formula |
| 13 | Documents below minimum DocScore threshold excluded from semantic results | VERIFIED | `semantic.py:169`: `scored_docs = [d for d in scored_docs if d["score"] >= DOCSCORE_MIN_THRESHOLD]` |
| 14 | User can search by description embedding similarity; single query embedding shared across engines | VERIFIED | `description.py:34-109`: `search_description` accepts optional `query_embedding` parameter, imports `embed_query` from `semantic.py` for reuse; calls `rpc("match_descriptions", ...)` |
| 15 | Backfill function exists to embed descriptions for pre-existing documents | VERIFIED | `description.py:117-195`: `backfill_description_embeddings` queries null `description_embedding` docs, batch-embeds with `get_provider().embed()`, updates rows, returns `{backfilled, errors}` summary |
| 16 | Tree search runs concurrently on multiple documents using asyncio | VERIFIED | `tree_search.py:279-362`: `asyncio.Semaphore(max_concurrency)` + `asyncio.gather(*tasks, return_exceptions=True)` with `_search_with_semaphore` wrapper |
| 17 | Tree search results include section titles, page ranges (start_page, end_page), and node_ids | VERIFIED | `tree_search.py:245-257`: each section dict has `title`, `start_page`, `end_page`, `node_id`; `TreeSearchResult.sections` field typed as `list[dict]` |
| 18 | All four engines importable from pageindex.retrieval via clean re-exports | VERIFIED | `__init__.py:3-14`: re-exports `search_metadata`, `search_semantic`, `embed_query`, `search_description`, `backfill_description_embeddings`, `tree_search`, `tree_search_sync`, all six result types; runtime import confirms "All re-exports OK" |

**Score:** 18/18 truths verified

### Required Artifacts

| Artifact | Expected | Min Lines | Actual Lines | Status | Details |
|----------|----------|-----------|--------------|--------|---------|
| `pageindex/retrieval/__init__.py` | Package marker + re-exports | 8 | 14 | VERIFIED | Re-exports all 4 engines and 6 result types |
| `pageindex/retrieval/models.py` | Uniform result contract: 5 dataclasses + MetadataFilter + assign_confidence | 50 | 150 | VERIFIED | RetrievalResult base + 4 subclasses + MetadataFilter with from_dict/to_dict/field_count + assign_confidence helper |
| `pageindex/retrieval/config.py` | Tunable thresholds and defaults | 20 | 98 | VERIFIED | 7 module-level constants + CONFIDENCE_THRESHOLDS dict + load_retrieval_config() with config.yaml merge |
| `pageindex/db/migrations/003_retrieval.sql` | pg_trgm, GIN indexes, description_embedding, HNSW, match_descriptions RPC | 30 | 108 | VERIFIED | All 5 DDL groups present; GRANT EXECUTE on match_descriptions to pageindex_readonly |
| `pageindex/retrieval/prompts.py` | System prompt builder with schema injection, FILTER_JSON_SCHEMA | 50 | 236 | VERIFIED | _FILTER_FIELDS single source of truth; FILTER_JSON_SCHEMA with strict=True; build_filter_system_prompt (4483 chars at runtime); build_retry_prompt |
| `pageindex/retrieval/metadata.py` | generate_filters, build_metadata_query, score_metadata_results, search_metadata | 80 | 360 | VERIFIED | All four functions present and wired; dual-level retry (tenacity + validation loop) |
| `pageindex/retrieval/semantic.py` | embed_query, compute_doc_scores, search_semantic | 60 | 198 | VERIFIED | All three functions; DocScore formula verified at runtime |
| `pageindex/retrieval/description.py` | search_description, backfill_description_embeddings | 50 | 195 | VERIFIED | Both functions; match_descriptions RPC call; batch backfill with per-doc try/except |
| `pageindex/retrieval/tree_search.py` | _get_tree_nodes, _rebuild_node_text, _search_single_tree, tree_search, tree_search_sync | 70 | 420 | VERIFIED | All five functions; asyncio.Semaphore concurrency; text reconstruction from chunks; sync wrapper handles running loop via thread |

### Key Link Verification

| From | To | Via | Status | Evidence |
|------|----|-----|--------|---------|
| `models.py` | `dataclasses` (stdlib) | `@dataclass` decorator | VERIFIED | `models.py:14`: `from dataclasses import dataclass, field`; all classes decorated |
| `003_retrieval.sql` | `001_initial_schema.sql` documents table | `ALTER TABLE documents` | VERIFIED | `003_retrieval.sql:50`: `ALTER TABLE documents ADD COLUMN IF NOT EXISTS description_embedding vector(768)` |
| `prompts.py` | `pageindex/ingestion/prompts.py` | `load_vocabulary()` import | VERIFIED | `prompts.py:13`: `from pageindex.ingestion.prompts import load_vocabulary`; called at `prompts.py:177` |
| `metadata.py` | `models.py` | `MetadataFilter` + `MetadataResult` | VERIFIED | `metadata.py:33`: `from pageindex.retrieval.models import MetadataFilter, MetadataResult, assign_confidence` |
| `metadata.py` | `pageindex/db/client.py` | `get_client()` PostgREST chains | VERIFIED | `metadata.py:24`: `from pageindex.db.client import get_client`; used at `metadata.py:171` |
| `metadata.py` | `litellm` | `litellm.completion` with `response_format` | VERIFIED | `metadata.py:21`: `import litellm`; `metadata.py:54`: `litellm.completion(..., response_format=FILTER_JSON_SCHEMA, ...)` |
| `semantic.py` | `pageindex/db/chunks.py` | `match_chunks` RPC | VERIFIED | `semantic.py:24`: `from pageindex.db.chunks import match_chunks`; called at `semantic.py:155` |
| `semantic.py` | `pageindex/llm/provider.py` | `get_provider().embed()` | VERIFIED | `semantic.py:26`: `from pageindex.llm.provider import get_provider`; `semantic.py:59-61`: `provider.embed([query])` |
| `description.py` | `pageindex/db/client.py` | `rpc("match_descriptions")` | VERIFIED | `description.py:16`: `from pageindex.db.client import get_client`; `description.py:72-79`: `client.rpc("match_descriptions", {...}).execute()` |
| `description.py` | `pageindex/db/documents.py` | `get_document` for backfill | VERIFIED | `description.py:17`: `from pageindex.db.documents import get_document`; called at `description.py:89` and `description.py:177` |
| `tree_search.py` | `pageindex/db/trees.py` | `get_tree()` | VERIFIED | `tree_search.py:22`: `from pageindex.db.trees import get_tree`; called at `tree_search.py:169,342` |
| `tree_search.py` | `pageindex/db/chunks.py` | `get_chunks_by_doc()` | VERIFIED | `tree_search.py:21`: `from pageindex.db.chunks import get_chunks_by_doc`; called at `tree_search.py:183` |
| `__init__.py` | `metadata.py` | re-exports `search_metadata` | VERIFIED | `__init__.py:3`: `from .metadata import search_metadata` |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|---------|
| META-01 | 03-02 | Natural language query translated to structured metadata search via LLM | SATISFIED | `generate_filters()` uses LiteLLM structured output (JSON schema, not SQL) per locked design decision in CONTEXT.md; requirement text says "SQL" but intent is safe metadata search — fulfilled by PostgREST filter chains which are safer than LLM-generated SQL |
| META-02 | 03-01, 03-02 | LLM output validated and sanitized before execution | SATISFIED | `MetadataFilter.from_dict()` validates schema structure; structured output schema (`FILTER_JSON_SCHEMA` with `strict=True`) prevents malformed output at LLM layer; PostgREST methods eliminate injection risk entirely; requirement text says "AST validation" but the structured-output approach is the superior locked design |
| META-03 | 03-01, 03-02 | Metadata schema injected into LLM prompt | SATISFIED | `build_filter_system_prompt()` injects full `_FILTER_FIELDS` descriptions + Italian vocabulary from `legal_vocabulary.yaml`; verified at runtime: 4483-char prompt contains field names and Italian values |
| SEM-01 | 03-01 (also Phase 2) | Chunking via tree leaf nodes + embeddings in pgvector | SATISFIED | Completed in Phase 2; Plan 03-01 claims it as well (duplicate claim, benign) — chunking and embedding infrastructure verified in Phase 2 verification |
| SEM-02 | 03-03 | Semantic similarity search using query embedding vs chunk embeddings | SATISFIED | `search_semantic()` embeds query, calls `match_chunks` RPC, aggregates to DocScore, returns `SemanticResult` list |
| SEM-03 | 03-03 | DocScore = (1/sqrt(N+1)) * sum(ChunkScore(n)) | SATISFIED | `semantic.py:101`: exact formula implemented; runtime test confirms `a=0.981, b=0.672` matching expected values |
| TREE-01 | 03-04 | LLM-powered tree search within documents for relevant sections | SATISFIED | `_search_single_tree()` builds section descriptions, calls `provider.acomplete()`, parses JSON array of relevant node_ids |
| TREE-02 | 03-04 | Returns page ranges and section titles with source traceability | SATISFIED | Section dicts with `title`, `start_page`, `end_page`, `node_id` returned in `TreeSearchResult.sections` |
| ENRICH-03 | 03-01, 03-03 | Description-based search strategy | SATISFIED | `search_description()` calls `match_descriptions` RPC; `backfill_description_embeddings()` handles pre-existing documents; `description_embedding` column added in migration 003 |

**Orphaned requirements check:** All requirements mapped to Phase 3 in REQUIREMENTS.md (META-01, META-02, META-03, SEM-02, SEM-03, TREE-01, TREE-02, ENRICH-03) are accounted for across the four plans. SEM-01 is mapped to Phase 2 by REQUIREMENTS.md (Phase 3 Plan 01 also claims it — duplicate, not orphaned).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `metadata.py` | 328, 337 | `return []` | Info | Legitimate empty-result guards after threshold filtering — not stubs |
| `semantic.py` | 163 | `return []` | Info | Legitimate empty-result guard when no chunks match — not a stub |
| `description.py` | 84 | `return []` | Info | Legitimate empty-result guard when RPC returns nothing — not a stub |
| `tree_search.py` | 81, 171, 175, 180, 226, 239 | `return []` | Info | All are legitimate early-return guards (no tree, empty tree, parse failure) — not stubs |

No blockers or warnings found. All `return []` occurrences are after real implementation logic (data fetching, scoring, threshold checks) and represent correct empty-result behavior per the locked design decision.

### Requirement Text vs Implementation Note

META-01 says "translated to SQL" and META-02 says "AST validation" — the implementation uses LiteLLM structured outputs (JSON schema) feeding Supabase PostgREST filter chains, with no SQL at any point. This was an explicit locked design decision in CONTEXT.md: "No raw SQL generation. The LLM fills a structured JSON filter schema." The implementation is architecturally superior to what the requirement text describes and fully satisfies the intent of both requirements. The requirement text was written before the design was locked; REQUIREMENTS.md correctly marks both as complete.

### Human Verification Required

#### 1. End-to-End Metadata Search

**Test:** Run `from pageindex.retrieval import search_metadata; results = search_metadata("sentenze della Corte di Cassazione dal 2020 in materia penale")` against a live Supabase instance with ingested documents.
**Expected:** Returns a non-empty `list[MetadataResult]`; each result has `engine_name="metadata"`, `parsed_filters` dict with at least `doc_type` and/or `court_level` non-null, `score` between 0 and 1, `confidence` in ("high", "medium", "low").
**Why human:** Requires live Supabase credentials (SUPABASE_URL, SUPABASE_KEY), LiteLLM API key (GEMINI_API_KEY), and an ingested Italian legal corpus.

#### 2. Semantic Search DocScore in Practice

**Test:** Run `from pageindex.retrieval import search_semantic; results = search_semantic("responsabilita civile contratto appalto", limit=5)` against a live corpus.
**Expected:** Returns `list[SemanticResult]` ordered by score descending; `chunk_count >= 1` on each result; `score >= 0.3` (DOCSCORE_MIN_THRESHOLD).
**Why human:** Requires live match_chunks RPC and embedded chunk corpus.

#### 3. Description Search and Backfill Cycle

**Test:** (a) Apply migration 003 to Supabase. (b) Run `backfill_description_embeddings()` — should return `{"backfilled": N, "errors": 0}` for documents with `doc_description` but no `description_embedding`. (c) Run `search_description("contratto di locazione")`.
**Expected:** Backfill completes without errors; description search returns `list[DescriptionResult]` with `doc_description` fields populated.
**Why human:** Requires migration applied to live Supabase and documents with `doc_description` from Phase 2 ingestion.

#### 4. Tree Search Concurrent Execution

**Test:** Run `from pageindex.retrieval import tree_search_sync; results = tree_search_sync(['doc-id-1', 'doc-id-2'], "clausole penali nel contratto di appalto")` with real document IDs.
**Expected:** Returns `list[TreeSearchResult]`; each result has `sections` with at least one dict containing `title`, `start_page`, `end_page`, `node_id`.
**Why human:** Requires documents with populated `document_trees` table entries and LLM API for section relevance classification.

#### 5. Migration 003 Clean Apply

**Test:** Apply `pageindex/db/migrations/003_retrieval.sql` to the Supabase project via the SQL editor or Supabase CLI.
**Expected:** All statements execute without error. Verify: `documents` table has `description_embedding` column; `match_descriptions` function exists; four GIN indexes visible in pg_indexes.
**Why human:** Requires live Supabase project access.

---

## Gaps Summary

No gaps found. All 18 observable truths verified against actual code. All artifacts exist with substantive implementations above their minimum line thresholds. All key links confirmed wired via import and usage checks. No TODO/FIXME/placeholder anti-patterns found. All eight claimed git commits (9d9ca6d, ba9fd4e, 7ddc537, 951bdaa, 5e174f2, fc49eb6, fdf9d08, 2048234) verified in git log.

Five items require human verification with a live Supabase instance and API keys — standard for database-backed retrieval systems.

---

_Verified: 2026-02-23T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
