# Phase 3: Retrieval Engines - Research

**Researched:** 2026-02-23
**Domain:** Multi-strategy document retrieval (metadata filtering, semantic search, tree search, description search) over Italian legal corpus in Supabase/pgvector
**Confidence:** HIGH

## Summary

Phase 3 builds four independent retrieval engines on top of the ingested Supabase corpus from Phase 2. The metadata engine uses LLM-generated structured JSON filters (not raw SQL) translated to Supabase PostgREST query chains. The semantic engine uses the existing `match_chunks` RPC for pgvector cosine similarity, aggregated to document-level via the DocScore formula. The tree search engine wraps the existing `page_index.py` tree search for multi-document concurrent use. The description engine embeds the query and compares against pre-embedded document descriptions via a new RPC function.

All four engines share a uniform result contract (base fields + engine-specific extras) and are designed to work independently -- strategy orchestration is Phase 4. The project already has the database schema, vector indexes, LLM provider abstraction, and match_chunks RPC function in place from Phases 1-2, so this phase focuses on the query-side logic, a new migration for `pg_trgm` indexes and a description embedding column, and the DocScore aggregation algorithm.

**Primary recommendation:** Build a `pageindex/retrieval/` package with one module per engine, a shared `models.py` for the uniform result contract, and a `config.py` for tunable thresholds. Use LiteLLM's `response_format` with `json_schema` for structured filter generation (already proven in ingestion Stage 2). Use the Supabase Python client's chainable filter methods (`.ilike()`, `.gte()`, `.lte()`, `.overlaps()`, `.contains()`) to translate filter JSON to queries -- no raw SQL at any point.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **No raw SQL generation.** The LLM fills a structured JSON filter schema via tool calling / structured outputs (supported across Gemini, OpenAI, Anthropic via LiteLLM)
- The JSON schema is flat: each field is equality, list (implicit OR / `IN`), or date range (`date_from`, `date_to`). Cross-field is implicit AND
- String fields use Supabase `.ilike()` for partial matching (not exact equality) since legal entity names vary in form
- Upgrade Supabase schema with `pg_trgm` indexes for fuzzy matching at the database layer -- no vocabulary coupling at query time
- Full metadata schema injected into LLM prompt so it generates correct field names and types
- On validation failure: retry with feedback up to 2 retries (3 total attempts), then return error
- **Transparency:** Return the parsed filter JSON alongside matched documents so callers can see how the query was interpreted
- Default top-K: 10 results (user-overridable per query)
- Minimum DocScore threshold: results below threshold are excluded even if top-K isn't filled
- Description search uses **embedding similarity** (embed query, compare against pre-embedded descriptions via cosine similarity) -- fast, reuses existing infrastructure, no extra LLM call per query
- Empty results return an empty list + reason string explaining why
- **Auto-chained** tree search after other engines return results -- not standalone user-triggered
- Tree search runs on the **top 5 documents** from the preceding engine's results
- **Wraps existing PageIndex tree search implementation** (page_index.py search methods), adapted for multi-doc use
- **Parallel execution:** concurrent tree search across all 5 documents simultaneously (async)
- **Uniform base + engine-specific extras:** Common base type shared by all engines, with engine-specific fields added on top
- Base fields: `doc_id`, `score`, `metadata` (full legal metadata), `engine_name`, `confidence` (high/medium/low label derived from score threshold)
- Tree search adds: section titles, page ranges
- Metadata engine adds: parsed filter JSON
- **Metadata engine scoring:** score = number of filter fields that matched (a doc matching 4 of 5 filters scores higher than one matching 2 of 5)

