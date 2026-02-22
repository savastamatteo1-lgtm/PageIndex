# Stack Research

**Domain:** Multi-document legal retrieval (metadata + semantic + tree search)
**Researched:** 2026-02-22
**Confidence:** HIGH

> **Scope note:** This documents NEW dependencies for multi-document retrieval. The existing stack (Python 3.x, google-genai, PyMuPDF, PyPDF2, python-dotenv, PyYAML) is documented in `.planning/codebase/STACK.md` and not repeated here.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| `supabase` (Python client) | `>=2.28.0` | Database operations, table CRUD, RPC calls to Postgres functions | Official Supabase Python SDK. Provides async client, table queries with filters (`.eq()`, `.gte()`, etc.), and `.rpc()` for calling Postgres stored procedures. Required for metadata storage/retrieval and invoking hybrid search functions server-side. | HIGH — Context7 verified, PyPI confirmed v2.28.0 released 2026-02-10 |
| `vecs` | `>=0.4.5` | Vector collection management (upsert, index, query with metadata filters) | Supabase's official pgvector Python client. Purpose-built for vector operations: create collections, upsert embeddings with metadata, build HNSW/IVFFlat indexes, query with rich metadata filter operators (`$eq`, `$gte`, `$in`, `$and`, `$or`). Directly connects to Postgres, no REST overhead for vector ops. | HIGH — Context7 verified, Supabase official |
| pgvector (Postgres extension) | `0.8.x` (server-side) | Vector similarity search in Postgres | The standard for vector search in Postgres. HNSW indexes for fast approximate nearest neighbor search. Supports cosine distance, L2, inner product. v0.8 adds `iterative_scan` for filtered queries (critical for metadata+vector combined search). Supabase includes pgvector pre-installed. | HIGH — Context7 verified, PostgreSQL.org confirmed v0.8.0 release |
| `litellm` | `>=1.81.0` | Provider-agnostic LLM abstraction (completions + embeddings) | Unified OpenAI-format API for 100+ providers. Direct Python SDK (no proxy needed): `litellm.completion()` and `litellm.embedding()`. Supports Gemini via `gemini/` prefix, OpenAI natively, local models via Ollama. Handles retries, cost tracking, fallbacks. Replaces direct `google-genai` dependency for new retrieval code while keeping existing PageIndex code untouched. | HIGH — Context7 verified (v1.81.14 on PyPI as of 2026-02-22), extensive docs |

### Embedding Model

| Model | Dimensions | Purpose | Why Recommended | Confidence |
|-------|------------|---------|-----------------|------------|
| `gemini/gemini-embedding-001` (via LiteLLM) | 3072 (default), truncatable to 768/1536 | Document chunk embeddings for semantic search | Google's current embedding model, GA. Supports 100+ languages including Italian. 2048 max input tokens. Matryoshka Representation Learning allows dimension reduction without quality loss. text-embedding-004 is deprecated (Jan 2026). Use 768 dimensions for cost/storage efficiency at 1000+ docs scale. | HIGH — Google official announcement, deprecation confirmed |

### Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| `numpy` | `>=2.4.0` | Vector array operations | Required by `vecs` for embedding vector manipulation. Already a transitive dependency. | HIGH |
| `psycopg2-binary` | `>=2.9.0` | Direct Postgres connection | Transitive dependency of `vecs`. May be needed for custom SQL queries or migrations beyond what supabase-py provides. | HIGH |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| Supabase CLI (`supabase`) | Local development, migrations, schema management | Install via Homebrew: `brew install supabase/tap/supabase`. Use for creating/testing Postgres functions locally before deploying. |
| Supabase Dashboard | Schema inspection, SQL editor, extension management | Enable pgvector extension via Dashboard > Database > Extensions. Monitor vector index performance. |

## Installation

```bash
# New dependencies for multi-document retrieval
pip install "supabase>=2.28.0" "vecs>=0.4.5" "litellm>=1.81.0" "numpy>=2.4.0"

# Existing dependencies (already in requirements.txt - no changes needed)
# google-genai>=1.47.0, pymupdf==1.26.4, PyPDF2==3.0.1, python-dotenv==1.1.0, pyyaml==6.0.2
```

