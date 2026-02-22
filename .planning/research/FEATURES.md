# Feature Research

**Domain:** Multi-document legal retrieval system for Italian legal documents (court judgments, laws, regulations, decrees) combining metadata-based SQL filtering, semantic vector search, and LLM tree search over PageIndex tree indices stored in Supabase.

**Researched:** 2026-02-22
**Confidence:** MEDIUM -- PageIndex multi-document patterns are well-documented; Italian legal metadata specifics rely on domain knowledge and EU standards (ECLI, ELI) that are stable; hybrid search architecture is established practice but specific implementation details require validation during build.

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Document registry with Supabase backend** | Without a central registry, there is no multi-document system. Every document must be addressable by `doc_id` with its tree index and metadata stored persistently. | MEDIUM | Schema: `documents` table with `doc_id`, `doc_name`, `doc_description`, `tree_json`, `created_at`, plus metadata columns. PageIndex already outputs `{doc_name, doc_description, structure}` JSON -- this is the natural persistence target. |
| **Italian legal metadata schema** | The entire value of metadata search depends on having the right fields. Italian legal documents have well-structured identifiers (ECLI, Gazzetta Ufficiale numbers) that lawyers expect to filter by. | MEDIUM | Core fields: `doc_type` (sentenza, legge, decreto, regolamento, circolare), `date` (publication/decision date), `authority` (issuing court/body), `ecli` (ECLI identifier for case law), `gu_number` (Gazzetta Ufficiale series + number), `legal_area` (civile, penale, amministrativo, tributario, lavoro), `parties` (plaintiff/defendant for case law), `court_level` (cassazione, appello, tribunale, TAR, consiglio_di_stato, corte_costituzionale), `cross_references` (array of cited ECLI/law numbers). See "Italian Legal Metadata Schema" section below for full specification. |
| **Metadata-based retrieval via LLM-to-SQL** | This is PageIndex's documented first strategy for multi-document search. Users with legal corpora expect to query "find all Cassazione decisions on labor law from 2023" and get precise results. | HIGH | Four-step workflow per PageIndex docs: (1) tree generation, (2) SQL database with metadata, (3) LLM translates natural language to SQL, (4) use returned `doc_id` for tree search. The LLM-to-SQL step requires: schema injection into prompt, SQL validation/sanitization, parameterized query execution against Supabase Postgres. Common LLM errors: faulty JOINs, missing WHERE clauses, aggregation mistakes. Must implement SQL validation layer. |
| **Semantic retrieval via chunk embedding + pgvector** | This is PageIndex's documented second strategy. Users searching by topic ("precedents on unfair dismissal in fixed-term contracts") need semantic matching that goes beyond exact metadata. | HIGH | Workflow: chunk documents (use tree leaf nodes as natural chunks), embed with multilingual model, store in pgvector, vector search on query embedding, aggregate to DocScore per document. DocScore formula: `DocScore = (1/sqrt(N+1)) * sum(ChunkScore(n))` where N = number of content chunks per document. This favors documents with fewer highly-relevant chunks over those with many weakly-relevant ones. Requires: embedding model selection, chunk strategy, pgvector index (HNSW recommended for speed-accuracy balance). |
| **Document scoring and top-K selection** | After metadata or semantic search returns candidate documents, users need a ranked list. Without scoring, results are unordered and unusable. | LOW | For metadata search: results are already filtered, order by relevance metadata (date, court level). For semantic search: DocScore aggregation as above. For combined: Reciprocal Rank Fusion (RRF) to merge ranked lists from metadata and semantic paths. |
| **LLM tree search within selected documents** | This is PageIndex's core capability -- the reason the system exists. After document selection, users expect to extract the precise relevant sections from within each document. | LOW | Already implemented in existing codebase via PageIndex's tree parser and retrieval. The multi-document layer just needs to iterate tree search across selected `doc_id` list. Existing `page_index_main()` builds the trees; retrieval traverses them. |
| **Batch document ingestion pipeline** | Users have 1000+ documents to load. Manual one-by-one ingestion is not viable. Pipeline must handle: PDF parse -> tree index -> metadata extraction -> embedding generation -> Supabase storage. | HIGH | Pipeline stages: (1) PDF text extraction (existing), (2) tree index generation (existing `page_index_main`), (3) metadata extraction from document text via LLM (new), (4) chunk embedding generation (new), (5) upsert to Supabase (new). Must handle: failures mid-batch (resume from last success), rate limiting (Gemini API), progress reporting, validation of extracted metadata. Cost concern: each document requires multiple LLM calls for tree building + metadata extraction + summary generation. |
| **Python library API** | PROJECT.md explicitly requires programmatic integration. No REST API for v1 -- consistent with existing PageIndex library style. | LOW | Expose: `ingest_document(pdf_path, metadata=None)`, `search(query, strategy="auto")`, `retrieve(doc_id, query)`. Wraps the internal pipeline stages. |
| **Provider-agnostic LLM abstraction** | PROJECT.md constraint. Users must be able to swap Gemini for OpenAI, Anthropic, or local models without code changes. Current codebase is tightly coupled to Gemini (`google-genai`). | MEDIUM | Use LiteLLM (open source, 100+ providers, OpenAI-compatible interface, free) as abstraction layer. Wrap current `Gemini_API()`, `Gemini_API_async()`, and `ChatGPT_API()` functions with LiteLLM calls. Requires refactoring `pageindex/utils.py` to use LiteLLM completion calls instead of direct `google-genai` SDK. Embedding calls need separate abstraction since LiteLLM handles completions; use LiteLLM's embedding API or direct provider SDKs behind an interface. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **User-selectable retrieval strategy** | Unlike black-box legal RAG systems, users choose metadata-only, semantic-only, or hybrid search per query. Lawyers know when they want precise metadata filtering vs. broad semantic discovery. This transparency builds trust. | LOW | Expose `strategy` parameter: `"metadata"`, `"semantic"`, `"hybrid"`, `"auto"`. Auto mode: if query has structured indicators (dates, court names, ECLI patterns), use metadata-first; if query is topical/conceptual, use semantic-first; combine with RRF for hybrid. |
| **Three-strategy hybrid search (metadata + semantic + tree)** | Most legal RAG systems use only vector search. Combining SQL filtering with semantic scoring with reasoning-based tree search is rare. The metadata layer eliminates false positives; the semantic layer finds thematically relevant documents; the tree search extracts precise sections. This is the full PageIndex multi-document architecture implemented locally. | HIGH | The combination itself is the differentiator. Reciprocal Rank Fusion (RRF) merges metadata and semantic ranked lists. Tree search then operates on top-K documents from the combined list. No competitor offers all three in a single open-source library. |
| **Automatic metadata extraction from legal text** | Instead of requiring manual metadata entry, LLM extracts ECLI, court, date, legal area, parties from the document text during ingestion. Reduces ingestion friction for large corpora. | MEDIUM | LLM prompt: given document tree structure + first pages, extract structured metadata fields into JSON. Validate against known patterns (ECLI format: `ECLI:IT:[court]:[year]:[id]`). Flag low-confidence extractions for human review. |
| **Description-based search (PageIndex third strategy)** | Lightweight alternative for quick corpus navigation. Each document gets a one-sentence LLM-generated description; search compares query against descriptions. No embeddings needed. Useful for small sub-corpora or quick filtering before deeper search. | LOW | Already partially implemented: `generate_doc_description()` exists in `utils.py`. Extend to store descriptions in Supabase, add LLM comparison step per PageIndex tutorial. Best for corpora under ~100 documents. |
| **Cross-reference graph** | Legal documents cite other documents (laws cite laws, judgments cite precedents). Storing cross-references enables "find all documents that cite this law" and "find the citation chain for this precedent." Lawyers live in citation networks. | MEDIUM | Store cross-references as array column in documents table + separate `cross_references` table for bidirectional lookup. Extract during metadata extraction phase. Enables: cited-by queries, citation chain traversal, authority scoring (more-cited = more authoritative). Not a graph database -- simple SQL joins suffice for v1 scale. |
| **Ingestion progress and resume** | Batch ingestion of 1000+ documents will take hours. Users need progress visibility and crash recovery. | MEDIUM | Track ingestion state per document in Supabase: `status` (pending, indexing, embedding, complete, failed), `error_message`, `last_step`. On resume, query for non-complete documents and restart from `last_step`. Log estimated time remaining based on average per-document processing time. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems. Deliberately NOT building these.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **REST API server** | "We need a web API for our frontend." | Adds deployment complexity (server process, auth, rate limiting, CORS), doubles surface area, premature for v1 where only programmatic integration is needed. PROJECT.md explicitly defers this to v2. | Python library API. Any framework (FastAPI, Flask) can wrap the library later with 50 lines of glue code. |
| **Web UI / chat interface** | "Lawyers need a search interface." | UI development is a separate discipline. Building a UI couples the library to presentation concerns and slows iteration on core retrieval. PROJECT.md says other projects will build UIs. | Expose clean Python API; let downstream projects build UIs. Provide Jupyter notebook examples for interactive use. |
| **Real-time document monitoring / auto-ingestion** | "Automatically detect new PDFs and ingest them." | File watchers, webhook handlers, background daemons -- all add operational complexity. For v1 with manual batch ingestion, this is unnecessary infrastructure. | Manual batch ingestion with clear CLI: `python ingest.py --dir ./documents/`. Add monitoring in v2 when deployment patterns are known. |
| **Document OCR / scanned PDF handling** | "Some PDFs are scanned images." | OCR adds heavy dependencies (Tesseract, cloud OCR APIs), dramatically increases ingestion time, and introduces OCR accuracy as a variable in retrieval quality. PROJECT.md explicitly assumes text-extractable PDFs. | Require text-extractable PDFs. Document the limitation. Recommend pre-processing scanned PDFs with external OCR tools before ingestion. |
| **Fine-tuned embedding models** | "Domain-specific embeddings will be more accurate." | Fine-tuning requires labeled training data (expensive to create for Italian legal domain), ML infrastructure, ongoing maintenance, and risk of overfitting. Off-the-shelf multilingual models (BGE-M3, voyage-law-2) already handle legal text well. | Use BGE-M3 (open source, 100+ languages including Italian, 8192 token context) or voyage-law-2 (legal domain-specific, commercial API). Evaluate both during development and pick based on Italian legal text benchmarks. |
| **Multi-language support** | "We should handle EU documents in multiple languages." | Multiplies metadata schema complexity, requires per-language embedding models or multilingual models, and the Italian legal domain has its own terminology and structure. PROJECT.md scopes to Italian only for v1. | Italian only. Multilingual models (BGE-M3) would support expansion later without architecture changes. |
| **Knowledge graph with Neo4j** | "Legal reasoning requires graph databases for citation networks and concept relationships." | Neo4j adds a third database to manage alongside Supabase Postgres. For 1000 documents, graph queries can be handled by SQL joins on a cross-references table. Graph databases become valuable at 100K+ documents with complex multi-hop reasoning. | SQL-based cross-reference table with bidirectional lookups. Revisit graph database if citation traversal becomes a bottleneck at scale. |
| **Agentic multi-step retrieval** | "The LLM should autonomously decide which strategy to use, refine queries, and iterate." | Agentic loops are non-deterministic, expensive (multiple LLM calls per query), hard to debug, and introduce latency. For legal retrieval, users want predictable, explainable results -- not an AI that might wander. | User-selectable strategy with an "auto" mode that applies simple heuristics (not agentic loops) to pick the best strategy. Keep the human in control. |

