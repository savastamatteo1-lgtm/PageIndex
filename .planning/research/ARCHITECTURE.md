# Architecture Research

**Domain:** Multi-document legal retrieval (metadata + semantic + tree search)
**Researched:** 2026-02-22
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Client Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ Python API   │  │ Batch CLI    │  │ Query Interface          │   │
│  │ (library)    │  │ (ingestion)  │  │ (retrieve + search)      │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘   │
├─────────┴──────────────────┴────────────────────┴───────────────────┤
│                      Orchestration Layer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ Ingestion    │  │ Query Router │  │ Document Scorer          │   │
│  │ Pipeline     │  │              │  │ (rank + merge)           │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘   │
├─────────┴──────────────────┴────────────────────┴───────────────────┤
│                       Service Layer                                 │
│  ┌────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │ Metadata   │  │ Semantic    │  │ Tree Search │  │ LLM        │  │
│  │ Retriever  │  │ Retriever   │  │ Engine      │  │ Abstraction│  │
│  │ (SQL)      │  │ (vector)    │  │ (existing)  │  │ Layer      │  │
│  └──────┬─────┘  └──────┬──────┘  └──────┬──────┘  └─────┬──────┘  │
├─────────┴───────────────┴───────────────┴───────────────┴──────────┤
│                        Data Layer                                   │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    Supabase (Postgres)                         │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │  │
│  │  │ documents    │  │ chunks       │  │ document_trees       │ │  │
│  │  │ (metadata)   │  │ (embeddings) │  │ (tree JSON)          │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|----------------|-------------------|
| **LLM Abstraction Layer** | Provider-agnostic interface for all LLM calls (Gemini, OpenAI, local). Handles API keys, retries, model routing. | Every component that needs LLM reasoning |
| **Ingestion Pipeline** | Orchestrates PDF-to-storage: parse, tree index, extract metadata, chunk, embed, store. | PageIndex core, LLM Layer, Supabase |
| **Document Registry** | CRUD operations on the `documents` table. Tracks ingestion status, stores metadata. | Supabase, Ingestion Pipeline |
| **Metadata Retriever** | Translates natural language queries to SQL WHERE clauses via LLM. Returns candidate document IDs. | LLM Layer, Supabase `documents` table |
| **Semantic Retriever** | Embeds query, runs pgvector similarity search on chunks, aggregates chunk scores to document-level scores (DocScore). | Embedding model, Supabase `chunks` table |
| **Query Router** | Determines which retrieval strategy to use (metadata, semantic, or combined) based on user selection or query classification. | Metadata Retriever, Semantic Retriever |
| **Document Scorer** | Merges results from different retrieval paths into a unified ranked list using Reciprocal Rank Fusion or weighted scoring. | Query Router outputs |
| **Tree Search Engine** | Loads tree indices for top-K documents and runs LLM reasoning to find relevant sections. This is the existing PageIndex search capability applied within selected documents. | LLM Layer, Supabase `document_trees` table |
| **Python API** | Public library interface for programmatic use. | All orchestration components |
| **Batch CLI** | Command-line tool for bulk document ingestion. | Ingestion Pipeline |

## Recommended Project Structure

```
pageindex/
├── __init__.py                # Existing exports + new multi-doc exports
├── page_index.py              # Existing PDF tree indexing (UNCHANGED)
├── page_index_md.py           # Existing Markdown tree indexing (UNCHANGED)
├── utils.py                   # Existing utilities (UNCHANGED)
├── config.yaml                # Existing config (extended with new keys)
│
├── llm/                       # LLM Abstraction Layer
│   ├── __init__.py
│   ├── base.py                # Abstract LLM interface (BaseLLM, BaseEmbedder)
│   ├── gemini.py              # Gemini provider implementation
│   ├── openai.py              # OpenAI provider implementation
│   └── factory.py             # Provider factory from config/string name
│
├── store/                     # Data Layer (Supabase interaction)
│   ├── __init__.py
│   ├── client.py              # Supabase client singleton/factory
│   ├── documents.py           # Document registry CRUD
│   ├── chunks.py              # Chunk storage + vector operations
│   └── trees.py               # Tree index storage + retrieval
│
├── ingest/                    # Ingestion Pipeline
│   ├── __init__.py
│   ├── pipeline.py            # Main ingestion orchestrator
│   ├── metadata.py            # Legal metadata extraction via LLM
│   └── chunker.py             # Document chunking for embeddings
│
├── retrieve/                  # Retrieval Layer
│   ├── __init__.py
│   ├── router.py              # Query routing logic
│   ├── metadata_search.py     # LLM-to-SQL metadata retrieval
│   ├── semantic_search.py     # Vector similarity search + DocScore
│   ├── scorer.py              # Result fusion (RRF or weighted)
│   └── tree_search.py         # LLM tree search within documents
│
└── schema/                    # Shared types and schemas
    ├── __init__.py
    ├── legal.py               # Italian legal metadata schema
    └── models.py              # Shared dataclasses/TypedDicts
```