**Environment variables to add to `.env`:**
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-or-service-role-key
GEMINI_API_KEY=your-gemini-key          # Used by LiteLLM for embeddings + completions
# OPENAI_API_KEY=your-openai-key        # Optional: if user wants OpenAI models
# OLLAMA_API_BASE=http://localhost:11434 # Optional: if user wants local models
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `litellm` (LLM abstraction) | `langchain` | If you need full RAG orchestration, agent chains, or memory management. LangChain is 10-50x heavier and brings massive transitive dependencies. PageIndex already has its own tree-based retrieval logic, so LangChain's RAG primitives would be redundant. |
| `litellm` (LLM abstraction) | `llamaindex` | If you need LlamaIndex-specific data connectors or its built-in index types. Same concern as LangChain: heavy framework that duplicates PageIndex's core value (tree indexing). |
| `litellm` (LLM abstraction) | Custom wrapper over `google-genai` + `openai` | If you want zero new dependencies and only support 2 providers. Viable for v1 but becomes maintenance burden as providers are added. LiteLLM is well-maintained (daily releases) and handles edge cases (retries, streaming, token counting) across providers. |
| `vecs` (vector client) | Direct `psycopg2` + raw SQL | If you need maximum control over SQL queries. `vecs` is a thin wrapper (~2K lines) that handles collection management, indexing, and metadata filtering. Raw SQL is always available via `supabase.rpc()` for hybrid search functions. |
| `vecs` (vector client) | `pgvector-python` | If you use SQLAlchemy ORM. `pgvector-python` integrates with SQLAlchemy, Django, Peewee. PageIndex doesn't use an ORM, so `vecs` (purpose-built for Supabase) is the better fit. |
| `gemini-embedding-001` | `text-embedding-3-large` (OpenAI) | If you need 3072 dimensions natively or prefer OpenAI's ecosystem. OpenAI embeddings cost more per token. Gemini embeddings are free-tier eligible and already aligned with the project's Gemini dependency. |
| `gemini-embedding-001` | `BGE-M3` or `gte-multilingual-base` (open-source) | If you need fully local/offline embeddings or want to avoid API costs entirely. Requires `sentence-transformers` (~2GB model download), GPU recommended. Good fallback for users who cannot use cloud APIs. |
| Supabase (hosted Postgres) | Self-hosted Postgres + pgvector | If you need full control over Postgres config, or want to avoid Supabase's pricing at scale. Loses Supabase's managed auth, dashboard, and auto-generated REST API. More ops burden. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `langchain` for LLM calls | Massive dependency tree (200+ transitive deps), abstractions that fight PageIndex's existing architecture, frequent breaking changes between versions. Overkill when you only need provider-agnostic completion/embedding calls. | `litellm` — single focused library, OpenAI-compatible interface, minimal deps |
| `chromadb` or `pinecone` | Separate vector databases that duplicate Supabase's pgvector capability. Adds operational complexity (another service to manage) and prevents SQL JOINs between metadata and vectors. | pgvector via `vecs` — vectors live in the same Postgres database as metadata, enabling single-query hybrid search |
| `text-embedding-004` (Google) | Deprecated as of January 2026. Will stop working. | `gemini-embedding-001` — Google's current model, supports Matryoshka dimensions |
| `embedding-001` (Google) | Deprecated as of August 2025. | `gemini-embedding-001` |
| `sentence-transformers` as primary | Requires local GPU for reasonable performance, large model downloads (~2GB), and doesn't match `gemini-embedding-001` quality on multilingual legal text without fine-tuning. | `gemini-embedding-001` via LiteLLM. Consider `sentence-transformers` only as offline fallback. |
| `SQLAlchemy` ORM | PageIndex is a lightweight library, not a web framework. Adding an ORM layer for what amounts to 5-10 SQL patterns adds complexity without benefit. | Direct `supabase` client for CRUD + `vecs` for vectors + Postgres functions (via `.rpc()`) for hybrid search |
| Full-text search (`tsvector`) for Italian legal text | Postgres `tsvector` has limited Italian stemming support compared to English. Legal terminology (Latin phrases, statutory references like "art. 2043 c.c.") doesn't stem well. Full-text search adds marginal value when you already have metadata filtering + semantic search. | Metadata SQL filtering (structured fields like date, court, type) + semantic vector search. The two-strategy combination covers the use cases where tsvector would help, without the Italian NLP limitations. |

## Stack Patterns by Variant

**If user has Gemini API key only (default path):**
- Use `litellm` with `gemini/` prefix for completions
- Use `gemini/gemini-embedding-001` for embeddings
- Minimal config: just `GEMINI_API_KEY` env var

**If user wants OpenAI models:**
- Use `litellm` with `gpt-4o` or `o3-mini` for completions
- Use `text-embedding-3-small` or `text-embedding-3-large` for embeddings
- Set `OPENAI_API_KEY` env var
- **Caveat:** Embedding dimensions must match across all documents in a collection. Cannot mix Gemini and OpenAI embeddings.

**If user wants local/offline models:**
- Use `litellm` with `ollama/` prefix for completions (e.g., `ollama/llama3`)
- Use `sentence-transformers` for local embeddings (add `sentence-transformers>=3.0.0` to requirements)
- Set `OLLAMA_API_BASE` env var
- **Caveat:** Quality will be lower than cloud models for Italian legal text.

## Key Architecture Decisions Driven by Stack