## Italian Legal Metadata Schema

**Confidence: MEDIUM** -- Based on ECLI standard (EU Council Conclusions), Italian judicial system structure (Wikipedia, e-Justice Portal), and Gazzetta Ufficiale publication structure.

### Document Types (`doc_type`)

| Value | Description | Example |
|-------|-------------|---------|
| `sentenza` | Court judgment/decision | Cass. civ., sez. III, 15/03/2024 |
| `ordinanza` | Court order (procedural) | Trib. Milano, ord. 02/05/2024 |
| `decreto` | Decree (legislative or ministerial) | D.Lgs. 81/2008 |
| `legge` | Law (parliamentary) | L. 104/1992 |
| `regolamento` | Regulation | Reg. UE 2016/679 |
| `circolare` | Administrative circular | Circ. INPS n. 73/2024 |
| `decreto_legge` | Emergency decree (converted to law within 60 days) | D.L. 18/2020 |

### Court Hierarchy (`court_level`)

| Value | Full Name | Jurisdiction |
|-------|-----------|-------------|
| `corte_costituzionale` | Corte Costituzionale | Constitutional review |
| `cassazione` | Corte Suprema di Cassazione | Supreme court (5 civil + 7 criminal sections) |
| `consiglio_di_stato` | Consiglio di Stato | Supreme administrative court |
| `corte_dei_conti` | Corte dei Conti | Financial/audit court |
| `appello` | Corte d'Appello | Regional court of appeal |
| `tar` | Tribunale Amministrativo Regionale | Regional administrative court (first instance) |
| `tribunale` | Tribunale Ordinario | First instance court |
| `giudice_di_pace` | Giudice di Pace | Justice of the peace (minor disputes) |