### Structure Rationale

- **`llm/`:** Isolated so all LLM calls across the system go through one abstraction. Existing `Gemini_API` and `Gemini_API_async` in `utils.py` remain for backward compatibility but new code uses `llm/`. Migration of existing code is optional and deferred.
- **`store/`:** All Supabase/database interaction in one place. If the storage backend changes, only this module changes. Separating `documents`, `chunks`, and `trees` reflects the three distinct table concerns.
- **`ingest/`:** Ingestion is a write-heavy batch pipeline, architecturally distinct from read-heavy retrieval. Keeping them separate avoids coupling batch concerns with query-time concerns.
- **`retrieve/`:** All query-time logic. The router decides strategy, individual retrievers execute, scorer merges. This mirrors the three retrieval strategies from PageIndex documentation (metadata, semantic, description/tree).
- **`schema/`:** Shared types prevent circular imports between `store/`, `ingest/`, and `retrieve/`. The Italian legal metadata schema lives here because it is used by both ingestion (writing metadata) and retrieval (querying metadata).

## Architectural Patterns

### Pattern 1: Strategy-Based Retrieval with Query Router

**What:** The Query Router classifies each query and dispatches it to one or more retrieval strategies. The user can also explicitly select a strategy, overriding automatic routing.

**When to use:** Every multi-document query. The router is the single entry point for retrieval.

**Trade-offs:**
- Pro: Clean separation of retrieval strategies; easy to add new strategies later
- Pro: User control over strategy selection means domain experts can optimize for their use case
- Con: Automatic routing via LLM classification adds latency and cost (mitigated by making it optional)

**Example:**
```python
class QueryRouter:
    def __init__(self, metadata_retriever, semantic_retriever, scorer):
        self.metadata = metadata_retriever
        self.semantic = semantic_retriever
        self.scorer = scorer

    async def retrieve(
        self,
        query: str,
        strategy: str = "combined",  # "metadata" | "semantic" | "combined"
        top_k: int = 10,
    ) -> list[ScoredDocument]:
        if strategy == "metadata":
            return await self.metadata.search(query, top_k)
        elif strategy == "semantic":
            return await self.semantic.search(query, top_k)
        else:  # combined
            meta_results = await self.metadata.search(query, top_k * 2)
            sem_results = await self.semantic.search(query, top_k * 2)
            return self.scorer.fuse(meta_results, sem_results, top_k)
```

### Pattern 2: DocScore Aggregation for Semantic Search

**What:** Document chunks are embedded individually, but retrieval returns document-level scores. Each chunk's similarity score is aggregated to a parent document score (e.g., max score, mean of top-3 chunks, or weighted sum). This bridges the gap between chunk-level vector search and document-level selection.

**When to use:** Semantic retrieval path. After pgvector returns the top-N most similar chunks, group by `document_id` and aggregate.

**Trade-offs:**
- Pro: Fine-grained semantic matching at chunk level, but usable document-level ranking
- Pro: Works naturally with Supabase since chunks reference their parent document via foreign key
- Con: Aggregation strategy (max vs mean vs top-3) affects results; needs tuning per domain