### Claude's Discretion
- Exact DocScore threshold value (tunable default)
- Confidence label bucket boundaries
- Structured output JSON schema design details
- Async concurrency limits for parallel tree search

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| META-01 | User can search documents by natural language queries translated to SQL against metadata schema via LLM | LiteLLM structured outputs with `response_format` JSON schema generate filter objects; Supabase Python client `.ilike()`, `.gte()`, `.lte()`, `.overlaps()` translate filters to PostgREST queries without raw SQL |
| META-02 | System validates and sanitizes LLM-generated SQL queries before execution (read-only role, AST validation) | Decision changed from raw SQL to structured JSON filters, eliminating SQL injection risk entirely. Validation is JSON schema conformance checking (field names, types, value formats). The `pageindex_readonly` role from migration 001 remains as defense-in-depth |
| META-03 | System injects metadata schema into LLM prompt so it generates correct column names and value types | The full metadata column schema with types and example values is injected into the system prompt, same pattern as the ingestion metadata extraction prompt. Legal vocabulary YAML provides reference values |
| SEM-01 | System chunks documents using tree leaf nodes and generates embeddings in pgvector | Already complete from Phase 2. Chunks table with HNSW index and `match_chunks` RPC exist |
| SEM-02 | User can search documents by semantic similarity using query embedding against stored chunk embeddings | Embed query via `LLMProvider.embed()`, call existing `match_chunks` RPC, aggregate chunk results to document level via DocScore |
| SEM-03 | System computes DocScore per document using `DocScore = (1/sqrt(N+1)) * sum(ChunkScore(n))` to aggregate chunk relevance | Pure Python aggregation over `match_chunks` results, grouping by `doc_id`. Formula normalizes by document size to avoid bias toward longer documents |
| TREE-01 | System performs LLM-powered tree search within selected documents to identify most relevant sections/nodes | Wraps existing `page_index.py` tree search, loading tree JSON from `document_trees` table via `get_tree()`, running concurrent async searches across top-5 documents |
| TREE-02 | System returns specific page ranges and section titles from tree search results with source traceability | Tree nodes already contain `start_index`, `end_index` (page ranges), `title`, and `node_id` for traceability. These are extracted from tree search results and added to the engine-specific result fields |
| ENRICH-03 | User can search documents by comparing query against LLM-generated descriptions | New `match_descriptions` RPC function compares query embedding against pre-embedded description embeddings stored in a new `description_embedding` column on the `documents` table. Requires a new migration to add the column and embed existing descriptions |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| litellm | 1.81.x | Structured outputs for filter generation + query embedding | Already in project; `response_format` with `json_schema` works across Gemini/OpenAI/Anthropic |
| supabase-py | 2.x | Query builder for metadata filtering + RPC calls for vector search | Already in project; PostgREST filter methods eliminate raw SQL |
| pgvector | 0.7+ (Supabase hosted) | HNSW cosine similarity search for chunks and descriptions | Already deployed; HNSW index exists on chunks table |
| pg_trgm | built-in Postgres | Trigram indexes for fuzzy `ILIKE` matching on text metadata columns | Postgres built-in extension; accelerates `ILIKE` patterns that would otherwise seq-scan |
| asyncio | stdlib | Concurrent tree search across multiple documents | Python stdlib; project already uses asyncio for tree indexing |
| tenacity | 9.x | Retry with exponential backoff for LLM filter generation | Already in project; used in ingestion stages |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | 2.x | Validation of filter JSON and result models | Filter schema validation before query execution; result contract type safety |
| dataclasses | stdlib | Lightweight result types if pydantic deemed too heavy | Alternative to pydantic for simple typed containers |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Supabase PostgREST filters | Raw SQL via `pageindex_readonly` role | Raw SQL offers more expressiveness but introduces injection risk, violates locked decision |
| pg_trgm for fuzzy matching | Application-side fuzzy matching (fuzzywuzzy/rapidfuzz) | pg_trgm is faster (DB-level), no round-trip overhead, handles Italian diacritics natively |
| pydantic for validation | Manual dict checking | Pydantic auto-validates types, generates clear error messages, but adds dependency |

**Installation:**
```bash
# pydantic is the only potential new dependency
pip install pydantic>=2.0
```

## Architecture Patterns