### Legal Areas (`legal_area`)

| Value | Description |
|-------|-------------|
| `civile` | Civil law |
| `penale` | Criminal law |
| `amministrativo` | Administrative law |
| `tributario` | Tax law |
| `lavoro` | Employment/labor law |
| `commerciale` | Commercial law |
| `famiglia` | Family law |
| `costituzionale` | Constitutional law |
| `europeo` | EU law |

### ECLI Format

Standard: `ECLI:IT:[court_code]:[year]:[unique_id]`

Examples:
- `ECLI:IT:CASS:2024:12345CIV` -- Cassazione civil judgment
- `ECLI:IT:CONS:2024:00789` -- Consiglio di Stato decision
- `ECLI:IT:COST:2024:00123` -- Corte Costituzionale

Court codes are assigned by the national ECLI coordinator, max 7 characters. Unique ID max 25 characters, alphanumeric + dots only.

### Gazzetta Ufficiale Reference

Format: `GU [serie] n. [number] del [date]`

Series:
- **Serie Generale** -- Laws, decrees, regulations
- **1a Serie Speciale** -- Corte Costituzionale
- **2a Serie Speciale** -- EU legislation
- **3a Serie Speciale** -- Regional legislation
- **4a Serie Speciale** -- Public procurement
- **5a Serie Speciale** -- Public contracts

