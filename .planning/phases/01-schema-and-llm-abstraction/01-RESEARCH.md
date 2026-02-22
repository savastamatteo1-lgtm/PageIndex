# Phase 1: Schema and LLM Abstraction - Research

**Researched:** 2026-02-22
**Domain:** Supabase database schema (Postgres + pgvector), Italian legal metadata modeling, LiteLLM provider-agnostic abstraction
**Confidence:** HIGH

## Summary

Phase 1 builds two foundational pillars: (1) a Supabase Postgres database with three tables (`documents`, `chunks`, `document_trees`) storing Italian legal document metadata with pgvector embeddings, and (2) a LiteLLM-based abstraction layer that wraps all LLM completion and embedding calls behind a provider-agnostic interface. The existing codebase uses Google Gemini SDK directly (`google-genai`) throughout `utils.py` with hardcoded `Gemini_API`, `Gemini_API_async`, and `_gemini_client` calls -- this phase replaces that coupling without breaking existing single-document functionality.

A critical finding is that Google's `text-embedding-004` model was deprecated on January 14, 2026. The replacement is `gemini-embedding-001` (3072 default dimensions, configurable down to 768 via Matryoshka Representation Learning). The CONTEXT.md decision to use `text-embedding-004` must be updated. LiteLLM supports `gemini/gemini-embedding-001` via its direct SDK (not proxy), with `output_dimensionality` controllable through the `dimensions` parameter.

The Supabase Python client (`supabase==2.28.0`) handles standard CRUD operations. For vector similarity search, PostgREST does not support pgvector operators (`<->`, `<=>`, `<#>`) directly -- queries must be wrapped in Postgres functions and called via `.rpc()`. HNSW indexes should be created at table creation time (unlike IVFFlat, no data is needed first). The schema uses dedicated columns for all common Italian legal metadata fields and JSONB only as an overflow safety valve, per user decisions.