### Recommended Project Structure
```
pageindex/
├── retrieval/
│   ├── __init__.py          # re-exports: search_metadata, search_semantic, search_description, tree_search
│   ├── models.py            # RetrievalResult base + engine-specific result types, FilterSchema
│   ├── config.py            # Tunable thresholds: DocScore min, confidence buckets, top-K default
│   ├── metadata.py          # MetadataEngine: LLM filter generation + Supabase query execution
│   ├── semantic.py          # SemanticEngine: embed query + match_chunks + DocScore aggregation
│   ├── description.py       # DescriptionEngine: embed query + match_descriptions RPC
│   ├── tree_search.py       # TreeSearchEngine: async concurrent tree search wrapper
│   └── prompts.py           # System prompts for filter generation (schema injection)
├── db/
│   ├── migrations/
│   │   └── 003_retrieval.sql  # pg_trgm, description_embedding column, match_descriptions RPC
│   └── ...existing modules...
└── ...existing modules...
```

### Pattern 1: Structured Filter Generation via LiteLLM
**What:** Use LiteLLM's `response_format` parameter with `type: "json_schema"` to have the LLM output a flat filter JSON object from a natural language query. The schema defines exact field names, types, and constraints.
**When to use:** Every metadata search query.
**Example:**
```python
# Source: Context7 /websites/litellm_ai - JSON mode docs
from litellm import completion

FILTER_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "metadata_filter",
        "schema": {
            "type": "object",
            "properties": {
                "doc_type": {"type": ["string", "null"]},
                "date_from": {"type": ["string", "null"]},  # ISO date
                "date_to": {"type": ["string", "null"]},    # ISO date
                "authority": {"type": ["string", "null"]},
                "court_level": {"type": ["string", "null"]},
                "legal_area": {
                    "type": ["array", "null"],
                    "items": {"type": "string"},
                },
                "ecli": {"type": ["string", "null"]},
                "parties": {
                    "type": ["array", "null"],
                    "items": {"type": "string"},
                },
            },
            "required": ["doc_type", "date_from", "date_to", "authority",
                         "court_level", "legal_area", "ecli", "parties"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}

response = completion(
    model="gemini/gemini-2.0-flash",
    messages=[
        {"role": "system", "content": system_prompt_with_schema},
        {"role": "user", "content": "sentenze della Corte di Cassazione dal 2020 in materia penale"},
    ],
    response_format=FILTER_JSON_SCHEMA,
    temperature=0,
)
filters = json.loads(response.choices[0].message.content)
# => {"doc_type": "sentenza", "date_from": "2020-01-01", "date_to": null,
#     "authority": "Corte di Cassazione", "court_level": "Cassazione",
#     "legal_area": ["diritto_penale"], "ecli": null, "parties": null}
```

### Pattern 2: Filter-to-Query Translation via Supabase PostgREST
**What:** Translate the flat filter JSON into chained Supabase query builder calls. Each non-null field maps to a specific filter method.
**When to use:** After filter JSON is validated.
**Example:**
```python
# Source: Context7 /websites/supabase_reference_python - filter docs
def build_metadata_query(filters: dict, limit: int = 10):
    client = get_client()
    query = client.table("documents").select("*")

    if filters.get("doc_type"):
        query = query.ilike("doc_type", f"%{filters['doc_type']}%")
    if filters.get("date_from"):
        query = query.gte("date", filters["date_from"])
    if filters.get("date_to"):
        query = query.lte("date", filters["date_to"])
    if filters.get("authority"):
        query = query.ilike("authority", f"%{filters['authority']}%")
    if filters.get("court_level"):
        query = query.ilike("court_level", f"%{filters['court_level']}%")
    if filters.get("legal_area"):
        query = query.overlaps("legal_area", filters["legal_area"])
    if filters.get("ecli"):
        query = query.ilike("ecli", f"%{filters['ecli']}%")
    if filters.get("parties"):
        # Search in JSONB array -- use contains for party name matching
        for party_name in filters["parties"]:
            query = query.ilike("parties", f"%{party_name}%")

    return query.limit(limit).execute()
```