### 1. Two clients, one database
`supabase` client handles metadata CRUD and RPC calls. `vecs` client handles vector operations. Both connect to the same Postgres database. This avoids fighting either library's API and uses each for what it's best at.

### 2. Hybrid search via Postgres functions (not application code)
Combine metadata filtering + semantic search inside Postgres stored procedures called via `supabase.rpc()`. This pushes computation to the database (where indexes live) instead of fetching data to Python for scoring. The Supabase hybrid search pattern (RRF over CTEs) is the proven approach.

### 3. LiteLLM as abstraction boundary
All new retrieval code calls `litellm.completion()` and `litellm.embedding()` instead of `google-genai` directly. Existing PageIndex code keeps its `google-genai` calls unchanged. Over time, existing code can migrate to LiteLLM too, but this is not required for v1.

### 4. Embedding dimension choice: 768
`gemini-embedding-001` supports 3072 (default), 1536, and 768 via Matryoshka truncation. Use 768 dimensions for this project:
- At 1000+ documents with 50+ chunks each, storage matters (768 vs 3072 = 4x savings)
- 768 dimensions provide excellent retrieval quality for the document scales involved
- Matches common open-source model dimensions if user switches to local embeddings later

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `supabase>=2.28.0` | Python 3.9+ | Requires Python 3.9 minimum |
| `vecs>=0.4.5` | Python 3.7+, pgvector 0.5+ | Connects directly via `psycopg2`, not via Supabase REST |
| `litellm>=1.81.0` | Python 3.8+ | Actively developed (daily releases). Pin to `>=1.81.0,<2.0` for stability |
| pgvector `0.8.x` | Postgres 13+ | `iterative_scan` feature (v0.8) recommended for filtered vector queries |
| `gemini-embedding-001` | LiteLLM `>=1.55.0` | Gemini embedding support added in LiteLLM 1.55.x |
| `numpy>=2.4.0` | Python 3.10+ | NumPy 2.x requires Python 3.10+. If targeting Python 3.9, use `numpy>=1.26,<2.0` |

**Python version recommendation:** Python 3.10+ to align with NumPy 2.x and get full `supabase` async support.

## Sources

- [Context7: /supabase/supabase-py](https://context7.com/supabase/supabase-py) — Client init, CRUD, RPC calls (HIGH confidence)
- [Context7: /supabase/vecs](https://context7.com/supabase/vecs) — Collection management, metadata filters, indexing (HIGH confidence)
- [Context7: /websites/litellm_ai](https://context7.com/websites/litellm_ai) — SDK usage, Gemini/OpenAI providers, embedding API (HIGH confidence)
- [Context7: /pgvector/pgvector](https://context7.com/pgvector/pgvector) — Hybrid search SQL, HNSW indexing, filtered queries (HIGH confidence)
- [Supabase Hybrid Search Docs](https://supabase.com/docs/guides/ai/hybrid-search) — RPC function pattern, RRF implementation (HIGH confidence)
- [Supabase AI & Vectors Docs](https://supabase.com/docs/guides/ai) — Vector columns, semantic search patterns (HIGH confidence)
- [PyPI: supabase 2.28.0](https://pypi.org/project/supabase/) — Version verified 2026-02-22 (HIGH confidence)
- [PyPI: litellm 1.81.14](https://pypi.org/project/litellm/) — Version verified 2026-02-22 (HIGH confidence)
- [Google Developers Blog: Gemini Embedding GA](https://developers.googleblog.com/gemini-embedding-available-gemini-api/) — gemini-embedding-001 specs, deprecation of text-embedding-004 (HIGH confidence)
- [LiteLLM Embedding Docs](https://docs.litellm.ai/docs/embedding/supported_embedding) — Gemini embedding via LiteLLM (HIGH confidence)
- [pgvector 0.8.0 Release](https://www.postgresql.org/about/news/pgvector-080-released-2952/) — iterative_scan feature (HIGH confidence)
- [BentoML: Open-Source Embedding Models 2026](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models) — BGE-M3, gte-multilingual-base benchmarks (MEDIUM confidence)
- [Ailog: Best Embedding Models 2025](https://app.ailog.fr/en/blog/guides/choosing-embedding-models) — MTEB scores, Qwen3-Embedding (MEDIUM confidence)
- [Milvus: Embedding Models for Legal Documents](https://milvus.io/ai-quick-reference/what-types-of-embedding-models-are-best-for-legal-documents) — Legal embedding recommendations (MEDIUM confidence)
- [LiteLLM vs LangChain comparison](https://medium.com/@heyamit10/langchain-vs-litellm-a9b784a2ad1a) — Framework weight comparison (LOW confidence — blog post)

---
*Stack research for: Multi-document legal retrieval with Supabase + pgvector + provider-agnostic LLM*
*Researched: 2026-02-22*