**Example:**
```python
async def search(self, query: str, top_k: int) -> list[ScoredDocument]:
    query_embedding = await self.embedder.embed(query)

    # pgvector similarity search via Supabase RPC
    chunk_results = await self.store.rpc("match_chunks", {
        "query_embedding": query_embedding,
        "match_count": top_k * 5,  # over-fetch chunks
    })

    # Aggregate chunks to document-level scores
    doc_scores: dict[str, list[float]] = {}
    for chunk in chunk_results:
        doc_id = chunk["document_id"]
        doc_scores.setdefault(doc_id, []).append(chunk["similarity"])

    # DocScore: mean of top-3 chunk scores per document
    scored = []
    for doc_id, scores in doc_scores.items():
        top_scores = sorted(scores, reverse=True)[:3]
        scored.append(ScoredDocument(
            document_id=doc_id,
            score=sum(top_scores) / len(top_scores),
            source="semantic",
        ))

    return sorted(scored, key=lambda d: d.score, reverse=True)[:top_k]
```

### Pattern 3: LLM-to-SQL Metadata Translation

**What:** The Metadata Retriever uses an LLM to translate natural language queries into SQL WHERE clauses against the structured legal metadata columns. The LLM is given the schema definition and generates parameterized filters.

**When to use:** Metadata retrieval path. Particularly effective for Italian legal documents because they have rich, well-structured metadata (ECLI, court, date, legal area, etc.).

**Trade-offs:**
- Pro: Users query in natural language; LLM handles the translation
- Pro: Structured metadata filtering is fast and precise (standard SQL index lookups)
- Con: LLM may generate invalid SQL; needs validation/sanitization layer
- Con: Complex queries spanning multiple metadata fields may require iterative refinement

**Example:**
```python
SCHEMA_PROMPT = """
The documents table has these columns for filtering:
- doc_type: text (sentenza, legge, decreto, regolamento)
- authority: text (Corte di Cassazione, Consiglio di Stato, ...)
- date: date
- legal_area: text (civile, penale, amministrativo, tributario)
- ecli: text (European Case Law Identifier)
- number: text (document reference number)

Given the user query, generate a JSON object with filter conditions.
Only include fields that the query explicitly or implicitly references.
"""

async def search(self, query: str, top_k: int) -> list[ScoredDocument]:
    filters = await self.llm.generate_json(
        SCHEMA_PROMPT + f"\nUser query: {query}"
    )
    # filters might be: {"doc_type": "sentenza", "legal_area": "penale", "date_after": "2020-01-01"}
    results = await self.store.query_documents(filters, limit=top_k)
    return [ScoredDocument(document_id=r["id"], score=1.0, source="metadata") for r in results]
```

## Data Flow

### Ingestion Flow (Write Path)

```
PDF File
    │
    ▼
┌─────────────────────┐
│ PageIndex Core       │  ← Existing page_index_main()
│ (tree indexing)      │
└──────────┬──────────┘
           │ Returns: {doc_name, structure, doc_description}
           ▼
┌─────────────────────┐
│ Ingestion Pipeline   │
│                      │
│  1. Extract metadata │ → LLM reads tree structure + first pages
│     (legal fields)   │   to extract doc_type, authority, date, etc.
│                      │
│  2. Chunk document   │ → Split leaf nodes into embedding-sized chunks
│     for embeddings   │   (respecting tree boundaries, ~512 tokens each)
│                      │
│  3. Generate         │ → Embedding model processes each chunk
│     embeddings       │
│                      │
│  4. Store all        │ → Three parallel writes to Supabase:
│                      │
└──────┬───┬───┬──────┘
       │   │   │
       ▼   ▼   ▼
   ┌──────┐ ┌──────┐ ┌──────────┐
   │docs  │ │chunks│ │doc_trees │
   │table │ │table │ │table     │
   │      │ │      │ │          │
   │meta- │ │text +│ │full JSON │
   │data  │ │embed-│ │tree      │
   │fields│ │dings │ │structure │
   └──────┘ └──────┘ └──────────┘
```

### Query Flow (Read Path)