### Pattern 3: DocScore Aggregation
**What:** Group chunk-level similarity results by `doc_id` and compute a document-level score that normalizes by document size.
**When to use:** After `match_chunks` returns chunk-level results.
**Example:**
```python
import math
from collections import defaultdict

def compute_doc_scores(chunk_results: list[dict]) -> list[dict]:
    """Aggregate chunk similarities into document-level DocScores.

    DocScore = (1 / sqrt(N + 1)) * sum(chunk_similarity_i)
    where N = number of matching chunks for the document.
    """
    doc_chunks = defaultdict(list)
    for chunk in chunk_results:
        doc_chunks[chunk["doc_id"]].append(chunk["similarity"])

    doc_scores = []
    for doc_id, similarities in doc_chunks.items():
        n = len(similarities)
        raw_sum = sum(similarities)
        doc_score = (1 / math.sqrt(n + 1)) * raw_sum
        doc_scores.append({"doc_id": doc_id, "score": doc_score, "chunk_count": n})

    return sorted(doc_scores, key=lambda x: x["score"], reverse=True)
```

### Pattern 4: Concurrent Tree Search with asyncio
**What:** Run tree search on multiple documents simultaneously using `asyncio.gather`.
**When to use:** After a preceding engine returns top-5 documents.
**Example:**
```python
import asyncio
from pageindex.db.trees import get_tree

async def tree_search_multi(doc_ids: list[str], query: str, model: str):
    """Run tree search concurrently on multiple documents."""
    async def search_single(doc_id: str):
        tree_row = get_tree(doc_id)
        if tree_row is None:
            return None
        tree_json = tree_row["tree_json"]
        # Adapt existing tree search logic for query-based node selection
        results = await _tree_search_query(tree_json, query, model=model)
        return {"doc_id": doc_id, "sections": results}

    tasks = [search_single(doc_id) for doc_id in doc_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if r is not None and not isinstance(r, Exception)]
```

### Anti-Patterns to Avoid
- **Raw SQL generation by LLM:** Even with `pageindex_readonly`, LLM-generated SQL is fragile, hard to validate, and varies between providers. Use structured JSON filters instead.
- **Global similarity threshold for all engines:** Each engine has different score distributions. DocScore, metadata match count, and description similarity need independent thresholds.
- **Synchronous tree search:** Tree search makes multiple LLM calls per document. Running 5 documents sequentially would be 5x slower. Always use async concurrent execution.
- **Coupling engine implementations:** Engines must work independently. Do not import one engine from another. Phase 4 handles orchestration.
- **Embedding query once and reusing across engines:** The semantic engine and description engine both need query embeddings, but they search different vector spaces. However, since both use the same embedding model and dimensions (768), a single query embedding CAN be shared. Do reuse it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Query embedding generation | Custom embedding pipeline | `LLMProvider.embed([query])` | Already handles batching, dimensions, model selection |
| Vector similarity search | Manual cosine computation in Python | `match_chunks` RPC (pgvector HNSW) | Database-level HNSW index is orders of magnitude faster than Python |
| Fuzzy text matching | Application-level fuzzy matching | Postgres `ILIKE` + `pg_trgm` GIN indexes | DB-level trigram matching handles Italian diacritics, case-insensitive, index-accelerated |
| Retry logic for LLM calls | Custom retry loops | `tenacity` decorators | Already used throughout project; handles exponential backoff correctly |
| JSON schema validation | Manual dict key checking | LiteLLM `response_format` + post-validation | LLM produces schema-conformant output natively; validate after for defense-in-depth |
| Tree structure traversal | New tree walker | Existing `page_index.py` functions + `get_tree()` | The codebase already has battle-tested tree traversal with node selection |

**Key insight:** The heaviest lifting (vector search, fuzzy matching, tree indexing) is already done by existing infrastructure. Phase 3 is primarily orchestration and translation -- taking user queries, converting them to the right format, and routing them through existing capabilities.

## Common Pitfalls