## Feature Dependencies

```
[Supabase Document Registry]
    |
    |--required-by--> [Italian Legal Metadata Schema]
    |                      |
    |                      |--required-by--> [Metadata-based Retrieval (LLM-to-SQL)]
    |                      |--required-by--> [Automatic Metadata Extraction]
    |                      |--required-by--> [Cross-reference Graph]
    |
    |--required-by--> [Semantic Retrieval (Embedding + pgvector)]
    |                      |
    |                      |--required-by--> [DocScore Aggregation]
    |
    |--required-by--> [Description-based Search]
    |
    |--required-by--> [LLM Tree Search on Selected Documents]
    |
    |--required-by--> [Batch Ingestion Pipeline]
    |                      |
    |                      |--requires--> [Provider-agnostic LLM Abstraction]
    |                      |--requires--> [Italian Legal Metadata Schema]
    |                      |--requires--> [Semantic Retrieval] (for embedding generation)
    |
    |--required-by--> [Document Scoring + Top-K Selection]
                           |
                           |--requires--> [Metadata-based Retrieval] (for metadata scores)
                           |--requires--> [Semantic Retrieval] (for DocScore)

[Provider-agnostic LLM Abstraction]
    |
    |--required-by--> [Metadata-based Retrieval] (LLM-to-SQL translation)
    |--required-by--> [Tree Search] (LLM reasoning)
    |--required-by--> [Batch Ingestion Pipeline] (tree generation + metadata extraction)
    |--required-by--> [Automatic Metadata Extraction]
    |--required-by--> [Description-based Search] (LLM comparison)

[User-selectable Retrieval Strategy]
    |--requires--> [Metadata-based Retrieval]
    |--requires--> [Semantic Retrieval]
    |--enhances--> [Document Scoring] (strategy determines scoring method)
```

### Dependency Notes

- **Document Registry is the foundation:** Everything depends on persistent document storage. Build this first.
- **Provider-agnostic LLM is a cross-cutting concern:** Refactoring `utils.py` to use LiteLLM affects all LLM-dependent features. Do this early to avoid rework.
- **Metadata schema enables metadata search:** The schema definition must precede both the metadata retrieval feature and the automatic metadata extraction feature.
- **Semantic retrieval has its own dependency chain:** Embedding model selection -> chunk strategy -> pgvector schema -> vector search function -> DocScore aggregation.
- **Batch ingestion depends on almost everything:** It ties together tree generation, metadata extraction, embedding generation, and Supabase storage. It should be built last among the table-stakes features.
- **Description-based search is independent from semantic search:** It uses LLM comparison, not embeddings. Can be built in parallel with semantic retrieval.
- **Cross-reference graph enhances but does not block other features:** It adds a new query capability but existing search strategies work without it.