```
User Query + Strategy Selection
    │
    ▼
┌─────────────────────┐
│ Query Router         │  Determines execution path based on strategy
└──────────┬──────────┘
           │
     ┌─────┼──────────────────┐
     ▼     ▼                  ▼
┌────────┐ ┌─────────┐  ┌─────────────┐
│Metadata│ │Semantic │  │Combined     │
│Search  │ │Search   │  │(both paths) │
└───┬────┘ └────┬────┘  └──┬──────┬───┘
    │           │           │      │
    │    ┌──────┘     ┌─────┘      │
    │    │            │            │
    ▼    ▼            ▼            ▼
┌────────────────────────────────────┐
│ Document Scorer                     │
│ Reciprocal Rank Fusion (RRF)       │
│ or weighted merge                   │
│                                     │
│ Output: Ranked list of document IDs │
└──────────────┬─────────────────────┘
               │ top-K document IDs
               ▼
┌─────────────────────────┐
│ Tree Search Engine       │
│                          │
│ 1. Load tree indices     │ ← Fetch from doc_trees table
│    for top-K documents   │
│                          │
│ 2. LLM navigates each   │ ← Existing PageIndex tree
│    tree to find relevant │   reasoning, applied per-doc
│    sections              │
│                          │
│ 3. Return sections with  │
│    source attribution    │
└──────────────┬──────────┘
               │
               ▼
        Final Results
        (relevant sections from ranked documents,
         with document metadata + section text)
```

### Key Data Flows

1. **Ingestion:** PDF → PageIndex tree → metadata extraction → chunking → embedding → Supabase (3 tables). This is a sequential pipeline where each step depends on the previous. The PageIndex tree step is the most expensive (many LLM calls), so it runs first and its output feeds all downstream steps.

2. **Retrieval:** Query → Router → Retriever(s) → Scorer → Tree Search → Results. The router fans out to one or two retrievers, the scorer merges, then tree search drills into the top-K documents. The two-phase design (document selection then section extraction) keeps the expensive tree search focused on only the most relevant documents.

3. **Tree Reuse:** The tree index generated during ingestion is stored in Supabase and reloaded during tree search. This avoids re-indexing at query time. The tree structure is the same JSON format that `page_index_main()` currently outputs to disk.

## Database Schema

### Core Tables