### Pitfall 1: ILIKE Performance Without pg_trgm
**What goes wrong:** `ILIKE '%pattern%'` on text columns triggers sequential scans on the entire `documents` table. At 1000+ documents this is slow but tolerable; at 100K+ it becomes unacceptable.
**Why it happens:** Standard B-tree indexes do not accelerate `ILIKE` with leading wildcard patterns.
**How to avoid:** Enable `pg_trgm` extension and create GIN trigram indexes on the text columns used for `ILIKE` filtering: `doc_type`, `authority`, `court_level`, `ecli`. The migration MUST include `CREATE EXTENSION IF NOT EXISTS pg_trgm` followed by `CREATE INDEX ... USING GIN (column gin_trgm_ops)`.
**Warning signs:** Metadata queries taking >500ms on a corpus of 500+ documents.

### Pitfall 2: DocScore Bias Toward Long Documents
**What goes wrong:** Long documents produce more chunks, so they have more chances to match. A 100-page document with mediocre relevance can outscore a 5-page highly relevant document.
**Why it happens:** Naive sum of chunk similarities grows with chunk count.
**How to avoid:** The `1/sqrt(N+1)` normalization factor in the DocScore formula specifically addresses this. Always use the full formula, never just `sum(similarities)`. Also enforce a minimum per-chunk similarity threshold via `match_threshold` parameter to `match_chunks` RPC so irrelevant chunks don't contribute.
**Warning signs:** Long reference works (codices, annotated laws) consistently ranking above short but targeted judgments.

### Pitfall 3: Filter Schema Drift Between Prompt and Validation
**What goes wrong:** The metadata schema described in the LLM system prompt diverges from the actual JSON schema used for validation, causing the LLM to produce field names or types that fail validation.
**Why it happens:** Schema is defined in two places: the prompt text and the `response_format` JSON schema. They get out of sync during development.
**How to avoid:** Generate both the prompt schema description and the `response_format` JSON schema from a single source of truth (e.g., a Python dict or the `legal_vocabulary.yaml`). The `FILTER_JSON_SCHEMA` dict and the prompt builder function should both derive from the same field definitions.
**Warning signs:** Filter generation consistently failing validation after 3 attempts.

### Pitfall 4: Description Embedding Column Missing for Existing Documents
**What goes wrong:** The description search engine finds zero results because existing documents have `NULL` in the new `description_embedding` column.
**Why it happens:** The migration adds the column but doesn't backfill embeddings for already-ingested documents.
**How to avoid:** The migration must be paired with a backfill script that embeds all existing `doc_description` values and stores the vectors. This can be a one-time Python script or an RPC-based batch operation.
**Warning signs:** Description search returning empty results despite having 50+ documents with non-null `doc_description`.

### Pitfall 5: Parties Field JSONB Filtering Complexity
**What goes wrong:** The `parties` column is JSONB (`[{name, role}]`), but `ILIKE` on JSONB doesn't work like on text columns. Searching for a party name inside the JSONB array requires a different approach.
**Why it happens:** PostgREST's `.ilike()` expects a text column, not JSONB.
**How to avoid:** For party name search, cast JSONB to text and use `ILIKE`, or use a Postgres RPC function that does `jsonb_array_elements_text` matching. The simplest approach: use Supabase `.filter("parties::text", "ilike", f"%{name}%")` to cast to text for pattern matching. Alternatively, create a dedicated RPC for party search.
**Warning signs:** Party name filters being silently ignored or throwing type errors.

### Pitfall 6: Tree Search Assumes Full Text in Tree JSON
**What goes wrong:** Tree search wrapper tries to access `text` fields on tree nodes, but `stage_store` strips text keys before saving to reduce DB storage.
**Why it happens:** The ingestion pipeline deliberately removes text from tree JSON to save space (see `_strip_text_from_tree` in stages.py).
**How to avoid:** Tree search must reconstruct text by reading from the PDF file or from the chunks table. The existing `page_index.py` functions that need `page_list` can use the original PDF, or for an already-ingested document, the text can be reconstructed from stored chunks using `get_chunks_by_doc()`.
**Warning signs:** Tree search returning sections with empty text or `None` node content.