## MVP Definition

### Launch With (v1)

Minimum viable product -- what is needed to validate the multi-document retrieval concept with Italian legal documents.

- [ ] **Supabase document registry** -- Foundation for all persistence. Without it, nothing else works.
- [ ] **Italian legal metadata schema** -- Domain-specific fields that make metadata search meaningful.
- [ ] **Provider-agnostic LLM abstraction (LiteLLM)** -- Refactor early to avoid rebuilding every LLM call later.
- [ ] **Metadata-based retrieval (LLM-to-SQL)** -- Primary search strategy for structured legal queries.
- [ ] **Semantic retrieval (embedding + pgvector + DocScore)** -- Second search strategy for topical/conceptual queries.
- [ ] **LLM tree search on selected documents** -- Extracts relevant sections after document selection.
- [ ] **Batch ingestion pipeline** -- Loads the corpus. Without it, the system has no documents to search.
- [ ] **Python library API** -- Clean programmatic interface wrapping the pipeline.

### Add After Validation (v1.x)

Features to add once core retrieval is working and tested against real legal corpora.

- [ ] **User-selectable retrieval strategy** -- Trigger: users report that auto-mode picks the wrong strategy for their queries.
- [ ] **Automatic metadata extraction** -- Trigger: manual metadata entry during ingestion becomes the bottleneck for onboarding new document sets.
- [ ] **Description-based search** -- Trigger: users want a quick "which documents are about X?" without full semantic search overhead.
- [ ] **Hybrid scoring (RRF)** -- Trigger: metadata-only and semantic-only results are both incomplete; combining improves recall.
- [ ] **Ingestion progress and resume** -- Trigger: batch ingestion of 500+ documents starts failing mid-batch due to API limits or network issues.

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] **Cross-reference graph** -- Why defer: requires extracting citations accurately, which is a hard NLP problem; SQL joins cover basic needs for now.
- [ ] **REST API server** -- Why defer: PROJECT.md explicitly defers this; Python library is sufficient for v1 integration.
- [ ] **Multi-language support** -- Why defer: Italian-only scope for v1; architecture (multilingual embeddings, Supabase) supports expansion later.
- [ ] **Agentic multi-step retrieval** -- Why defer: requires stable single-step retrieval first; agentic loops add non-determinism and cost.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Supabase document registry | HIGH | MEDIUM | P1 |
| Italian legal metadata schema | HIGH | MEDIUM | P1 |
| Provider-agnostic LLM (LiteLLM) | HIGH | MEDIUM | P1 |
| Metadata-based retrieval (LLM-to-SQL) | HIGH | HIGH | P1 |
| Semantic retrieval (embed + pgvector + DocScore) | HIGH | HIGH | P1 |
| LLM tree search on selected docs | HIGH | LOW | P1 |
| Batch ingestion pipeline | HIGH | HIGH | P1 |
| Python library API | HIGH | LOW | P1 |
| User-selectable retrieval strategy | MEDIUM | LOW | P2 |
| Automatic metadata extraction | MEDIUM | MEDIUM | P2 |
| Description-based search | MEDIUM | LOW | P2 |
| Hybrid scoring (RRF) | MEDIUM | MEDIUM | P2 |
| Ingestion progress/resume | MEDIUM | MEDIUM | P2 |
| Cross-reference graph | LOW | MEDIUM | P3 |
| REST API server | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch (the eight table-stakes features)
- P2: Should have, add when possible (differentiators that improve usability)
- P3: Nice to have, future consideration (features that add capability but not core value)

## Competitor Feature Analysis