**Primary recommendation:** Use LiteLLM (`litellm==1.81.x`) as a thin wrapper with `completion()`/`acompletion()`/`embedding()`/`aembedding()` functions, Supabase Python client for data operations with SQL migrations for schema DDL, and `gemini-embedding-001` (not the deprecated `text-embedding-004`) as the default embedding model with 768 dimensions for pgvector compatibility.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Document types (doc_type)**: Full legal corpus -- sentenze, ordinanze, decreti, leggi, decreti legislativi, decreti legge, regolamenti, circolari, pareri, delibere, atti parlamentari, and any other document type encountered
- **Legal areas (legal_area)**: Granular sub-areas with nested taxonomy (e.g., diritto civile > obbligazioni, famiglia, successioni, reale; diritto penale > reati contro la persona, reati informatici, etc.)
- **Legal area multiplicity**: A document can have multiple legal areas (array field) -- many documents span topics
- **Court levels (court_level)**: Court tier only, not individual courts -- Cassazione, Corte d'Appello, Tribunale, Giudice di Pace, Corte Costituzionale, TAR, Consiglio di Stato, and other levels as encountered
- **Enum style**: Open text with documented conventions -- no hardcoded enums. Standard values are documented but new values can be added freely without schema migrations. The LLM extractor uses the documented conventions as guidance.
- **Parties**: Structured JSONB objects with name and role -- `[{name: 'Mario Rossi', role: 'ricorrente'}, {name: 'Luigi Bianchi', role: 'resistente'}]`. Roles include ricorrente, resistente, imputato, parte civile, etc.
- **Cross-references**: Structured JSONB with reference, source, and type -- `[{ref: 'art. 2043', source: 'codice civile', type: 'legislation'}, {ref: '12345/2020', source: 'Cassazione', type: 'case_law'}]`. Types: legislation, case_law, regulation, EU law, etc.
- **JSONB additional_fields**: Overflow only -- safety valve for rare document types. All common fields get dedicated columns. JSONB is not an experimental ground for testing new fields.
- **Legal area storage**: Array column (text[]) since documents can belong to multiple granular sub-areas
- **Default embedding model**: Gemini text-embedding-004 (multilingual, supports Italian legal text) -- **NOTE: DEPRECATED as of 2026-01-14. Must use gemini-embedding-001 instead.**
- **Swappability**: Embedding model configurable via config, same as LLM provider
- **Vector dimensions**: Configurable via config (read from model settings), not hardcoded
- **Corpus scale**: Designed for 10K+ documents -- HNSW index recommended from the start
- **LLM abstraction**: LiteLLM as specified in requirements (FOUND-03)
- **Taxonomy language**: Standard Italian legal terminology, not translated English equivalents
- **Court hierarchy**: Italian hierarchy (Giudice di Pace < Tribunale < Corte d'Appello < Cassazione for ordinary; TAR < Consiglio di Stato for administrative)
- **Vocabulary approach**: Open conventions -- LLM metadata extractor in Phase 2 references a documented vocabulary file/config, not database constraints

### Claude's Discretion
- Exact Supabase table structure and column types (within the constraints above)
- Migration strategy and SQL implementation
- LiteLLM wrapper design and configuration file format
- HNSW index parameters (m, ef_construction) -- optimize for the scale
- How to handle the tree JSON structure storage in document_trees table
- Read-only database role setup for query safety

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FOUND-01 | System provides a Supabase document registry that stores document metadata, tree JSON structures, and embedding references with unique `doc_id` identifiers | Supabase Python client (`supabase==2.28.0`) supports table operations via `.table().insert()/.select()`. Schema design uses UUID `doc_id` as primary key across `documents`, `chunks`, and `document_trees` tables. Tree JSON stored as JSONB column. |
| FOUND-02 | System implements Italian legal metadata schema with fields: `doc_type`, `date`, `authority`, `ecli`, `gu_number`, `legal_area`, `parties`, `court_level`, `cross_references`, plus flexible JSONB for additional fields | Postgres supports all required types: TEXT for open-enum fields, DATE for date, TEXT[] for legal_area arrays, JSONB for parties/cross_references/additional_fields. GIN indexes on JSONB columns for query performance. |
| FOUND-03 | System uses LiteLLM as provider-agnostic LLM abstraction layer supporting Gemini, OpenAI, Anthropic, and local models without code changes | LiteLLM (`litellm==1.81.x`) provides `completion()`/`acompletion()`/`embedding()`/`aembedding()` with provider prefix model naming (`gemini/model-name`, `openai/model-name`, `anthropic/model-name`). Switching provider requires only changing model string and API key env var. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `litellm` | 1.81.x | Provider-agnostic LLM completion and embedding calls | 100+ providers, OpenAI-compatible format, unified error handling, MIT license, actively maintained (released 2026-02-22) |
| `supabase` | 2.28.0 | Python client for Supabase Postgres operations | Official Supabase Python client, supports table CRUD, RPC calls, auth, storage. Released 2026-02-10 |
| pgvector (Supabase extension) | 0.7.x+ (hosted) | Vector similarity search in Postgres | Built into Supabase, supports HNSW indexes, cosine/L2/inner-product distance |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `python-dotenv` | 1.1.0 | Load environment variables from .env file | Already in project, used for API keys (GOOGLE_API_KEY, SUPABASE_URL, SUPABASE_KEY) |
| `pyyaml` | 6.0.2 | YAML config file parsing | Already in project, extend for LLM provider and embedding model configuration |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `litellm` | Direct provider SDKs (google-genai, openai) | More control, but vendor lock-in and duplicate code per provider |
| `supabase` Python client | `psycopg2`/`asyncpg` direct | More SQL control, but lose Supabase client conveniences (auth, RLS, realtime) |
| `supabase` Python client | `vecs` (Supabase vector client) | Purpose-built for vectors, but only handles vectors -- not general metadata CRUD |
| pgvector HNSW | pgvector IVFFlat | IVFFlat needs data before index creation; HNSW works immediately and handles data changes better |

**Installation:**
```bash
pip install litellm supabase python-dotenv pyyaml
```

## Architecture Patterns

### Recommended Project Structure
```
pageindex/
├── __init__.py              # Existing -- extend exports
├── config.yaml              # Existing -- extend with llm/embedding/supabase settings
├── page_index.py            # Existing -- single-document indexing (untouched)
├── page_index_md.py         # Existing -- markdown indexing (untouched)
├── utils.py                 # Existing -- refactor LLM calls to use new abstraction
├── db/
│   ├── __init__.py
│   ├── client.py            # Supabase client initialization and connection management
│   ├── documents.py         # Documents table operations (insert, get, query)
│   ├── chunks.py            # Chunks table operations (insert, get, vector search)
│   ├── trees.py             # Document trees table operations
│   └── migrations/
│       └── 001_initial_schema.sql  # DDL for all tables, indexes, extensions, roles
├── llm/
│   ├── __init__.py
│   ├── provider.py          # LiteLLM wrapper: completion, acompletion, embedding, aembedding
│   └── config.py            # LLM/embedding model configuration loading
└── schema/
    └── legal_vocabulary.yaml  # Documented conventions for Italian legal terms
```

### Pattern 1: LiteLLM Provider Abstraction
**What:** A thin wrapper module around LiteLLM that reads model configuration from config.yaml and exposes `complete()`, `acomplete()`, `embed()`, `aembed()` functions. Call sites never import litellm directly.
**When to use:** Every LLM or embedding call in the system.
**Example:**
```python
# Source: https://docs.litellm.ai/docs/providers/gemini
# pageindex/llm/provider.py
import litellm
from litellm import completion, acompletion, embedding, aembedding

class LLMProvider:
    def __init__(self, config: dict):
        self.completion_model = config["completion_model"]  # e.g. "gemini/gemini-2.0-flash"
        self.embedding_model = config["embedding_model"]    # e.g. "gemini/gemini-embedding-001"
        self.embedding_dimensions = config.get("embedding_dimensions", 768)
        # LiteLLM reads API keys from env vars (GEMINI_API_KEY, OPENAI_API_KEY, etc.)

    def complete(self, messages: list[dict], **kwargs) -> str:
        response = completion(
            model=self.completion_model,
            messages=messages,
            temperature=kwargs.get("temperature", 0),
        )
        return response.choices[0].message.content

    async def acomplete(self, messages: list[dict], **kwargs) -> str:
        response = await acompletion(
            model=self.completion_model,
            messages=messages,
            temperature=kwargs.get("temperature", 0),
        )
        return response.choices[0].message.content

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = embedding(
            model=self.embedding_model,
            input=texts,
            dimensions=self.embedding_dimensions,
        )
        return [item["embedding"] for item in response.data]

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        response = await aembedding(
            model=self.embedding_model,
            input=texts,
            dimensions=self.embedding_dimensions,
        )
        return [item["embedding"] for item in response.data]
```

**Switching providers** requires only config changes:
```yaml
# config.yaml -- Gemini
completion_model: "gemini/gemini-2.0-flash"
embedding_model: "gemini/gemini-embedding-001"
embedding_dimensions: 768

# config.yaml -- OpenAI (zero code changes)
completion_model: "openai/gpt-4o"
embedding_model: "openai/text-embedding-3-small"
embedding_dimensions: 768
```

### Pattern 2: Supabase Client Singleton
**What:** A module that initializes the Supabase client once from env vars and exposes it for all database operations.
**When to use:** All database access throughout the application.
**Example:**
```python
# Source: https://supabase.com/docs/reference/python/llms/python
# pageindex/db/client.py
import os
from supabase import create_client, Client

_client: Client | None = None

def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client
```

### Pattern 3: SQL Migration Files
**What:** Plain SQL files versioned in the repository, applied via Supabase MCP tools (`apply_migration`) or Supabase CLI. No ORM.
**When to use:** All DDL operations (CREATE TABLE, CREATE INDEX, CREATE FUNCTION, CREATE ROLE).
**Example:**
```sql
-- pageindex/db/migrations/001_initial_schema.sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- Documents table with Italian legal metadata
CREATE TABLE IF NOT EXISTS documents (
    doc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_name TEXT NOT NULL,
    doc_description TEXT,

    -- Italian legal metadata (open text, no enums)
    doc_type TEXT,                    -- sentenza, ordinanza, decreto, legge, etc.
    date DATE,                       -- document date
    authority TEXT,                   -- issuing authority
    ecli TEXT,                       -- European Case Law Identifier
    gu_number TEXT,                  -- Gazzetta Ufficiale number
    legal_area TEXT[],               -- array of legal sub-areas
    parties JSONB DEFAULT '[]',      -- [{name, role}]
    court_level TEXT,                -- Cassazione, Corte d'Appello, Tribunale, etc.
    cross_references JSONB DEFAULT '[]', -- [{ref, source, type}]

    -- Flexible overflow
    additional_fields JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Document trees (one tree per document)
CREATE TABLE IF NOT EXISTS document_trees (
    tree_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    tree_json JSONB NOT NULL,        -- full tree structure from PageIndex
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(doc_id)                   -- one tree per document
);

-- Chunks with embeddings (leaf nodes from tree)
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    node_id TEXT,                     -- node_id from tree structure
    content TEXT NOT NULL,            -- chunk text content
    embedding vector(768),           -- configurable dimensions, default 768
    metadata JSONB DEFAULT '{}',     -- node title, start/end page, etc.
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for vector similarity search (cosine distance)
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
    ON chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- GIN indexes for JSONB query performance
CREATE INDEX IF NOT EXISTS documents_parties_gin_idx
    ON documents USING GIN (parties);
CREATE INDEX IF NOT EXISTS documents_cross_refs_gin_idx
    ON documents USING GIN (cross_references);

-- B-tree indexes for common filter columns
CREATE INDEX IF NOT EXISTS documents_doc_type_idx ON documents (doc_type);
CREATE INDEX IF NOT EXISTS documents_date_idx ON documents (date);
CREATE INDEX IF NOT EXISTS documents_court_level_idx ON documents (court_level);
CREATE INDEX IF NOT EXISTS documents_ecli_idx ON documents (ecli);

-- GIN index for text[] array column
CREATE INDEX IF NOT EXISTS documents_legal_area_idx
    ON documents USING GIN (legal_area);
```

### Pattern 4: Vector Search via RPC
**What:** PostgREST does not support pgvector operators directly. Wrap vector queries in Postgres functions and call via `supabase.rpc()`.
**When to use:** All vector similarity searches.
**Example:**
```sql
-- Postgres function for semantic search
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(768),
    match_threshold float DEFAULT 0.7,
    match_count int DEFAULT 20
)
RETURNS TABLE (
    chunk_id UUID,
    doc_id UUID,
    content TEXT,
    metadata JSONB,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.chunk_id,
        c.doc_id,
        c.content,
        c.metadata,
        1 - (c.embedding <=> query_embedding) AS similarity
    FROM chunks c
    WHERE 1 - (c.embedding <=> query_embedding) > match_threshold
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
```

```python
# Python call via Supabase client
# Source: https://supabase.com/docs/reference/python/rpc
response = supabase.rpc("match_chunks", {
    "query_embedding": query_vector,  # list of floats
    "match_threshold": 0.7,
    "match_count": 20,
}).execute()
```

### Anti-Patterns to Avoid
- **Direct pgvector operators in PostgREST**: PostgREST does not support `<=>`, `<->`, `<#>` operators. Always use RPC functions.
- **Hardcoded enum constraints in DB**: User decision is open text with documented conventions. Do NOT create `CHECK` constraints or Postgres ENUMs for doc_type, court_level, etc.
- **Importing litellm directly in business logic**: All LLM calls go through the wrapper. Consuming modules import from `pageindex.llm.provider`, never from `litellm`.
- **Using IVFFlat indexes**: HNSW is strictly better for this use case (works on empty tables, handles incremental data, better recall).
- **Storing embeddings as JSONB arrays**: Always use the native `vector` type from pgvector for proper indexing and distance operations.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM provider abstraction | Custom adapter per provider | LiteLLM | 100+ providers, unified error handling, token counting, cost tracking built in |
| Embedding generation | Direct Google/OpenAI SDK calls | LiteLLM `embedding()`/`aembedding()` | Same abstraction, handles retries, model-specific parameter translation |
| Vector similarity search | Custom cosine similarity in Python | pgvector with HNSW index in Postgres | Orders of magnitude faster, scales to millions of vectors, leverages DB query planner |
| Token counting | Custom tokenizer per model | LiteLLM `token_counter()` | Handles model-specific tokenizers, falls back to tiktoken |
| Database connection management | Manual psycopg2 connections | Supabase Python client | Connection pooling, auth integration, RPC support built in |
| UUID generation | Python `uuid4()` | Postgres `gen_random_uuid()` | Database-generated, guaranteed unique at insert time, no round-trip |
| JSONB validation | Python-side validation of parties/cross-refs structure | Postgres CHECK constraints (optional) or application-level validation | JSONB is schema-flexible by design; validate at application layer before insert |

**Key insight:** This phase is infrastructure plumbing. Every component (database client, LLM calls, vector indexing) has mature, well-tested libraries. The value is in correct integration and clean interfaces, not in reimplementation.

## Common Pitfalls

### Pitfall 1: text-embedding-004 Deprecation
**What goes wrong:** Using the deprecated `text-embedding-004` model which was shut down on January 14, 2026.
**Why it happens:** CONTEXT.md specifies `text-embedding-004` based on earlier research, but Google deprecated it.
**How to avoid:** Use `gemini/gemini-embedding-001` as the default embedding model. It produces 3072 dimensions by default but supports `output_dimensionality` parameter to reduce to 768 or 1536.
**Warning signs:** API errors from Google when calling `text-embedding-004`, 404 or model-not-found responses.

### Pitfall 2: Vector Dimension Mismatch
**What goes wrong:** Embedding model produces N-dimensional vectors, but the `vector(M)` column expects M dimensions where N != M.
**Why it happens:** Changing the embedding model without updating the vector column size, or forgetting to set `dimensions` parameter on the LiteLLM `embedding()` call.
**How to avoid:** Read `embedding_dimensions` from config.yaml and pass it to both the `embedding()` call and use it for the `vector()` column definition. The default `gemini-embedding-001` produces 3072, but we configure it to output 768 for pgvector compatibility (vector type supports up to 2000 dimensions; halfvec up to 4000).
**Warning signs:** Insert errors on the `chunks` table, dimension mismatch exceptions.

### Pitfall 3: PostgREST Vector Operator Limitation
**What goes wrong:** Trying to use pgvector distance operators (`<=>`, `<->`, `<#>`) directly through the Supabase Python client's `.select()` or `.filter()`.
**Why it happens:** PostgREST (which underlies the Supabase client) does not support these custom operators.
**How to avoid:** Always create Postgres functions for vector operations and call them via `supabase.rpc()`.
**Warning signs:** SQL syntax errors or "operator does not exist" errors from PostgREST.

### Pitfall 4: Breaking Existing Codebase
**What goes wrong:** Refactoring `utils.py` to use LiteLLM breaks existing `page_index.py` and `page_index_md.py` which depend on `Gemini_API`, `ChatGPT_API`, `Gemini_API_async`, `ChatGPT_API_async`, and `count_tokens`.
**Why it happens:** The existing code imports these functions via `from .utils import *` and uses them extensively.
**How to avoid:** Keep backward-compatible function signatures in `utils.py` that delegate to the new LLM provider. The old function names (`Gemini_API`, `ChatGPT_API`, etc.) remain but internally use the new abstraction. Alternatively, the new `llm/provider.py` module is used by new code while `utils.py` legacy functions are gradually migrated.
**Warning signs:** ImportError or changed return types in existing tests/functionality.

### Pitfall 5: Gemini Model Naming in LiteLLM
**What goes wrong:** Using bare model names (e.g., `gemini-2.0-flash`) without the `gemini/` prefix in LiteLLM, which causes it to route to Vertex AI instead of Google AI Studio.
**Why it happens:** LiteLLM requires the `gemini/` prefix to route to the Google AI Studio API (using `GEMINI_API_KEY`). Without the prefix, it defaults to Vertex AI (requiring full GCP credentials).
**How to avoid:** Always use the `gemini/` prefix: `gemini/gemini-2.0-flash`, `gemini/gemini-embedding-001`, etc.
**Warning signs:** Authentication errors mentioning Vertex AI or GCP credentials when you expected to use `GEMINI_API_KEY`.

### Pitfall 6: HNSW Index on Empty Table is Fine (Don't Wait)
**What goes wrong:** Delaying HNSW index creation until after data is loaded (unnecessary with HNSW).
**Why it happens:** Confusion with IVFFlat indexes, which do require pre-existing data for training.
**How to avoid:** Create HNSW index in the initial migration. Unlike IVFFlat, HNSW indexes build incrementally as data is inserted.
**Warning signs:** N/A -- this is a non-issue if you create the index upfront.

### Pitfall 7: Read-Only Role Not Preventing Function Execution
**What goes wrong:** A read-only role can still execute functions that perform writes if the function is defined as `SECURITY DEFINER`.
**Why it happens:** `SECURITY DEFINER` functions run with the privileges of the function creator, not the caller.
**How to avoid:** The read-only role for LLM-generated SQL should only have SELECT privileges on tables. RPC functions for vector search should be `SECURITY INVOKER` (the default) so they respect the caller's role.
**Warning signs:** Unexpected write operations succeeding through the read-only role.

## Code Examples

Verified patterns from official sources:

### LiteLLM Completion (Sync + Async)
```python
# Source: https://docs.litellm.ai/docs/providers/gemini
import litellm
import os

os.environ["GEMINI_API_KEY"] = "your-key"

# Sync completion
response = litellm.completion(
    model="gemini/gemini-2.0-flash",
    messages=[{"role": "user", "content": "Hello"}],
    temperature=0,
)
print(response.choices[0].message.content)

# Async completion
response = await litellm.acompletion(
    model="gemini/gemini-2.0-flash",
    messages=[{"role": "user", "content": "Hello"}],
    temperature=0,
)
print(response.choices[0].message.content)
```

### LiteLLM Embedding with Configurable Dimensions
```python
# Source: https://docs.litellm.ai/docs/embedding/supported_embedding
from litellm import embedding

response = embedding(
    model="gemini/gemini-embedding-001",
    input=["Sentenza della Corte di Cassazione in materia di responsabilita civile"],
    dimensions=768,  # configurable: 768, 1536, or 3072
)
vector = response.data[0]["embedding"]  # list of 768 floats
```

### LiteLLM Token Counting
```python
# Source: https://docs.litellm.ai/docs/completion/token_usage
from litellm import token_counter

count = token_counter(
    model="gemini/gemini-2.0-flash",
    messages=[{"role": "user", "content": "some text"}]
)
```

### Supabase Client Initialization
```python
# Source: https://supabase.com/docs/reference/python/llms/python
import os
from supabase import create_client, Client

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_KEY"]
supabase: Client = create_client(url, key)
```

### Supabase Insert and Select
```python
# Source: https://supabase.com/docs/reference/python/llms/python
# Insert a document
response = supabase.table("documents").insert({
    "doc_name": "Sentenza 12345/2024",
    "doc_type": "sentenza",
    "date": "2024-03-15",
    "authority": "Corte di Cassazione",
    "court_level": "Cassazione",
    "legal_area": ["diritto civile", "obbligazioni"],
    "parties": [
        {"name": "Mario Rossi", "role": "ricorrente"},
        {"name": "Luigi Bianchi", "role": "resistente"}
    ],
}).execute()

doc_id = response.data[0]["doc_id"]

# Retrieve by doc_id
response = supabase.table("documents").select("*").eq("doc_id", doc_id).execute()
```

### Supabase RPC for Vector Search
```python
# Source: https://supabase.com/docs/reference/python/rpc
query_embedding = llm_provider.embed(["responsabilita contrattuale"])[0]

response = supabase.rpc("match_chunks", {
    "query_embedding": query_embedding,
    "match_threshold": 0.7,
    "match_count": 20,
}).execute()

for chunk in response.data:
    print(f"Doc: {chunk['doc_id']}, Similarity: {chunk['similarity']:.3f}")
```

### Read-Only Role Creation
```sql
-- Create a read-only role for LLM-generated SQL queries (Phase 3)
CREATE ROLE pageindex_readonly WITH LOGIN PASSWORD 'secure_password_here';
GRANT USAGE ON SCHEMA public TO pageindex_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO pageindex_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO pageindex_readonly;
-- Explicitly deny write permissions
REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM pageindex_readonly;
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `text-embedding-004` (768d) | `gemini-embedding-001` (3072d, configurable) | 2026-01-14 (deprecation) | Must use new model; supports Matryoshka dimension reduction |
| IVFFlat vector index | HNSW vector index | pgvector 0.5+ (2023) | HNSW is default recommendation; works on empty tables, better recall |
| Direct Google Gemini SDK (`google-genai`) | LiteLLM provider-agnostic wrapper | Project decision | Removes vendor lock-in; supports 100+ LLM providers |
| pgvector max 2000 dimensions (vector type) | halfvec type supports up to 4000 dimensions | pgvector 0.7+ | Option to store full 3072d embeddings using halfvec if needed |
| `supabase` Python client v1.x | `supabase` v2.28.0 | 2025 | Improved async support, better typing |

**Deprecated/outdated:**
- `text-embedding-004`: Shut down 2026-01-14. Replaced by `gemini-embedding-001`.
- `embedding-001` (legacy Gemini): Shut down 2025-08-14. Also replaced by `gemini-embedding-001`.
- IVFFlat indexes for new projects: HNSW is universally recommended for new deployments.
- `google-genai` direct usage: Still works but creates vendor lock-in. LiteLLM wraps it.

## Open Questions

1. **Supabase hosted pgvector version**
   - What we know: Supabase provides pgvector as a built-in extension. STATE.md notes that the hosted version may not be 0.8.x.
   - What's unclear: The exact pgvector version on the user's Supabase instance. This affects whether `halfvec` type (0.7+) is available.
   - Recommendation: Check the pgvector version via `SELECT extversion FROM pg_extension WHERE extname = 'vector';` during setup. Use `vector(768)` with dimensionality reduction as the safe default. If pgvector >= 0.7, `halfvec(3072)` is an option for full-resolution embeddings.

2. **gemini-embedding-001 via LiteLLM stability**
   - What we know: LiteLLM supports `gemini/gemini-embedding-001` in direct SDK mode. There are reported proxy issues (405 errors) but the direct SDK path works.
   - What's unclear: Whether the `dimensions` parameter is correctly passed through to the Gemini API as `output_dimensionality`.
   - Recommendation: Test the embedding call early in implementation. If `dimensions` is not passed through, use `litellm.drop_params = True` and pass `output_dimensionality` as an extra parameter, or patch via litellm's provider-specific params.

3. **Config file format evolution**
   - What we know: Existing `config.yaml` has PageIndex-specific settings (model, toc_check_page_num, etc.). New settings for LLM provider, embedding model, Supabase connection are needed.
   - What's unclear: Whether to extend the existing `config.yaml` or create a separate config for the retrieval system.
   - Recommendation: Extend the existing `config.yaml` with new sections (`llm`, `embedding`, `supabase`). Keep backward compatibility with existing keys. The `ConfigLoader` class in `utils.py` already handles YAML merging.

4. **Backward compatibility with `Gemini_API` functions**
   - What we know: `utils.py` exposes `Gemini_API`, `Gemini_API_async`, `ChatGPT_API`, `ChatGPT_API_async`, `count_tokens` -- all used by existing `page_index.py` and `page_index_md.py`.
   - What's unclear: Whether to refactor these in-place or create a parallel abstraction.
   - Recommendation: Create the new `llm/provider.py` module for new code. Refactor `utils.py` functions to delegate to the new module internally, preserving existing function signatures for backward compatibility. The existing `google-genai` import and `_gemini_client` can be removed once all callers go through LiteLLM.

## Sources

### Primary (HIGH confidence)
- LiteLLM docs (Context7 `/websites/litellm_ai`) - Provider configuration, embedding models, completion API, token counting
- Supabase Python reference (Context7 `/websites/supabase_reference_python`) - Client initialization, table operations, RPC calls
- [Supabase HNSW indexes docs](https://supabase.com/docs/guides/ai/vector-indexes/hnsw-indexes) - HNSW creation syntax, operator classes, dimension limits
- [Supabase vector columns docs](https://supabase.com/docs/guides/ai/vector-columns) - Vector column creation, dimension specs, RPC requirement
- [Supabase Postgres roles docs](https://supabase.com/docs/guides/database/postgres/roles) - Role system, GRANT syntax, predefined roles
- [LiteLLM Gemini provider docs](https://docs.litellm.ai/docs/providers/gemini) - `gemini/` prefix, API key setup, supported models
- [LiteLLM embedding docs](https://docs.litellm.ai/docs/embedding/supported_embedding) - Gemini embedding models, aembedding async support
- [LiteLLM token usage docs](https://docs.litellm.ai/docs/completion/token_usage) - token_counter, cost_per_token, completion_cost
- [Supabase Python RPC reference](https://supabase.com/docs/reference/python/rpc) - rpc() method syntax and parameters

### Secondary (MEDIUM confidence)
- [Google Gemini Embedding announcement](https://developers.googleblog.com/gemini-embedding-available-gemini-api/) - gemini-embedding-001 GA, deprecation timeline, MRL dimensions
- [PyPI litellm](https://pypi.org/project/litellm/) - Version 1.81.14, released 2026-02-22
- [PyPI supabase](https://pypi.org/project/supabase/) - Version 2.28.0, released 2026-02-10
- [Google AI changelog](https://ai.google.dev/gemini-api/docs/changelog) - text-embedding-004 deprecation date (2026-01-14)

### Tertiary (LOW confidence)
- [LiteLLM GitHub issue #17759](https://github.com/BerriAI/litellm/issues/17759) - gemini-embedding-001 proxy compatibility issues (may be resolved in latest version)
- WebSearch results on Postgres JSONB best practices - Hybrid schema pattern (dedicated columns + JSONB overflow)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries are well-documented, actively maintained, and verified via Context7 + official docs
- Architecture: HIGH - Patterns follow Supabase official guidance (RPC for vectors) and LiteLLM documented usage
- Pitfalls: HIGH - text-embedding-004 deprecation verified via multiple sources; PostgREST limitation documented officially
- Italian legal schema: MEDIUM - Metadata field structure based on user domain knowledge; correctness of Italian legal terminology deferred to user validation

**Research date:** 2026-02-22
**Valid until:** 2026-03-22 (30 days - stack is stable, libraries have recent releases)