## Code Examples

### Metadata Engine: Complete Filter Generation and Execution
```python
# Source: Project codebase patterns + Context7 LiteLLM/Supabase docs
import json
from tenacity import retry, stop_after_attempt, wait_random_exponential
from litellm import completion
from pageindex.db.client import get_client

TOTAL_FILTER_FIELDS = 8  # doc_type, date_from, date_to, authority, court_level, legal_area, ecli, parties

@retry(wait=wait_random_exponential(min=1, max=30), stop=stop_after_attempt(3))
def generate_filters(query: str, model: str, system_prompt: str) -> dict:
    """Generate structured metadata filters from a natural language query."""
    response = completion(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
        response_format=FILTER_JSON_SCHEMA,
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)


def score_metadata_results(results: list[dict], filters: dict) -> list[dict]:
    """Score documents by how many filter fields they matched."""
    for doc in results:
        match_count = 0
        if filters.get("doc_type") and doc.get("doc_type"):
            if filters["doc_type"].lower() in doc["doc_type"].lower():
                match_count += 1
        if filters.get("date_from") and doc.get("date"):
            if doc["date"] >= filters["date_from"]:
                match_count += 1
        # ... similar for each field
        doc["score"] = match_count / TOTAL_FILTER_FIELDS
    return sorted(results, key=lambda x: x["score"], reverse=True)
```

### Description Search: RPC Function (SQL)
```sql
-- New RPC for description embedding similarity search
CREATE OR REPLACE FUNCTION match_descriptions(
    query_embedding vector(768),
    match_threshold float DEFAULT 0.7,
    match_count int DEFAULT 10
)
RETURNS TABLE (
    doc_id UUID,
    doc_name TEXT,
    doc_description TEXT,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.doc_id,
        d.doc_name,
        d.doc_description,
        1 - (d.description_embedding <=> query_embedding) AS similarity
    FROM documents d
    WHERE d.description_embedding IS NOT NULL
      AND 1 - (d.description_embedding <=> query_embedding) > match_threshold
    ORDER BY d.description_embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
```

