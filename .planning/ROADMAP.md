# Roadmap: PageIndex Legal Retrieval

## Overview

This roadmap delivers a multi-document Italian legal retrieval system on top of the existing PageIndex tree-indexing library. The build sequence follows hard dependency constraints: the database schema and LLM abstraction must exist before anything can be stored, documents must be ingested before retrieval can be validated, individual retrieval engines must work before they can be orchestrated, and the public API wraps proven capabilities rather than aspirational design. Five phases take the project from an empty Supabase instance to a Python library that accepts a legal query and returns the precise relevant sections from a 1000+ document corpus.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Schema and LLM Abstraction** - Supabase database schema, Italian legal metadata definitions, and provider-agnostic LLM layer
- [x] **Phase 2: Ingestion Pipeline** - Batch processing of PDFs into indexed, enriched, and embedded documents stored in Supabase
- [x] **Phase 3: Retrieval Engines** - Metadata search, semantic search, tree search, and description search working independently
- [x] **Phase 3.1: Ingestion Integration Fixes** - Fix config key collision crashing ingest() and populate description embeddings during pipeline (INSERTED — gap closure) (completed 2026-02-23)
- [ ] **Phase 4: Strategy Orchestration** - User-selectable retrieval strategy with hybrid scoring and automatic strategy selection
- [ ] **Phase 5: Public API** - Clean Python library interface wrapping all capabilities for programmatic integration

## Phase Details

### Phase 1: Schema and LLM Abstraction
**Goal**: The database foundation and LLM infrastructure exist so that all subsequent phases can store data and make provider-agnostic LLM calls
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02, FOUND-03
**Success Criteria** (what must be TRUE):
  1. A Supabase database exists with `documents`, `chunks`, and `document_trees` tables, and a document can be inserted and retrieved by its `doc_id`
  2. The `documents` table stores Italian legal metadata fields (doc_type, date, authority, ecli, gu_number, legal_area, parties, court_level, cross_references) plus a flexible JSONB column for additional fields
  3. An LLM call (completion or embedding) can be made through the abstraction layer using Gemini without any provider-specific code at the call site
  4. Switching the configured LLM provider in config requires zero code changes in consuming modules
**Plans:** 2/2 plans complete

Plans:
- [x] 01-01-PLAN.md -- Supabase database schema, migration SQL, DB data access layer, and Italian legal vocabulary reference
- [x] 01-02-PLAN.md -- LiteLLM provider abstraction, config extension, and backward-compatible utils.py refactor

### Phase 2: Ingestion Pipeline
**Goal**: PDFs can be batch-processed through the full pipeline (tree indexing, metadata extraction, description generation, chunking, embedding) and stored in Supabase
**Depends on**: Phase 1
**Requirements**: FOUND-04, SEM-01, ENRICH-01, ENRICH-02
**Success Criteria** (what must be TRUE):
  1. User can run a batch ingestion command against a directory of Italian legal PDFs and each document is processed end-to-end into Supabase
  2. Each ingested document has automatically extracted Italian legal metadata (ECLI, court, date, legal area, doc_type) populated from the document text via LLM
  3. Each ingested document has a one-sentence LLM-generated description stored alongside its metadata
  4. Each ingested document has chunks with vector embeddings stored in pgvector, where chunk boundaries follow tree leaf nodes
  5. Ingestion failures for individual documents do not halt the batch, and failed documents can be identified and retried
**Plans:** 3/3 plans complete

Plans:
- [x] 02-01-PLAN.md -- DB migration (ingestion_status, needs_review), pipeline data models, LLM prompt templates, recursive text splitter
- [x] 02-02-PLAN.md -- Per-document pipeline stages (tree index, metadata extract, description, chunk, embed, store) and DB update/delete helpers
- [x] 02-03-PLAN.md -- Batch orchestration with ingest() entry point, ThreadPoolExecutor, rollback, resume, and config extension