| Feature | LawGlance (OSS) | LexisNexis / Westlaw AI | PageIndex Cloud | Our Approach |
|---------|-----------------|------------------------|-----------------|--------------|
| Document indexing | Flat chunking | Proprietary | Tree-based (cloud) | Tree-based (local, open source) |
| Metadata search | Basic filters | Advanced faceted search | Closed beta | LLM-to-SQL translation against domain-specific schema |
| Semantic search | Vector similarity | Proprietary embeddings | Via description strategy | pgvector with DocScore aggregation |
| Tree search / reasoning | None | None | LLM reasoning over tree | Same approach, locally implemented |
| Italian legal metadata | Generic | Some Italian coverage | Generic | Purpose-built Italian legal schema (ECLI, GU, court hierarchy) |
| Hybrid search | None | Proprietary fusion | Metadata + description | Metadata + semantic + tree (three-layer) |
| Provider-agnostic | OpenAI only | Closed | Gemini-coupled | LiteLLM (100+ providers) |
| Batch ingestion | Manual | Managed service | Cloud upload | Automated pipeline with resume |
| Open source | Yes | No | No (SDK only) | Yes |
| Self-hosted | Yes | No | No | Yes |

**Key competitive position:** No existing system combines (a) PageIndex tree-based reasoning with (b) Italian legal domain-specific metadata with (c) hybrid three-strategy search with (d) full self-hosted, open-source, provider-agnostic deployment. The closest is PageIndex Cloud, but it lacks Italian legal specialization and local deployment.

## Sources

- [PageIndex Documentation - Document Search](https://docs.pageindex.ai/tutorials/doc-search) -- MEDIUM confidence (official docs, verified)
- [PageIndex Documentation - Semantic Search](https://docs.pageindex.ai/tutorials/doc-search/semantics) -- MEDIUM confidence (official docs, verified)
- [PageIndex Documentation - Description Search](https://docs.pageindex.ai/tutorials/doc-search/description) -- MEDIUM confidence (official docs, verified)
- [ECLI - European Case Law Identifier - EUR-Lex](https://eur-lex.europa.eu/content/help/eurlex-content/ecli.html) -- HIGH confidence (official EU source)
- [European e-Justice Portal - ECLI](https://e-justice.europa.eu/topics/legislation-and-case-law/european-case-law-identifier-ecli_en) -- HIGH confidence (official EU source)
- [Judiciary of Italy - Wikipedia](https://en.wikipedia.org/wiki/Judiciary_of_Italy) -- MEDIUM confidence (Wikipedia, cross-referenced with e-Justice Portal)
- [European e-Justice Portal - National Justice Systems (Italy)](https://e-justice.europa.eu/topics/taking-legal-action/legal-systems-eu-and-national/national-justice-systems/it_en) -- HIGH confidence (official EU source)
- [Italian Legislative Text Classification - ACL Anthology](https://aclanthology.org/2023.nllp-1.6.pdf) -- MEDIUM confidence (peer-reviewed)
- [LiteLLM Documentation](https://docs.litellm.ai/docs/) -- HIGH confidence (official docs, verified via Context7)
- [BGE-M3 Embedding Paper](https://arxiv.org/abs/2402.03216) -- HIGH confidence (peer-reviewed)
- [Voyage-law-2 Blog Post](https://blog.voyageai.com/2024/04/15/domain-specific-embeddings-and-retrieval-legal-edition-voyage-law-2/) -- MEDIUM confidence (official vendor blog)
- [ITALIAN-LEGAL-BERT Models](https://www.sciencedirect.com/science/article/abs/pii/S0267364923001188) -- MEDIUM confidence (peer-reviewed)
- [Supabase pgvector Documentation](https://supabase.com/docs/guides/database/extensions/pgvector) -- HIGH confidence (official docs)
- [Hybrid Search in PostgreSQL - ParadeDB](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual) -- MEDIUM confidence (technical blog, verified pattern)
- [LLM Text-to-SQL Survey](https://arxiv.org/html/2410.06011v1) -- MEDIUM confidence (peer-reviewed survey)
- [Gazzetta Ufficiale - EU Publications Office](https://op.europa.eu/en/web/forum/italy-oj2) -- HIGH confidence (official EU source)
- [LawGlance - GitHub](https://github.com/lawglance/lawglance) -- LOW confidence (single OSS project, limited adoption)
- [LRAGE - Legal RAG Evaluation](https://arxiv.org/html/2504.01840v1) -- MEDIUM confidence (peer-reviewed)

---
*Feature research for: Multi-document Italian legal retrieval system*
*Researched: 2026-02-22*