### Uniform Result Contract
```python
from dataclasses import dataclass, field

@dataclass
class RetrievalResult:
    """Base result returned by all retrieval engines."""
    doc_id: str
    score: float
    metadata: dict          # Full legal metadata from documents table
    engine_name: str        # "metadata", "semantic", "description", "tree_search"
    confidence: str         # "high", "medium", "low"

@dataclass
class MetadataResult(RetrievalResult):
    """Metadata engine adds the parsed filter for transparency."""
    parsed_filters: dict = field(default_factory=dict)

@dataclass
class TreeSearchResult(RetrievalResult):
    """Tree search engine adds section titles and page ranges."""
    sections: list[dict] = field(default_factory=list)
    # Each section: {"title": str, "start_page": int, "end_page": int, "node_id": str}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LLM generates raw SQL for metadata queries | LLM fills structured JSON schema, app translates to PostgREST queries | CONTEXT.md decision (2026-02-22) | Eliminates SQL injection risk, makes validation trivial, works cross-provider |
| Separate embedding call per description query | Pre-embed descriptions at ingestion time, compare via cosine similarity at query time | CONTEXT.md decision (2026-02-22) | Eliminates per-query LLM cost for description search, sub-100ms response |
| LiteLLM JSON mode (`type: "json_object"`) | LiteLLM JSON schema mode (`type: "json_schema"`) | LiteLLM ~1.50+ / Gemini 2.0+ | Strict schema adherence, works natively on Gemini 2.0+ without workarounds |

**Deprecated/outdated:**
- Raw SQL generation for metadata retrieval: Replaced by structured JSON filter approach per user decision
- Single `match_chunks` for all similarity search: Need new `match_descriptions` RPC for document-level description similarity (different vector space)

## Open Questions

1. **Hosted Supabase pgvector version**
   - What we know: Migration 001 uses `vector(768)` and HNSW index, which requires pgvector 0.5+. The `match_chunks` RPC works.
   - What's unclear: Exact pgvector version on hosted Supabase (STATE.md flags this as a concern). HNSW with half-precision vectors requires 0.7+, but we use full-precision `vector(768)` so 0.5+ is sufficient.
   - Recommendation: Verify with `SELECT extversion FROM pg_extension WHERE extname = 'vector'` before deploying. Current schema works with any pgvector 0.5+.

2. **DocScore formula inconsistency**
   - What we know: STATE.md notes "DocScore aggregation formula inconsistency between FEATURES.md and ARCHITECTURE.md -- resolve during Phase 3 planning."
   - What's unclear: Which variant is canonical. REQUIREMENTS.md uses `DocScore = (1/sqrt(N+1)) * sum(ChunkScore(n))`.
   - Recommendation: Use the REQUIREMENTS.md formula as canonical. It's mathematically sound: normalizes by chunk count to prevent long-document bias while still rewarding multi-chunk relevance. The `1/sqrt(N+1)` factor means a document with 1 chunk at similarity 0.9 gets score `0.9/sqrt(2) = 0.636`, while a document with 4 chunks at 0.6 each gets `2.4/sqrt(5) = 1.073`. This correctly rewards broader relevance.

3. **Tree search text source for stored documents**
   - What we know: Tree JSON stored in DB has text fields stripped. Original PDFs may or may not be accessible at query time.
   - What's unclear: Whether to re-extract from PDF or reconstruct from stored chunks.
   - Recommendation: Use chunks from `get_chunks_by_doc()` as the primary text source since they are always available in DB. Map chunks to tree nodes via `node_id`. If a user provides a PDF path at query time, use that instead for full fidelity.

4. **Description embedding backfill strategy**
   - What we know: Existing ingested documents have `doc_description` text but no `description_embedding` vector.
   - What's unclear: Whether to batch-embed during migration or provide a separate backfill script.
   - Recommendation: Provide a Python backfill function `backfill_description_embeddings()` that reads all documents with non-null `doc_description` and null `description_embedding`, embeds them in batches of 250, and updates the rows. Run this once after migration 003.

## Sources

### Primary (HIGH confidence)
- Context7 `/websites/litellm_ai` -- JSON schema structured outputs, `response_format` parameter, Gemini 2.0 native JSON schema support
- Context7 `/websites/supabase_reference_python` -- `.ilike()`, `.overlaps()`, `.contains()`, `.gte()`, `.lte()`, `.filter()`, `.or_()` methods, RPC calls
- Supabase official docs (via MCP search) -- semantic search patterns with pgvector, `match_documents` RPC pattern, HNSW indexing
- Project codebase -- `pageindex/db/migrations/001_initial_schema.sql` (existing schema, match_chunks RPC, pageindex_readonly role), `pageindex/llm/provider.py` (LLMProvider), `pageindex/ingestion/stages.py` (metadata extraction pattern), `pageindex/db/chunks.py` (match_chunks wrapper)

### Secondary (MEDIUM confidence)
- Supabase docs on full text search -- `pg_trgm` not directly documented but is a standard Postgres extension available on Supabase hosted
- PostgreSQL documentation -- `pg_trgm` extension for trigram-based GIN indexes with `gin_trgm_ops`

### Tertiary (LOW confidence)
- Exact pgvector version on hosted Supabase -- needs runtime verification (see Open Questions)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, patterns verified via Context7 and codebase
- Architecture: HIGH -- patterns follow existing codebase conventions (db modules, LLM provider, ingestion stages)
- Pitfalls: HIGH -- derived from codebase analysis (stripped text in trees, JSONB party structure, missing backfill)
- DocScore formula: MEDIUM -- mathematically sound but needs validation against real corpus data to tune thresholds

**Research date:** 2026-02-23
**Valid until:** 2026-03-23 (stable domain, no fast-moving dependencies)