```sql
-- Document registry with Italian legal metadata
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_name TEXT NOT NULL,
    doc_description TEXT,
    file_hash TEXT UNIQUE NOT NULL,    -- SHA-256 of source file, dedup key

    -- Italian legal metadata (extracted by LLM during ingestion)
    doc_type TEXT,                      -- sentenza, legge, decreto, regolamento, etc.
    authority TEXT,                     -- issuing court/authority
    doc_date DATE,                     -- document date
    legal_area TEXT,                   -- civile, penale, amministrativo, tributario
    ecli TEXT,                         -- European Case Law Identifier
    doc_number TEXT,                   -- official reference number
    parties JSONB,                     -- parties involved (for judgments)
    cross_references JSONB,            -- references to other documents

    -- System metadata
    status TEXT DEFAULT 'pending',     -- pending, indexed, failed
    page_count INTEGER,
    token_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for metadata filtering
CREATE INDEX idx_documents_type ON documents(doc_type);
CREATE INDEX idx_documents_authority ON documents(authority);
CREATE INDEX idx_documents_date ON documents(doc_date);
CREATE INDEX idx_documents_legal_area ON documents(legal_area);
CREATE INDEX idx_documents_ecli ON documents(ecli);
CREATE INDEX idx_documents_status ON documents(status);

-- Document chunks with embeddings for semantic search
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,      -- position within document
    node_id TEXT,                       -- reference to tree node_id
    content TEXT NOT NULL,
    token_count INTEGER,
    embedding vector(768),             -- dimension matches chosen model

    UNIQUE(document_id, chunk_index)
);

-- HNSW index for fast approximate nearest neighbor search
CREATE INDEX idx_chunks_embedding ON chunks
    USING hnsw (embedding vector_cosine_ops);

-- Tree indices stored as JSONB
CREATE TABLE document_trees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE UNIQUE,
    tree_structure JSONB NOT NULL,      -- full PageIndex tree JSON
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Supabase RPC Functions

```sql
-- Semantic search: match chunks by embedding similarity
CREATE FUNCTION match_chunks(
    query_embedding vector(768),
    match_count INT DEFAULT 20,
    similarity_threshold FLOAT DEFAULT 0.5
)
RETURNS TABLE (
    chunk_id UUID,
    document_id UUID,
    content TEXT,
    node_id TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id AS chunk_id,
        c.document_id,
        c.content,
        c.node_id,
        1 - (c.embedding <=> query_embedding) AS similarity
    FROM chunks c
    JOIN documents d ON c.document_id = d.id
    WHERE d.status = 'indexed'
      AND 1 - (c.embedding <=> query_embedding) > similarity_threshold
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Metadata search with dynamic filtering
-- (called from Python after LLM generates filter JSON)
CREATE FUNCTION search_documents_by_metadata(
    filter_type TEXT DEFAULT NULL,
    filter_authority TEXT DEFAULT NULL,
    filter_legal_area TEXT DEFAULT NULL,
    filter_date_from DATE DEFAULT NULL,
    filter_date_to DATE DEFAULT NULL,
    filter_ecli TEXT DEFAULT NULL,
    match_count INT DEFAULT 20
)
RETURNS TABLE (
    id UUID,
    doc_name TEXT,
    doc_description TEXT,
    doc_type TEXT,
    authority TEXT,
    doc_date DATE,
    legal_area TEXT,
    ecli TEXT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id, d.doc_name, d.doc_description, d.doc_type,
        d.authority, d.doc_date, d.legal_area, d.ecli
    FROM documents d
    WHERE d.status = 'indexed'
      AND (filter_type IS NULL OR d.doc_type = filter_type)
      AND (filter_authority IS NULL OR d.authority = filter_authority)
      AND (filter_legal_area IS NULL OR d.legal_area = filter_legal_area)
      AND (filter_date_from IS NULL OR d.doc_date >= filter_date_from)
      AND (filter_date_to IS NULL OR d.doc_date <= filter_date_to)
      AND (filter_ecli IS NULL OR d.ecli = filter_ecli)
    ORDER BY d.doc_date DESC
    LIMIT match_count;
END;
$$;
```

## Integration with Existing PageIndex

### Principle: Wrap, Do Not Modify

The existing `page_index.py`, `page_index_md.py`, and `utils.py` are mature, tested code. The multi-document system wraps their output rather than modifying their internals.

**Integration surface:**

| Existing Function | How Multi-Doc System Uses It |
|-------------------|------------------------------|
| `page_index_main(doc, opt)` | Ingestion pipeline calls this to generate tree structure for each PDF |
| `md_to_tree(md_path, opt)` | Same, for Markdown documents |
| `page_index(doc, **kwargs)` | Convenience wrapper remains available for single-document use |
| Output JSON `{doc_name, structure, [doc_description]}` | Stored directly in `document_trees.tree_structure` |
| `generate_doc_description()` | Called during ingestion; description stored in `documents.doc_description` |
| `generate_summaries_for_structure()` | Called during ingestion; summaries in tree enable better tree search |
| Tree node format `{title, node_id, start_index, end_index, summary, nodes[]}` | Tree search engine navigates this structure at query time |

**What changes in existing code:** Nothing for v1. The `config.yaml` gets new keys for multi-document settings (Supabase URL, embedding model, etc.) but existing keys remain unchanged. The `ConfigLoader` already validates against known keys, so new keys are added to the config schema.

### LLM Abstraction Migration Path

The existing code uses `Gemini_API()` and `Gemini_API_async()` directly. The new `llm/` module provides a provider-agnostic interface. Migration is gradual:

1. **Phase 1:** New multi-document code uses `llm/` module exclusively
2. **Phase 2 (optional):** Existing PageIndex code continues using `Gemini_API` functions
3. **Phase 3 (optional, future):** Refactor existing code to use `llm/` module if provider-switching for tree indexing is needed

This avoids touching the stable indexing pipeline while still getting provider-agnostic LLM support for all new retrieval and ingestion code.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-100 docs | Single Supabase project, no index tuning needed. pgvector exact search is fast enough. Batch ingestion runs sequentially. |
| 100-1K docs | Enable HNSW index on chunks table. Batch ingestion with `asyncio.gather()` for parallel embedding generation. Chunk table may reach ~50K-500K rows depending on doc size. |
| 1K-10K docs | Consider IVFFlat index if HNSW memory is a concern. Partition chunks table by `document_id` range. Ingestion becomes a background job. |
| 10K+ docs | Supabase Vector Buckets (S3-backed) for embedding storage instead of pgvector. Queue-based ingestion with progress tracking. Consider caching frequent metadata filter results. |

### Scaling Priorities

1. **First bottleneck: Ingestion speed.** Each document requires ~5-20 LLM calls for tree indexing + 1 call for metadata extraction + N embedding calls for chunks. At 1000 documents, this is thousands of API calls. Mitigation: async concurrent processing (already the pattern in existing code), batch embedding endpoints, progress tracking with resume capability.

2. **Second bottleneck: Vector search latency.** As the chunks table grows past ~100K rows, unindexed vector search slows down. Mitigation: HNSW index (already in the schema above), pre-filtering by metadata to reduce search space.

3. **Third bottleneck: Tree search at query time.** Each of the top-K documents requires LLM calls to navigate the tree. With K=10, that is 10+ LLM calls per query. Mitigation: cache tree search results for frequently queried documents, limit K based on confidence scores.

## Anti-Patterns

### Anti-Pattern 1: Embedding Entire Documents

**What people do:** Embed the full document text as a single vector.
**Why it is wrong:** Long documents exceed embedding model context windows. Even when truncated, a single embedding loses section-level granularity. Legal documents have distinct sections (facts, reasoning, ruling) that should be independently searchable.
**Do this instead:** Chunk documents along tree node boundaries. Each leaf node or group of adjacent leaf nodes becomes a chunk. This preserves the hierarchical structure and enables section-level semantic matching.

### Anti-Pattern 2: Tight Coupling Between Retrieval Strategies

**What people do:** Build one monolithic search function that mixes SQL filtering, vector search, and LLM reasoning in a single code path.
**Why it is wrong:** Impossible to test, tune, or swap individual strategies. When metadata search works poorly, you cannot isolate and fix it without risking regressions in semantic search.
**Do this instead:** Each retrieval strategy is its own module with a common interface (`search(query, top_k) -> list[ScoredDocument]`). The router composes them. The scorer merges their outputs.

### Anti-Pattern 3: Re-indexing Trees at Query Time

**What people do:** Generate the tree structure on-the-fly when a user queries a document.
**Why it is wrong:** Tree indexing for a single document takes 30-120 seconds and many LLM calls. This is unacceptable at query time.
**Do this instead:** Index once during ingestion, store the tree JSON in Supabase, load it at query time. Tree search at query time only navigates the pre-built tree (a few LLM calls to select relevant branches), which is fast.

### Anti-Pattern 4: Storing Embeddings in a Separate System

**What people do:** Use Supabase for metadata and a separate vector database (Pinecone, Weaviate) for embeddings.
**Why it is wrong:** Two systems to manage, sync issues between metadata and embeddings, inability to do combined SQL+vector queries in a single round-trip. The whole point of pgvector in Supabase is having both in one database.
**Do this instead:** Use pgvector within the same Supabase Postgres instance. Metadata filtering and vector search happen in the same database, enabling combined queries and atomic operations.

## Build Order (Dependency Graph)

The components have clear dependencies that dictate build order:

```
Phase 1: Foundation
   ├── LLM Abstraction Layer (llm/)        ← No dependencies, enables everything
   ├── Schema Definitions (schema/)         ← No dependencies, defines shared types
   └── Supabase Client + Migrations (store/client.py + SQL)  ← No code dependencies

Phase 2: Storage Layer
   ├── Document Registry (store/documents.py)  ← Depends on: Phase 1
   ├── Tree Storage (store/trees.py)           ← Depends on: Phase 1
   └── Chunk Storage (store/chunks.py)         ← Depends on: Phase 1

Phase 3: Ingestion Pipeline
   ├── Metadata Extraction (ingest/metadata.py)  ← Depends on: LLM Layer, Document Registry
   ├── Document Chunker (ingest/chunker.py)      ← Depends on: Schema, existing tree output
   └── Pipeline Orchestrator (ingest/pipeline.py) ← Depends on: ALL of Phase 2 + above

Phase 4: Retrieval Layer
   ├── Metadata Retriever (retrieve/metadata_search.py) ← Depends on: LLM Layer, Document Registry
   ├── Semantic Retriever (retrieve/semantic_search.py) ← Depends on: LLM Layer (embedder), Chunk Storage
   ├── Document Scorer (retrieve/scorer.py)              ← Depends on: Schema only
   ├── Query Router (retrieve/router.py)                 ← Depends on: Both Retrievers, Scorer
   └── Tree Search Engine (retrieve/tree_search.py)      ← Depends on: LLM Layer, Tree Storage

Phase 5: Integration
   └── Public API + CLI (top-level interface)    ← Depends on: ALL above
```

**Key ordering rationale:**

- **LLM abstraction first** because every subsequent component needs it. Without a provider-agnostic LLM interface, each component would hard-code Gemini calls and need refactoring later.
- **Storage layer before ingestion** because the ingestion pipeline needs somewhere to write. Storage can be tested with manual SQL inserts before the full pipeline exists.
- **Ingestion before retrieval** because retrieval needs documents in the database to search. However, retrieval components can be developed in parallel using manually-inserted test data.
- **Tree search last within retrieval** because it is the most complex retrieval component and requires both tree storage and the LLM layer to be solid. It also has the least coupling to the other retrievers (it operates on documents already selected by them).

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Supabase (Postgres + pgvector) | `supabase-py` client library, RPC calls for vector search, direct SQL for DDL | Use service role key for server-side operations. Connection pooling via Supabase's built-in PgBouncer. |
| Gemini API | Async HTTP via `google-genai` library | Current provider for tree indexing. Wrapped by `llm/gemini.py`. |
| OpenAI API | Async HTTP via `openai` library | Alternative LLM provider. Also provides embedding models. Wrapped by `llm/openai.py`. |
| Embedding model | Via LLM abstraction `BaseEmbedder` interface | Model choice affects chunk table's vector dimension. Must be consistent across ingestion and query time. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Existing PageIndex ↔ Multi-doc system | Function call: `page_index_main()` returns dict | No changes to existing code. Ingestion pipeline calls it and processes the output. |
| LLM Layer ↔ Everything else | Async function calls via `BaseLLM.generate()`, `BaseEmbedder.embed()` | All LLM interaction goes through the abstraction. Provider is selected at initialization. |
| Store Layer ↔ Supabase | `supabase-py` RPC and table operations | All database interaction is encapsulated in `store/` module. Upper layers never touch Supabase directly. |
| Ingestion ↔ Retrieval | No direct communication | They share the database schema but do not call each other. Ingestion writes, retrieval reads. |
| Query Router ↔ Retrievers | Common interface: `search(query, top_k) -> list[ScoredDocument]` | Router calls retrievers polymorphically. New retrieval strategies can be added by implementing the interface. |

## Sources

- [Supabase Hybrid Search Documentation](https://supabase.com/docs/guides/ai/hybrid-search) — RRF implementation pattern, SQL function structure (HIGH confidence)
- [Supabase pgvector Documentation](https://supabase.com/docs/guides/database/extensions/pgvector) — Vector storage, index types, similarity operators (HIGH confidence)
- [Supabase Semantic Search Documentation](https://supabase.com/docs/guides/ai/semantic-search) — Embedding storage and RPC patterns (HIGH confidence)
- [Supabase Vector Querying Documentation](https://supabase.com/docs/guides/storage/vector/querying-vectors) — Filtered similarity search, hybrid search patterns (HIGH confidence)
- [Elastic Hybrid Search Guide](https://www.elastic.co/what-is/hybrid-search) — General hybrid search architecture concepts (MEDIUM confidence)
- [RAG Architectures Guide 2025](https://medium.com/data-science-collective/rag-architectures-a-complete-guide-for-2025-daf98a2ede8c) — Query routing patterns, multi-document retrieval architecture (MEDIUM confidence)
- [Building a RAG Router in 2025](https://medium.com/@tim_pearce/building-a-rag-router-in-2025-e0e9d99efe44) — Router classification approaches (MEDIUM confidence)
- Existing codebase analysis: `/Users/matteo/Desktop/PAI/PageIndex/.planning/codebase/ARCHITECTURE.md` (HIGH confidence)

---
*Architecture research for: Multi-document legal retrieval system*
*Researched: 2026-02-22*
