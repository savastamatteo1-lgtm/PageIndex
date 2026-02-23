# Requirements: PageIndex Legal Retrieval

**Defined:** 2026-02-22
**Core Value:** Given a legal query, find the right documents from a large corpus and extract the precise relevant sections — combining structured metadata filtering with semantic understanding and reasoning-based retrieval.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Foundation

- [x] **FOUND-01**: System provides a Supabase document registry that stores document metadata, tree JSON structures, and embedding references with unique `doc_id` identifiers
- [x] **FOUND-02**: System implements Italian legal metadata schema with fields: `doc_type`, `date`, `authority`, `ecli`, `gu_number`, `legal_area`, `parties`, `court_level`, `cross_references`, plus flexible JSONB for additional fields
- [x] **FOUND-03**: System uses LiteLLM as provider-agnostic LLM abstraction layer supporting Gemini, OpenAI, Anthropic, and local models without code changes
- [x] **FOUND-04**: System provides a batch ingestion pipeline that processes PDFs through: tree indexing → metadata extraction → embedding generation → Supabase storage
- [ ] **FOUND-05**: System exposes a Python library API for programmatic integration (`ingest`, `search`, `retrieve` as core operations)

### Metadata Retrieval

- [x] **META-01**: User can search documents by natural language queries that get translated to SQL against the Italian legal metadata schema via LLM
- [x] **META-02**: System validates and sanitizes LLM-generated SQL queries before execution (read-only role, AST validation)
- [x] **META-03**: System injects the metadata schema into the LLM prompt so it generates correct column names and value types

### Semantic Retrieval

- [x] **SEM-01**: System chunks documents using tree leaf nodes as natural boundaries and generates embeddings stored in pgvector
- [x] **SEM-02**: User can search documents by semantic similarity using a query embedding against stored document chunk embeddings
- [x] **SEM-03**: System computes DocScore per document using the formula `DocScore = (1/sqrt(N+1)) * sum(ChunkScore(n))` to aggregate chunk relevance

### Tree Search

- [x] **TREE-01**: System performs LLM-powered tree search within selected documents to identify the most relevant sections/nodes
- [x] **TREE-02**: System returns specific page ranges and section titles from tree search results with source traceability

### Strategy Selection

- [ ] **STRAT-01**: User can select retrieval strategy per query: `metadata`, `semantic`, `hybrid`, or `auto`
- [ ] **STRAT-02**: System combines metadata and semantic results via Reciprocal Rank Fusion (RRF) when hybrid strategy is selected
- [ ] **STRAT-03**: Auto mode applies heuristics to select strategy: structured indicators (dates, court names, ECLI) → metadata-first; topical/conceptual queries → semantic-first

### Ingestion Enrichment

- [x] **ENRICH-01**: System automatically extracts Italian legal metadata (ECLI, court, date, legal area, parties, document type) from document text during ingestion via LLM
- [x] **ENRICH-02**: System generates one-sentence LLM descriptions for each document during ingestion for description-based search
- [x] **ENRICH-03**: User can search documents by comparing query against LLM-generated descriptions (description-based search strategy)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Infrastructure

- **INFRA-01**: REST API server wrapping the Python library for language-agnostic integration
- **INFRA-02**: Ingestion progress tracking with per-document status and crash recovery/resume
- **INFRA-03**: Real-time document monitoring and auto-ingestion of new PDFs

### Data Enrichment

- **DATA-01**: Cross-reference graph storing citation relationships between documents for bidirectional lookup
- **DATA-02**: Citation authority scoring based on how frequently a document is cited

### Scale

- **SCALE-01**: Multi-language support beyond Italian
- **SCALE-02**: OCR support for scanned PDFs via external preprocessing

## Out of Scope

| Feature | Reason |
|---------|--------|
| Web UI / chat interface | Other projects will build UIs on top of the Python library API |
| Fine-tuned embedding models | Off-the-shelf multilingual models handle Italian legal text; fine-tuning requires labeled data and ML infrastructure |
| Neo4j / graph database | SQL joins on cross-references table sufficient for 1000-doc scale; revisit at 100K+ |
| Agentic multi-step retrieval | Non-deterministic, expensive, hard to debug; user-selectable strategy with auto heuristics is sufficient |
| Mobile application | Web/programmatic access only for v1 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1 | Complete |
| FOUND-02 | Phase 1 | Complete |
| FOUND-03 | Phase 1 | Complete |
| FOUND-04 | Phase 3.1 | Complete |
| FOUND-05 | Phase 5 | Pending |
| META-01 | Phase 3 | Complete |
| META-02 | Phase 3 | Complete |
| META-03 | Phase 3 | Complete |
| SEM-01 | Phase 2 | Complete |
| SEM-02 | Phase 3 | Complete |
| SEM-03 | Phase 3 | Complete |
| TREE-01 | Phase 3 | Complete |
| TREE-02 | Phase 3 | Complete |
| STRAT-01 | Phase 4 | Pending |
| STRAT-02 | Phase 4 | Pending |
| STRAT-03 | Phase 4 | Pending |
| ENRICH-01 | Phase 2 | Complete |
| ENRICH-02 | Phase 3.1 | Complete |
| ENRICH-03 | Phase 3.1 | Complete |

**Coverage:**
- v1 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0
- Satisfied: 13/19 (2 reset by v1.0 audit, 4 pending in future phases)

---
*Requirements defined: 2026-02-22*
*Last updated: 2026-02-23 after v1.0 audit gap closure*
