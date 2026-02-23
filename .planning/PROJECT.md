# PageIndex Legal Retrieval

## What This Is

A Python library for multi-document Italian legal retrieval that combines metadata-based filtering, semantic search via pgvector embeddings, and LLM-powered tree reasoning to find and extract precise relevant sections from a corpus of 1000+ legal documents stored in Supabase.

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
- ✓ Multi-document registry with Supabase backend (document metadata + tree storage) — v1.0
- ✓ Italian legal metadata schema (type, date, authority, number, legal area, parties, cross-references) — v1.0
- ✓ Metadata-based retrieval via LLM-to-structured-JSON query translation — v1.0
- ✓ Semantic retrieval via document chunking, embedding, and pgvector search — v1.0
- ✓ User-selectable retrieval strategy per query (metadata, semantic, hybrid, auto) — v1.0
- ✓ Document scoring via DocScore aggregation and Reciprocal Rank Fusion — v1.0
- ✓ LLM tree search within selected documents to extract relevant sections — v1.0
- ✓ Provider-agnostic LLM abstraction layer via LiteLLM (Gemini, OpenAI, Anthropic, local) — v1.0
- ✓ Batch document ingestion pipeline (PDF → tree index → metadata + embeddings → Supabase) — v1.0
- ✓ Python library API for programmatic integration (`PageIndex` class) — v1.0
- ✓ Description-based search via LLM-generated document descriptions and embedding similarity — v1.0
- ✓ LLM metadata extraction (ECLI, court, date, legal area, parties, doc_type) during ingestion — v1.0
- ✓ Pydantic-settings configuration with layered resolution (kwargs > env > YAML > defaults) — v1.0

### Active

(No active requirements — next milestone TBD)

### Out of Scope

- REST API server — defer to v2, Python library is sufficient for integration
- Web UI or chat interface — other projects will build their own UIs
- Real-time document monitoring or auto-ingestion — manual batch ingestion for v1
- Document OCR or scanned PDF handling — assume text-extractable PDFs
- Multi-language support — Italian legal documents only for v1
- Fine-tuned embeddings — use off-the-shelf embedding models
- Agentic multi-step retrieval — user-selectable strategy with auto heuristics is sufficient

## Context

**Current state:** v1.0 shipped (Feb 23, 2026). ~7,600 LOC across 33 Python/SQL files. 7 phases, 17 plans executed in 2 days.

**Tech stack:** Python 3.12, Supabase (Postgres + pgvector), LiteLLM, pydantic-settings, tenacity. 3 SQL migrations (schema, ingestion status, retrieval indexes).

**Architecture:** `PageIndex` class exposes `search()`, `ingest()`, `retrieve()` + 4 engine-specific search methods. Strategy dispatcher handles metadata/semantic/hybrid/auto routing with RRF fusion. 6-stage ingestion pipeline with ThreadPoolExecutor parallelism.

**Known tech debt (3 items, all LOW):** Batch `ingest()` path missing `embed_batch_size`/`additional_fields` forwarding; `default_strategy` setting dead for `PageIndex.search()`; `utils.py` google-genai import-time init.

**User feedback:** Not yet collected — first version shipped.

## Constraints

- **Database**: Supabase (Postgres + pgvector) — chosen for combined SQL + vector search in one platform
- **LLM**: Provider-agnostic via LiteLLM — any model prefix works without code changes
- **Scale**: Architecture must handle 100,000+ documents efficiently
- **Compatibility**: Must not break existing PageIndex single-document functionality
- **API key management**: Each provider needs separate credential handling via environment variables

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Supabase over SQLite | Need pgvector for semantic search + hosted Postgres for scale | ✓ Good — SQL + vector in one platform, PostgREST for metadata queries |
| Python library over REST API | Consistent with PageIndex style, easier integration, REST can wrap later | ✓ Good — `PageIndex` class with 7 methods is clean entry point |
| LiteLLM for provider abstraction | Avoid vendor lock-in, supports 100+ providers with model prefix convention | ✓ Good — zero code changes to switch providers |
| User-selectable retrieval strategy | Different queries benefit from different approaches | ✓ Good — auto mode routes correctly; hybrid RRF improves ranking |
| Italian legal metadata schema | Domain-specific fields enable precise filtering that generic schemas miss | ✓ Good — ECLI, court hierarchy, legal area enable structured queries |
| Structured JSON filters (not SQL) | PostgREST filter chains eliminate SQL injection risk entirely | ✓ Good — safer than AST-validated SQL, simpler implementation |
| Stdlib dataclasses for result types | Lightweight, zero dependencies, sufficient for return types | ✓ Good — pydantic only used for settings where validation matters |
| pydantic-settings for config | Layered resolution (kwargs > env > YAML > defaults) handles all deployment scenarios | ✓ Good — flat-kwargs constructor and env var fallbacks work well |
| Description embedding during ingestion | Avoids separate backfill step; every document searchable by description immediately | ✓ Good — resolved ISSUE-02 from first audit |
| Config namespace separation | Tree indexer ConfigLoader validates keys strictly; ingestion keys must be excluded | ✓ Good — resolved ISSUE-01 crash from first audit |

---
*Last updated: 2026-02-23 after v1.0 milestone*
