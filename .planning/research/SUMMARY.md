# Project Research Summary

**Project:** PageIndex Legal Retrieval — Multi-Document Italian Legal Corpus
**Domain:** Multi-document legal retrieval (metadata SQL + semantic vector + LLM tree search)
**Researched:** 2026-02-22
**Confidence:** HIGH (stack and architecture); MEDIUM (features and metadata schema specifics)

## Executive Summary

PageIndex is a tree-based document indexing library that enables LLM reasoning over hierarchical document structure. The task is to extend it into a multi-document retrieval system for Italian legal corpora (judgments, laws, decrees, regulations). Experts build such systems with a three-layer retrieval architecture: (1) structured metadata filtering via SQL to narrow a large corpus to candidate documents, (2) semantic vector search to rank candidates by topical relevance, and (3) LLM-powered tree navigation to extract precise sections from selected documents. All three are coordinated by a query router and merged using Reciprocal Rank Fusion. The recommended implementation uses Supabase (Postgres + pgvector) as the single backend for both metadata and vectors, LiteLLM as a provider-agnostic LLM wrapper, and `gemini-embedding-001` at 768 dimensions for chunk embeddings. Existing PageIndex tree indexing code is wrapped without modification.

The recommended build sequence is foundation first: define the Postgres schema (including a hybrid fixed+JSONB metadata design and a read-only database role for LLM-generated queries), then add the LLM abstraction layer, then build the ingestion pipeline, then build the retrieval layer, and finally expose the public Python API. This ordering is dictated by hard dependency constraints: the schema must exist before ingestion can write, and ingestion must populate documents before retrieval can be validated. The most expensive decision to get right early is the embedding model and vector dimension — changing them after a 1000-document corpus is embedded requires a full reindex that is multi-day at scale.

The critical risks are: (a) LLM-generated SQL executed without sanitization enabling injection attacks — mitigated by a read-only Postgres role and parameterized RPC functions rather than raw SQL execution; (b) a rigid flat metadata schema that cannot evolve as Italian legal taxonomy requirements grow — mitigated by a hybrid fixed+JSONB design from day one; and (c) silent batch ingestion failures at scale due to absent per-document status tracking — mitigated by an ingestion status table designed into the schema before the pipeline is built. None of these risks are expensive to prevent early, but all are expensive to fix after the fact.

## Key Findings

### Recommended Stack

The stack adds four new dependencies to the existing Python codebase (google-genai, PyMuPDF, PyPDF2, PyYAML, python-dotenv): `supabase>=2.28.0` for metadata CRUD and RPC calls, `vecs>=0.4.5` for vector collection management, `litellm>=1.81.0` for provider-agnostic LLM and embedding calls, and `numpy>=2.4.0` as a required dependency of `vecs`. Supabase with pgvector 0.8.x is the standard for combined metadata+vector search in Postgres — it avoids the sync complexity of a separate vector database and enables single-query hybrid search. LiteLLM is the ecosystem-standard abstraction for multi-provider LLM calls and is preferable to a custom wrapper because it handles retries, cost tracking, and edge cases that a bespoke wrapper would need to re-implement.

**Core technologies:**
- `supabase>=2.28.0`: Database operations, metadata CRUD, RPC calls — official SDK, verified v2.28.0 on PyPI 2026-02-22
- `vecs>=0.4.5`: Vector collection management and HNSW/IVFFlat index control — Supabase's official pgvector client, avoids REST overhead for vector ops
- `litellm>=1.81.0`: Provider-agnostic LLM and embedding calls — 100+ providers, OpenAI-compatible interface, daily releases, replaces direct `google-genai` calls in new code
- `gemini/gemini-embedding-001` at 768 dimensions: Document chunk embeddings — multilingual, Matryoshka dimension support, GA, `text-embedding-004` is deprecated as of January 2026
- `pgvector 0.8.x` (Postgres extension): Vector similarity search with HNSW indexes — v0.8 adds `iterative_scan` for filtered+vector combined queries