### Phase 3: Retrieval Engines
**Goal**: All four retrieval strategies (metadata, semantic, tree search, description) work independently against the ingested corpus
**Depends on**: Phase 2
**Requirements**: META-01, META-02, META-03, SEM-01, SEM-02, SEM-03, TREE-01, TREE-02, ENRICH-03
**Success Criteria** (what must be TRUE):
  1. User can search by natural language query and get back documents filtered by Italian legal metadata (e.g., "sentenze della Corte di Cassazione dal 2020 in materia penale") via LLM-translated SQL
  2. LLM-generated SQL queries are validated and executed through a read-only database role, preventing any data modification
  3. User can search by semantic similarity and get back documents ranked by DocScore, which aggregates chunk-level relevance into document-level scores
  4. User can run LLM tree search on a selected document and get back specific section titles and page ranges identifying the most relevant content
  5. User can search documents by comparing a query against LLM-generated descriptions for lightweight discovery
**Plans:** 4/4 plans complete

Plans:
- [x] 03-01-PLAN.md -- Shared retrieval types (uniform result contract, MetadataFilter), config, migration 003 (pg_trgm, description_embedding, match_descriptions RPC)
- [x] 03-02-PLAN.md -- Metadata retrieval engine (LLM structured JSON filters, Supabase PostgREST query chains, filter-field scoring)
- [x] 03-03-PLAN.md -- Semantic search (DocScore aggregation) and description search (embedding similarity) engines with backfill utility
- [x] 03-04-PLAN.md -- Tree search engine (async concurrent multi-document wrapper) and retrieval package re-exports

### Phase 3.1: Ingestion Integration Fixes (INSERTED)
**Goal**: Both E2E flows (Ingest PDFs, Search Description) work without runtime errors — config keys separated and description embeddings populated during ingestion
**Depends on**: Phase 3
**Requirements**: FOUND-04, ENRICH-02 (full), ENRICH-03
**Gap Closure**: Closes gaps from v1.0 milestone audit (ISSUE-01, ISSUE-02)
**Success Criteria** (what must be TRUE):
  1. `ingest()` processes documents without `ConfigLoader._validate_keys()` raising ValueError on ingestion-specific keys
  2. After ingestion, every document has a non-NULL `description_embedding` in the database, and `search_description()` returns results for matching queries
  3. Ingestion-specific config keys (`metadata_pages`, `chunk_max_tokens`, `chunk_overlap`) are separated from tree-indexer config before `stage_tree_index` is called
**Plans:** 1/1 plans complete

Plans:
- [ ] 03.1-01-PLAN.md -- Config namespace separation (ISSUE-01) and description embedding data flow (ISSUE-02)

### Phase 4: Strategy Orchestration
**Goal**: Users can select how retrieval works per query, and the system intelligently combines or routes between retrieval engines
**Depends on**: Phase 3
**Requirements**: STRAT-01, STRAT-02, STRAT-03
**Success Criteria** (what must be TRUE):
  1. User can specify a retrieval strategy per query: `metadata`, `semantic`, `hybrid`, or `auto`
  2. When `hybrid` is selected, metadata and semantic results are combined using Reciprocal Rank Fusion and the merged ranking outperforms either strategy alone on mixed queries
  3. When `auto` is selected, the system detects structured indicators (dates, court names, ECLI) to route to metadata-first, and routes topical/conceptual queries to semantic-first
**Plans**: TBD

Plans:
- [ ] 04-01: TBD

### Phase 5: Public API
**Goal**: A clean Python library API exposes all capabilities for programmatic integration
**Depends on**: Phase 4
**Requirements**: FOUND-05
**Success Criteria** (what must be TRUE):
  1. User can `ingest` documents, `search` the corpus, and `retrieve` specific sections through typed Python functions importable from the `pageindex` package
  2. The API accepts configuration (Supabase URL, LLM provider, embedding model) via config file or constructor arguments without requiring code changes
  3. A new user can install the package, configure credentials, ingest a document, and run a search query with fewer than 10 lines of Python
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 3.1 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Schema and LLM Abstraction | 2/2 | Complete    | 2026-02-22 |
| 2. Ingestion Pipeline | 3/3 | Complete    | 2026-02-22 |
| 3. Retrieval Engines | 4/4 | Complete    | 2026-02-23 |
| 3.1. Ingestion Integration Fixes | 0/0 | Complete    | 2026-02-23 |
| 4. Strategy Orchestration | 0/0 | Not started | - |
| 5. Public API | 0/0 | Not started | - |
