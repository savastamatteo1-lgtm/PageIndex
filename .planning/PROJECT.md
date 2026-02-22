# PageIndex Legal Retrieval

## What This Is

A Python library that extends PageIndex with multi-document retrieval for Italian legal documents (court judgments, laws, regulations, decrees). It combines metadata-based filtering (via SQL), semantic search (via vector embeddings), and LLM-powered tree search to find and extract relevant information from a corpus of 1000+ legal documents stored in Supabase.

## Core Value

Given a legal query, find the right documents from a large corpus and extract the precise relevant sections — combining structured metadata filtering with semantic understanding and reasoning-based retrieval.

## Requirements

### Validated

- ✓ Single-document PDF tree indexing with ToC detection and hierarchical structure — existing
- ✓ Single-document Markdown tree indexing with header-based parsing — existing
- ✓ LLM-powered node enrichment (summaries, IDs, descriptions) — existing
- ✓ Configurable processing pipeline (model, token limits, page limits) — existing
- ✓ Async concurrent processing for LLM API calls — existing
- ✓ Multi-strategy ToC extraction with fallback chain — existing

### Active

- [ ] Multi-document registry with Supabase backend (document metadata + tree storage)
- [ ] Italian legal metadata schema (type, date, authority, number, legal area, parties, cross-references)
- [ ] Metadata-based retrieval via LLM-to-SQL query translation
- [ ] Semantic retrieval via document chunking, embedding, and pgvector search
- [ ] User-selectable retrieval strategy per query (metadata-only, semantic-only, or both)
- [ ] Document scoring and top-K selection from combined retrieval paths
- [ ] LLM tree search within selected documents to extract relevant sections
- [ ] Provider-agnostic LLM abstraction layer (Gemini, OpenAI, local models)
- [ ] Batch document ingestion pipeline (PDF → tree index → metadata + embeddings → Supabase)
- [ ] Python library API for programmatic integration

### Out of Scope

- REST API server — defer to v2, Python library is sufficient for integration
- Web UI or chat interface — other projects will build their own UIs
- Real-time document monitoring or auto-ingestion — manual batch ingestion for v1
- Document OCR or scanned PDF handling — assume text-extractable PDFs
- Multi-language support — Italian legal documents only for v1
- Fine-tuned embeddings — use off-the-shelf embedding models

## Context

**Existing codebase:** PageIndex is a vectorless, reasoning-based RAG system that builds hierarchical tree indices from documents using LLM reasoning. It was recently migrated from OpenAI to Google Gemini API. The core indexing pipeline is mature and handles PDF and Markdown inputs.

**Gap being addressed:** PageIndex currently handles single-document indexing and retrieval. The official multi-document retrieval (metadata-based) is a closed-beta cloud feature. This project implements the full multi-document architecture locally, combining all three document search strategies from the PageIndex tutorials (metadata, semantics, description) with tree search for within-document retrieval.

**Domain context:** Italian legal documents have rich, well-structured metadata (ECLI identifiers, Gazzetta Ufficiale numbers, court hierarchies, legal area classifications). This makes metadata-based filtering particularly effective as a first-pass filter before semantic or reasoning-based retrieval.

**Reference architecture:** Based on PageIndex's documented multi-document search strategies:
- Metadata search: SQL-based filtering using LLM query translation
- Semantic search: Chunk + embed + vector search with DocScore aggregation
- Tree search: LLM reasoning over document tree structure

## Constraints

- **Database**: Supabase (Postgres + pgvector) — chosen for combined SQL + vector search in one platform
- **LLM**: Must be provider-agnostic — abstract away Gemini dependency so other providers work
- **Scale**: Architecture must handle 1000+ documents efficiently
- **Compatibility**: Must not break existing PageIndex single-document functionality
- **API key management**: Each provider (Gemini, OpenAI, embedding models) needs separate credential handling

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Supabase over SQLite | Need pgvector for semantic search + hosted Postgres for scale | — Pending |
| Python library over REST API | Consistent with PageIndex style, easier integration, REST can wrap later | — Pending |
| Provider-agnostic LLM layer | Avoid vendor lock-in, allow users to choose cost/quality tradeoff | — Pending |
| User-selectable retrieval strategy | Different queries benefit from different approaches (metadata vs semantic vs both) | — Pending |
| Italian legal metadata schema | Domain-specific fields enable precise filtering that generic schemas miss | — Pending |

---
*Last updated: 2026-02-22 after initialization*