**What NOT to use:** LangChain/LlamaIndex (100-200+ transitive deps, duplicates PageIndex's retrieval logic), Pinecone/Chromadb (separate vector database that prevents SQL+vector joins), `text-embedding-004` (deprecated January 2026), full-text search tsvector (poor Italian stemming, insufficient for legal terminology).

### Expected Features

The feature set divides cleanly into what must ship in v1, what extends it in v1.x, and what defers to v2. The single most important dependency observation from FEATURES.md is that the document registry is the foundation for everything else — nothing works until documents are persistently addressable by `doc_id`.

**Must have (v1 table stakes):**
- Supabase document registry — foundation; all retrieval paths require persistent document storage
- Italian legal metadata schema (ECLI, court hierarchy, legal area, GU reference, doc_type) — without domain-specific fields, metadata search delivers no value
- Provider-agnostic LLM abstraction via LiteLLM — must refactor early to avoid touching every call site later
- Metadata-based retrieval (LLM-to-SQL) — primary search strategy for structured legal queries
- Semantic retrieval (embed + pgvector + DocScore aggregation) — handles topical/conceptual queries
- LLM tree search on selected documents — existing PageIndex capability applied per top-K document
- Batch document ingestion pipeline — no corpus, no product
- Python library API (`ingest_document()`, `search()`, `retrieve()`)

**Should have (v1.x after validation):**
- User-selectable retrieval strategy (`"metadata"` / `"semantic"` / `"hybrid"` / `"auto"`)
- Automatic metadata extraction from document text via LLM
- Hybrid scoring via Reciprocal Rank Fusion (RRF)
- Ingestion progress tracking and resume capability
- Description-based search (lightweight quick navigation)

**Defer to v2+:**
- REST API server (explicitly deferred in PROJECT.md; library API suffices for v1 integrations)
- Multi-language support (architecture supports it; scope is Italian-only for v1)
- Cross-reference citation graph (SQL joins handle basic needs at 1000-doc scale; graph databases relevant at 100K+)
- Agentic multi-step retrieval (non-deterministic, expensive, premature before stable single-step retrieval)

**Anti-features to actively avoid:** Web UI, real-time document monitoring, OCR for scanned PDFs, fine-tuned embedding models, Neo4j graph database — all add complexity without proportional v1 value.

### Architecture Approach

The architecture follows a clean layered design: Client Layer (Python API, Batch CLI) → Orchestration Layer (Ingestion Pipeline, Query Router, Document Scorer) → Service Layer (Metadata Retriever, Semantic Retriever, Tree Search Engine, LLM Abstraction) → Data Layer (Supabase Postgres with three tables: `documents`, `chunks`, `document_trees`). The guiding principle for integrating with existing code is "wrap, do not modify" — `page_index.py`, `page_index_md.py`, and `utils.py` remain unchanged; the ingestion pipeline calls `page_index_main()` and processes its output. The folder structure under `pageindex/` adds four new subpackages: `llm/`, `store/`, `ingest/`, `retrieve/`, and `schema/` for shared types.

**Major components:**
1. **LLM Abstraction Layer (`llm/`)** — provider-agnostic interface for all new LLM and embedding calls; existing code continues using `Gemini_API()` unchanged
2. **Data Store (`store/`)** — all Supabase interaction encapsulated; `documents.py`, `chunks.py`, `trees.py` match the three table concerns
3. **Ingestion Pipeline (`ingest/`)** — write-heavy batch orchestration: PDF → tree → metadata extraction → chunking → embedding → Supabase upsert (3 tables)
4. **Retrieval Layer (`retrieve/`)** — query router fans out to metadata and/or semantic retrievers; scorer merges with RRF; tree search drills into top-K documents
5. **Schema (`schema/`)** — shared dataclasses and Italian legal metadata definitions; prevents circular imports between ingest and retrieve

**Key patterns:** Strategy-based retrieval with a common `search(query, top_k) -> list[ScoredDocument]` interface per retriever. DocScore aggregation (chunk-level similarity → document-level score). LLM-to-SQL with parameterized RPC functions (not raw SQL execution). Tree storage in Supabase JSONB, loaded at query time rather than regenerated (tree indexing takes 30-120s/document; query-time tree navigation is fast).

**Database schema (3 core tables + 2 RPC functions):**
- `documents`: fixed columns for stable fields (doc_type, authority, doc_date, legal_area, ecli, doc_number) + `metadata_extra JSONB` for evolving fields + `status` for ingestion state tracking
- `chunks`: text content + `embedding vector(768)` with HNSW index, linked to `documents` via foreign key
- `document_trees`: full PageIndex tree JSON stored as JSONB, linked to `documents`
- `match_chunks()` RPC: semantic similarity search with threshold filtering
- `search_documents_by_metadata()` RPC: parameterized metadata filtering (LLM outputs JSON filters, not raw SQL)

### Critical Pitfalls

Seven critical pitfalls were identified, all with documented prevention strategies. Five require schema-level prevention (Phase 1 decisions that are expensive to change later):

1. **LLM-to-SQL injection** — LLM generates SQL that gets executed directly, enabling DROP/DELETE attacks. Prevention: create a `readonly_search` Postgres role with SELECT-only; use parameterized RPC functions (LLM generates filter JSON, not SQL); add AST validation via `sqlglot` before any direct SQL execution. Research shows 0.44% poisoned training data yields 79.41% attack success rate; even without poisoned models, prompt injection can produce destructive SQL.

2. **Embedding model lock-in** — choosing a proprietary-only embedding model means forced full reindex when the provider deprecates it (Google already deprecated `text-embedding-004` in January 2026 and `embedding-001` in August 2025). Prevention: add `embedding_model` and `embedding_version` columns to the chunks table from day one; build reindex capability into the ingestion pipeline; use 768 dimensions (quality curve flattens between 768-1024, storage savings are 4x vs 3072).

3. **HNSW index memory exhaustion** — HNSW delivers 15.5x better throughput than IVFFlat but must fit in RAM. At 50K chunks at 768 dimensions, index alone is ~225MB; Supabase free/Pro plans have limited shared RAM. Prevention: calculate `num_vectors * dimensions * 4 bytes * 1.5` before choosing a plan; use IVFFlat during development, HNSW in production; monitor cache hit ratio via `pg_stat_user_indexes`.

4. **Naive strategy combination degrades results** — combining metadata and semantic scores without normalization or weighting produces worse results than either strategy alone. Prevention: keep retrieval paths independent until reranking; implement weighted RRF; use metadata as a pre-filter (not a parallel path) when the query has clear metadata signals; expose strategy selection to the user.

5. **Silent batch ingestion failures** — at 1000+ documents, individual failures during tree indexing, metadata extraction, or embedding generation are invisible without per-document status tracking. Prevention: design an `ingestion_status` table into the schema before building the pipeline (stages: pdf_parsed, tree_indexed, metadata_extracted, chunks_created, embeddings_generated, stored); make all upserts idempotent; use exponential backoff with jitter; bounded concurrency via `asyncio.Semaphore`.

6. **Provider abstraction becoming lowest-common-denominator** — different LLM providers have incompatible structured output semantics; naive abstraction loses provider-specific capabilities. Prevention: use LiteLLM as the abstraction (not a custom wrapper); test every prompt template against every target provider; pin specific model versions; do not abstract chat completions and embeddings behind the same interface.

7. **Italian legal metadata schema that cannot evolve** — flat Postgres table with fixed columns cannot accommodate new metadata dimensions without ALTER TABLE migrations that are expensive to run on large tables. Prevention: hybrid schema design from day one (fixed indexed columns for stable frequently-queried fields + `metadata_extra JSONB` for everything else with GIN indexing).

## Implications for Roadmap

Based on the dependency graph in ARCHITECTURE.md and pitfall-to-phase mapping in PITFALLS.md, a 5-phase structure is strongly recommended. Phases 1-3 are sequential (strict dependencies). Phases 4 and 5 have significant internal parallelism but Phase 4 must precede Phase 5.

### Phase 1: Foundation — Schema, Infrastructure, and LLM Abstraction

**Rationale:** Every subsequent phase depends on these decisions. Schema changes after ingestion are expensive or impossible. The LLM abstraction must exist before any feature code can use it. Pitfalls 1, 2, 5, 6, and 7 all require Phase 1 decisions to prevent. This is the highest-leverage phase.

**Delivers:**
- Supabase project with 3 core tables + 2 RPC functions + `ingestion_status` table
- `readonly_search` Postgres role with SELECT-only for LLM-generated queries
- Hybrid metadata schema (fixed columns + `metadata_extra JSONB`)
- `embedding_model` / `embedding_version` / `schema_version` tracking columns
- LLM abstraction layer (`llm/` package) with `BaseLLM` and `BaseEmbedder` protocols
- Gemini provider implementation wrapping existing `Gemini_API()` functions
- Italian legal metadata schema definitions (`schema/legal.py`, `schema/models.py`)
- Config extension in `config.yaml` for Supabase URL, embedding model, and provider settings
- Supabase client factory (`store/client.py`)

**Addresses:** Provider-agnostic LLM abstraction (table stakes P1), Italian legal metadata schema (P1)
**Avoids:** Pitfalls 1 (SQL injection), 2 (model lock-in), 5 (silent failures), 6 (abstraction pitfalls), 7 (rigid schema)

### Phase 2: Storage Layer and Document Registry

**Rationale:** Ingestion pipeline needs a storage layer to write to. Storage can be tested with manual SQL inserts before the full pipeline exists, enabling faster iteration. This is a prerequisite for Phase 3 and Phase 4.

**Delivers:**
- Document registry CRUD (`store/documents.py`)
- Tree index storage and retrieval (`store/trees.py`)
- Chunk storage + vector operations via `vecs` (`store/chunks.py`)
- Integration tests with manually inserted documents
- B-tree indexes on all metadata columns used in WHERE clauses (prevents performance trap: unindexed metadata columns)

**Uses:** `supabase>=2.28.0`, `vecs>=0.4.5`, Phase 1 schema
**Implements:** Data Layer from architecture diagram
**Avoids:** Pitfall 4 (performance trap: unindexed metadata columns)

### Phase 3: Ingestion Pipeline

**Rationale:** Retrieval needs documents to search. The ingestion pipeline ties together all previous phases and is the most complex write-path component. Building it after the storage layer means failures during ingestion can be attributed to pipeline logic, not storage bugs.

**Delivers:**
- Metadata extraction via LLM from document tree structure and first pages (`ingest/metadata.py`)
- Document chunker respecting tree node boundaries (`ingest/chunker.py`)
- Pipeline orchestrator with idempotent upserts, bounded concurrency (`asyncio.Semaphore`), exponential backoff with jitter, and per-document status tracking (`ingest/pipeline.py`)
- Batch embedding generation (batched API calls, 100-chunk batches to Supabase)
- Batch ingestion CLI (`python ingest.py --dir ./documents/`)
- End-to-end ingestion of a 10-document test set

**Uses:** Phase 1 LLM abstraction, Phase 2 storage layer, existing `page_index_main()` unchanged
**Implements:** Ingestion Pipeline (Orchestration Layer)
**Avoids:** Pitfall 5 (silent failures), Pitfall 6 (provider abstraction gaps in extraction prompts)

### Phase 4: Retrieval Layer

**Rationale:** Can only be validated against a populated corpus (from Phase 3). The individual retrievers can be developed in parallel (they share only the `schema/` types and common interface), but all must exist before the query router and scorer can be integrated.

**Delivers:**
- Metadata retriever with LLM-to-JSON filter generation + parameterized RPC calls (never raw SQL) (`retrieve/metadata_search.py`)
- AST-level SQL validation via `sqlglot` as defense-in-depth
- Semantic retriever with pgvector similarity search + DocScore aggregation (`retrieve/semantic_search.py`)
- HNSW vs IVFFlat index benchmarking (choose based on actual corpus size and Supabase plan RAM)
- Document scorer with configurable weighted RRF (`retrieve/scorer.py`)
- Query router with `"metadata"` / `"semantic"` / `"combined"` strategy parameter (`retrieve/router.py`)
- Tree search engine loading pre-built trees from Supabase, not regenerating them (`retrieve/tree_search.py`)
- Relevance threshold filtering on semantic search results (not just top-K regardless of score)

**Uses:** Phase 1 LLM abstraction, Phase 2 storage layer, Phase 3 populated corpus for validation
**Implements:** Service Layer (all retrieval components) + Orchestration Layer (router, scorer)
**Avoids:** Pitfall 1 (SQL injection via parameterized RPC), Pitfall 3 (HNSW memory via benchmarking), Pitfall 4 (naive combination via weighted RRF)

### Phase 5: Public API and Integration

**Rationale:** Clean external interface that wraps all internal phases. Only builds this after retrieval is proven to work end-to-end, so the API surface reflects actual capabilities rather than aspirational design.

**Delivers:**
- Python library API (`ingest_document()`, `search()`, `retrieve()`) with typed signatures
- `pageindex/__init__.py` updated with new multi-document exports
- Provider configuration via `config.yaml` (Supabase URL, embedding model, LLM provider)
- OpenAI provider implementation for LiteLLM (`llm/openai.py`) — validates provider abstraction works beyond Gemini
- Integration test suite: each prompt template tested with Gemini and OpenAI
- Example Jupyter notebook demonstrating Italian legal corpus search
- Documentation of embedding model/dimension configuration and reindex procedure

**Implements:** Client Layer (Python API)
**Avoids:** Pitfall 6 (abstraction gaps validated across providers)

### Phase Ordering Rationale

- **Schema before code:** The hybrid fixed+JSONB schema design and read-only database role cannot be retrofitted without expensive migrations. Every phase writes code that depends on this schema being correct.
- **LLM abstraction in Phase 1, not later:** The existing codebase has `ChatGPT_API = Gemini_API` aliases that prove migration is painful after the fact. New code must use the abstraction from the first line.
- **Ingestion before retrieval validation:** Retrieval logic can be written against manually inserted test data, but end-to-end validation requires real ingested documents. Phase 3 before Phase 4 is a validation dependency, not a code dependency.
- **Storage layer as its own phase:** The three store modules (`documents.py`, `chunks.py`, `trees.py`) are tested independently before the pipeline wires them together. This isolates storage bugs from pipeline bugs.
- **Public API last:** The API surface should reflect what actually works, not what was planned. Expose it after Phase 4 demonstrates retrieval quality.

### Research Flags

**Phases needing deeper research during planning:**

- **Phase 3 (Ingestion Pipeline):** The LLM prompt for automatic metadata extraction from Italian legal document text has not been tested. Gemini's ability to reliably extract ECLI identifiers, court names in Italian, and legal areas from diverse document formats needs empirical validation. Plan for prompt iteration during this phase.
- **Phase 4 (Retrieval Layer):** The DocScore aggregation strategy (max vs mean vs top-3 chunks per document) needs evaluation against actual Italian legal query test cases. The optimal RRF weights for metadata vs semantic paths for Italian legal queries are unknown and require labeled test data. Flag for experimental tuning during implementation.
- **Phase 4 (Retrieval Layer):** LLM-to-JSON filter generation quality for Italian-language legal queries (queries in Italian requesting Italian court decisions) has not been benchmarked. The metadata extraction prompt will need prompt engineering.

**Phases with well-documented standard patterns (skip research-phase):**

- **Phase 1 (Schema + Infrastructure):** Supabase schema design, JSONB hybrid patterns, pgvector table definitions, and read-only role creation are all documented in official Supabase docs with high confidence.
- **Phase 2 (Storage Layer):** `supabase-py` CRUD and `vecs` vector operations are well-documented and verified via Context7. Standard patterns apply.
- **Phase 5 (Public API):** Python library API design follows established patterns. LiteLLM multi-provider configuration is documented. No research needed beyond what is already in STACK.md.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All 4 core dependencies verified on PyPI 2026-02-22; official Supabase and LiteLLM docs confirmed via Context7; embedding model selection based on Google's official GA announcement |
| Features | MEDIUM | Italian legal metadata schema fields based on ECLI EU standard (HIGH) and Italian judicial system documentation (MEDIUM); multi-document retrieval patterns based on PageIndex official docs (MEDIUM, not peer-reviewed) |
| Architecture | HIGH | Layer separation, storage schema, RPC function patterns, and build order all follow Supabase's documented hybrid search architecture; existing codebase analysis confirmed wrap-don't-modify is viable |
| Pitfalls | HIGH | LLM-to-SQL injection backed by ACM SIGMOD 2025 and ICSE 2025 peer-reviewed research; HNSW memory benchmarks from cited study; embedding deprecation timeline from Google official announcement; batch ingestion patterns from production case studies |

**Overall confidence:** HIGH for technical decisions; MEDIUM for Italian legal domain-specific details (metadata schema completeness, legal taxonomy coverage).

### Gaps to Address

- **DocScore aggregation formula:** FEATURES.md references the official PageIndex formula `DocScore = (1/sqrt(N+1)) * sum(ChunkScore(n))` but ARCHITECTURE.md uses mean-of-top-3 as an approximation. The correct formula should be validated against the PageIndex official documentation and implemented consistently. Address during Phase 4 planning.

- **Italian ECLI extraction accuracy:** Whether Gemini can reliably extract ECLI identifiers and standardized court names from real Italian legal PDFs is unknown. The schema assumes successful extraction, but documents with non-standard formatting may require fallback strategies. Assess with a 20-document pilot during Phase 3.

- **Supabase plan sizing for 1000+ documents:** The HNSW memory requirement formula gives ~225MB for 50K chunks at 768 dimensions, but the actual chunk count depends on average document length (unknown). Estimate during Phase 3 pilot ingestion and choose Supabase plan accordingly before full corpus ingestion.

- **pgvector `iterative_scan` for filtered queries:** STACK.md recommends pgvector 0.8.x for its `iterative_scan` feature (critical for metadata+vector combined queries), but Supabase's hosted pgvector version may not be 0.8.x. Verify the Supabase-hosted pgvector version before Phase 4 and design fallback approach if v0.8.x is unavailable.

- **Embedding dimension consistency requirement:** STACK.md notes that mixing embedding models across a collection is impossible (Gemini and OpenAI vectors are incompatible). The multi-provider design must document this constraint clearly in the API and prevent mixed-model ingestion at the validation layer.

## Sources

### Primary (HIGH confidence)
- [Context7: /supabase/supabase-py](https://context7.com/supabase/supabase-py) — client init, CRUD, RPC calls, version 2.28.0
- [Context7: /supabase/vecs](https://context7.com/supabase/vecs) — collection management, metadata filters, indexing
- [Context7: /websites/litellm_ai](https://context7.com/websites/litellm_ai) — SDK usage, Gemini/OpenAI providers, embedding API
- [Context7: /pgvector/pgvector](https://context7.com/pgvector/pgvector) — HNSW indexing, filtered queries, hybrid search SQL
- [Supabase Hybrid Search Docs](https://supabase.com/docs/guides/ai/hybrid-search) — RRF implementation, RPC function pattern
- [Google Developers Blog: Gemini Embedding GA](https://developers.googleblog.com/gemini-embedding-available-gemini-api/) — gemini-embedding-001 specs and deprecation timeline
- [ToxicSQL: LLM Text-to-SQL Backdoor Attacks (ACM SIGMOD 2025)](https://arxiv.org/abs/2503.05445) — 0.44% poisoned data / 79.41% attack success
- [Prompt-to-SQL Injection Attacks (ICSE 2025)](https://dl.acm.org/doi/10.1109/ICSE55347.2025.00007) — middleware vulnerability analysis
- [pgvector HNSW vs IVFFlat Study](https://medium.com/@bavalpreetsinghh/pgvector-hnsw-vs-ivfflat-a-comprehensive-study-21ce0aaab931) — 15.5x throughput, 32x build time data
- [ECLI - EUR-Lex](https://eur-lex.europa.eu/content/help/eurlex-content/ecli.html) — Italian ECLI format specification
- [European e-Justice Portal (Italy)](https://e-justice.europa.eu/topics/taking-legal-action/legal-systems-eu-and-national/national-justice-systems/it_en) — Italian court hierarchy
- [Supabase pgvector Documentation](https://supabase.com/docs/guides/database/extensions/pgvector) — vector storage, index types, similarity operators
- [BGE-M3 Embedding Paper (arXiv)](https://arxiv.org/abs/2402.03216) — multilingual embedding benchmarks
- [Supabase: Fewer dimensions are better](https://supabase.com/blog/fewer-dimensions-are-better-pgvector) — dimension reduction evidence

### Secondary (MEDIUM confidence)
- [PageIndex Documentation — Document Search](https://docs.pageindex.ai/tutorials/doc-search) — multi-document retrieval strategies (official but not peer-reviewed)
- [PageIndex Documentation — Semantic Search](https://docs.pageindex.ai/tutorials/doc-search/semantics) — DocScore formula
- [PageIndex Documentation — Description Search](https://docs.pageindex.ai/tutorials/doc-search/description) — description-based strategy
- [Comprehensive Evaluation of Embeddings for Italian (BDCC 2025)](https://www.mdpi.com/2504-2289/9/5/141) — Italian-language embedding benchmarks
- [RAG Architectures Guide 2025](https://medium.com/data-science-collective/rag-architectures-a-complete-guide-for-2025-daf98a2ede8c) — query routing patterns
- [Optimizing RAG with Hybrid Search & Reranking (Superlinked)](https://superlinked.com/vectorhub/articles/optimizing-rag-with-hybrid-search-reranking) — strategy combination best practices
- [To Scale our RAG Agent (5,000 Files/hr)](https://www.theaiautomators.com/scale-rag-agent/) — batch insert optimization benchmarks
- [Postgres Schema Changes Are Still a PITA (Xata)](https://xata.io/blog/postgres-schema-changes-pita) — ALTER TABLE locking and migration patterns
- [Supabase RLS with pgvector](https://supabase.com/docs/guides/ai/rag-with-permissions) — row-level security for vector search
- [LLM Text-to-SQL Survey (arXiv)](https://arxiv.org/html/2410.06011v1) — LLM-to-SQL accuracy analysis

### Tertiary (LOW confidence)
- [LiteLLM vs LangChain comparison (Medium)](https://medium.com/@heyamit10/langchain-vs-litellm-a9b784a2ad1a) — framework weight comparison, blog post
- [Voyage-law-2 Blog Post](https://blog.voyageai.com/2024/04/15/domain-specific-embeddings-and-retrieval-legal-edition-voyage-law-2/) — legal domain embedding quality claims (vendor source)
- [LawGlance GitHub](https://github.com/lawglance/lawglance) — competitor feature reference (limited adoption)

---
*Research completed: 2026-02-22*
*Ready for roadmap: yes*
