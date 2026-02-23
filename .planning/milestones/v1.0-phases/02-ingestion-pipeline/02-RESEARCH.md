# Phase 2: Ingestion Pipeline - Research

**Researched:** 2026-02-22
**Domain:** Batch PDF ingestion, LLM metadata extraction, tree-based chunking, contextual embedding, Supabase storage
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Interface**: Python function (not CLI). Call `ingest(directory_path)` from code or REPL, following the existing `run_pageindex.py` pattern
- **No CLI wrapper** in this phase -- CLI is Phase 5 territory
- **Concurrency**: Configurable `max_workers` parameter for parallel document processing (e.g., ThreadPoolExecutor). Default to sequential (1) with option to increase
- **Progress Reporting**: Structured logging via Python `logging` module -- per-document status lines. No progress bars or interactive UI
- **Resume & Idempotency**: Check Supabase for existing `doc_id` before processing. Skip documents with `complete` status
- **Metadata Extraction**: First N pages of PDF (configurable, default ~3 pages). Two separate LLM calls (metadata JSON + description). Vocabulary injection from `legal_vocabulary.yaml`. Store `null` for missing fields + set `needs_review` flag
- **Chunking Strategy**: Leaf node is primary semantic container. Never combine text from different leaf nodes. Token limit check (~800 tokens). Recursive splitting: paragraphs first, then sentences, then words. 10-15% overlap between sub-chunks. Sub-chunks stored with `leaf_node_id` FK
- **Contextual Embedding**: Prepend tree path + full metadata block to each chunk before embedding. Batch embed per document. Embedding text = `[metadata block] [tree path] [chunk content]`
- **Failure Handling**: Database `ingestion_status` column (pending/processing/complete/failed) + local log file. Rollback per document on failure (delete all data). LLM retry up to 3 times with exponential backoff. Batch summary at end
- **Two separate LLM calls**: First extracts structured metadata (JSON output), second generates one-sentence description. Separate prompts for easier debugging

### Claude's Discretion
- Exact recursive text splitter implementation details
- Token counting approach (tiktoken, model-specific, or character-based estimation)
- ThreadPoolExecutor vs asyncio for concurrency
- Exact retry backoff parameters (base delay, max delay, jitter)
- Local log file format (JSON lines, CSV, or plain text)
- Pipeline stage ordering optimizations
- How to extract text from first N pages of PDF
- Exact embedding text template formatting

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FOUND-04 | System provides a batch ingestion pipeline that processes PDFs through: tree indexing -> metadata extraction -> embedding generation -> Supabase storage | Full pipeline architecture researched: existing `page_index_main()` for tree indexing, LiteLLM `response_format` for structured metadata extraction, LiteLLM `embed()` for batch embedding, supabase-py for storage. ThreadPoolExecutor for batch concurrency. |
| SEM-01 | System chunks documents using tree leaf nodes as natural boundaries and generates embeddings stored in pgvector | Existing `get_leaf_nodes()` utility extracts leaf nodes from tree. LangChain `RecursiveCharacterTextSplitter` with tiktoken for token-aware sub-chunking. LiteLLM `embed()` supports batch input. Chunks table with `vector(768)` and HNSW index already exist. |
| ENRICH-01 | System automatically extracts Italian legal metadata from document text during ingestion via LLM | LiteLLM `completion()` with `response_format={"type": "json_schema", ...}` provides reliable structured JSON output. Gemini models support this via LiteLLM. `legal_vocabulary.yaml` already contains doc_types, legal_areas, court_levels for prompt injection. |
| ENRICH-02 | System generates one-sentence LLM descriptions for each document during ingestion | Second LLM call via `LLMProvider.complete()`. Existing `generate_doc_description()` in `utils.py` provides a pattern. Use tree structure summary for description generation context. |
</phase_requirements>

## Summary

Phase 2 builds a batch ingestion pipeline that takes a directory of Italian legal PDFs and processes each through: (1) tree indexing via existing PageIndex, (2) LLM metadata extraction, (3) LLM description generation, (4) tree-based chunking, (5) contextual embedding, and (6) Supabase storage. The existing codebase from Phase 1 provides the foundation: `page_index_main()` for tree building, `LLMProvider` for provider-agnostic LLM/embedding calls, supabase-py client singleton, and DB helper functions for documents/trees/chunks.

The key technical challenges are: (a) reliable structured JSON extraction from LLM for Italian legal metadata, (b) token-aware recursive text splitting that respects tree leaf node boundaries, (c) contextual embedding with metadata+path prepended to each chunk, and (d) robust failure handling with per-document rollback. All of these have well-established solutions in the current ecosystem.

The pipeline should be implemented as a Python module (`pageindex/ingestion/`) with a top-level `ingest()` function. Each document flows through sequential stages, but multiple documents can be processed concurrently via ThreadPoolExecutor. The existing DB schema needs a minor migration to add `ingestion_status` and `needs_review` columns to the documents table.

**Primary recommendation:** Build a staged pipeline using existing `page_index_main()` + `LLMProvider` + supabase-py, with `tenacity` for LLM retry logic, hand-rolled recursive text splitter (no LangChain dependency), and ThreadPoolExecutor for document-level parallelism.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| litellm | >=1.81.0 | LLM completion + embedding (already installed) | Provider-agnostic, supports `response_format` JSON schema for structured output, batch embedding via `embed()` |
| supabase | >=2.28.0 | Database client (already installed) | Already used in Phase 1, singleton pattern established |
| tenacity | >=8.2.0 | Retry with exponential backoff for LLM calls | De facto standard for Python retry logic, supports `wait_random_exponential`, `stop_after_attempt`, custom retry predicates |
| PyPDF2 | 3.0.1 | PDF text extraction (already installed) | Already used in `utils.py` for `extract_text_from_pdf()` and `get_text_of_pages()` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tiktoken | >=0.7.0 | Token counting for chunk size validation | When LiteLLM's `token_counter()` is insufficient or when needing offline token counting without API calls. **Recommendation: use LiteLLM's existing `token_counter()`** which is already wired up in `LLMProvider.count_tokens()` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled recursive splitter | langchain-text-splitters `RecursiveCharacterTextSplitter` | LangChain adds a large dependency tree for a single utility. The splitting logic is ~50 lines of custom code. Recommend hand-rolling to avoid dependency bloat |
| ThreadPoolExecutor | asyncio with aiofiles | asyncio would integrate with existing `acomplete()`/`aembed()` but adds complexity. ThreadPoolExecutor is simpler and the user listed it as the preferred option. Each document runs `page_index_main()` which internally uses `asyncio.run()`, so ThreadPoolExecutor avoids nested event loop issues |
| tenacity | Hand-rolled retry loop | tenacity provides jitter, exponential backoff, retry predicates out of the box. ~3 lines of decorator vs ~15 lines of manual retry code |

**Installation:**
```bash
pip install tenacity>=8.2.0
```
(All other dependencies are already in `requirements.txt`)

## Architecture Patterns

### Recommended Project Structure
```
pageindex/
├── ingestion/
│   ├── __init__.py          # re-exports ingest()
│   ├── pipeline.py          # main ingest() function + batch orchestration
│   ├── stages.py            # per-document pipeline stages (tree, metadata, description, chunk, embed, store)
│   ├── chunker.py           # recursive text splitter respecting leaf node boundaries
│   ├── prompts.py           # LLM prompt templates for metadata extraction + description
│   └── models.py            # dataclasses/TypedDicts for pipeline data (DocumentResult, ChunkData, etc.)
├── db/
│   ├── migrations/
│   │   ├── 001_initial_schema.sql       # existing
│   │   └── 002_ingestion_status.sql     # NEW: adds ingestion_status, needs_review columns
│   ├── documents.py         # extend with update_document(), delete_document_cascade()
│   └── ...                  # existing files unchanged
```

### Pattern 1: Staged Pipeline per Document
**What:** Each document flows through sequential stages: tree_index -> extract_metadata -> generate_description -> chunk -> embed -> store. Each stage receives the output of the previous stage.
**When to use:** For every document in the batch.
**Example:**
```python
# Source: derived from existing page_index_main() pattern and CONTEXT.md decisions
from dataclasses import dataclass, field

@dataclass
class DocumentPipeline:
    """Holds intermediate state as a document flows through pipeline stages."""
    pdf_path: str
    doc_name: str
    # Stage outputs (populated as pipeline progresses)
    tree_json: dict | None = None
    doc_id: str | None = None
    metadata: dict | None = None
    description: str | None = None
    chunks: list[dict] = field(default_factory=list)
    embeddings: list[list[float]] = field(default_factory=list)

def process_single_document(pdf_path: str, llm_provider, config) -> DocumentPipeline:
    """Run all pipeline stages for one document."""
    pipeline = DocumentPipeline(pdf_path=pdf_path, doc_name=os.path.basename(pdf_path))

    # Stage 1: Tree indexing (existing PageIndex)
    tree_result = page_index_main(pdf_path, config.pageindex_opts)
    pipeline.tree_json = tree_result["structure"]

    # Stage 2: Extract metadata via LLM (first N pages + vocabulary)
    first_pages_text = get_text_of_pages(pdf_path, 1, config.metadata_pages)
    pipeline.metadata = extract_metadata(llm_provider, first_pages_text, vocabulary)

    # Stage 3: Generate description via LLM
    pipeline.description = generate_description(llm_provider, pipeline.tree_json)

    # Stage 4: Chunk at leaf node boundaries
    pipeline.chunks = chunk_tree_leaves(pipeline.tree_json, pdf_pages, config.chunk_token_limit)

    # Stage 5: Embed with contextual prefix
    pipeline.embeddings = embed_chunks(llm_provider, pipeline.chunks, pipeline.metadata)

    # Stage 6: Store in Supabase (atomic per document)
    store_document(pipeline)

    return pipeline
```

### Pattern 2: Batch Orchestration with ThreadPoolExecutor
**What:** Top-level `ingest()` discovers PDFs in a directory, skips already-ingested ones, and dispatches remaining to a thread pool.
**When to use:** The entry point for batch ingestion.
**Example:**
```python
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logger = logging.getLogger("pageindex.ingestion")

def ingest(directory: str, max_workers: int = 1, **kwargs) -> dict:
    """Batch-ingest PDFs from a directory.

    Returns summary dict: {succeeded: int, failed: int, skipped: int, errors: [...]}
    """
    pdf_paths = sorted(Path(directory).glob("*.pdf"))
    logger.info(f"Found {len(pdf_paths)} PDFs in {directory}")

    # Check which are already ingested
    to_process = []
    skipped = 0
    for path in pdf_paths:
        existing = get_document_by_name(path.name)
        if existing and existing.get("ingestion_status") == "complete":
            skipped += 1
            continue
        to_process.append(str(path))

    logger.info(f"Processing {len(to_process)}, skipping {skipped} already-ingested")

    results = {"succeeded": 0, "failed": 0, "skipped": skipped, "errors": []}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_single_document, path, provider, config): path
            for path in to_process
        }
        for i, future in enumerate(as_completed(futures), 1):
            path = futures[future]
            try:
                future.result()
                results["succeeded"] += 1
                logger.info(f"[{i}/{len(to_process)}] SUCCESS: {Path(path).name}")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"path": path, "error": str(e)})
                logger.error(f"[{i}/{len(to_process)}] FAILED: {Path(path).name} - {e}")

    logger.info(f"Batch complete: {results['succeeded']} succeeded, "
                f"{results['failed']} failed, {results['skipped']} skipped")
    return results
```

### Pattern 3: Per-Document Rollback on Failure
**What:** If any pipeline stage fails, delete all data for that document from Supabase so no partial state remains.
**When to use:** Wrapping `process_single_document()`.
**Example:**
```python
def process_with_rollback(pdf_path: str, llm_provider, config):
    """Process a document with rollback on failure."""
    doc_id = None
    try:
        # Insert document record first (status=processing)
        doc_row = insert_document(os.path.basename(pdf_path), {"ingestion_status": "processing"})
        doc_id = doc_row["doc_id"]

        # Run pipeline stages...
        pipeline = run_pipeline_stages(pdf_path, doc_id, llm_provider, config)

        # Mark complete
        update_document(doc_id, {"ingestion_status": "complete"})
        return pipeline

    except Exception as e:
        # Rollback: delete document (CASCADE will remove trees + chunks)
        if doc_id:
            delete_document(doc_id)
        raise  # Re-raise for batch handler to log
```

### Pattern 4: LLM Structured Metadata Extraction with JSON Schema
**What:** Use LiteLLM `response_format` with JSON schema to get reliable structured metadata from document text.
**When to use:** Stage 2 of the pipeline.
**Example:**
```python
# Source: LiteLLM docs - https://docs.litellm.ai/docs/completion/json_mode
import json
from tenacity import retry, wait_random_exponential, stop_after_attempt

METADATA_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "legal_metadata",
        "schema": {
            "type": "object",
            "properties": {
                "doc_type": {"type": ["string", "null"]},
                "date": {"type": ["string", "null"]},
                "authority": {"type": ["string", "null"]},
                "ecli": {"type": ["string", "null"]},
                "gu_number": {"type": ["string", "null"]},
                "legal_area": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "parties": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "role": {"type": "string"}
                        }
                    }
                },
                "court_level": {"type": ["string", "null"]},
                "cross_references": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "ref": {"type": "string"},
                            "type": {"type": "string"}
                        }
                    }
                }
            },
            "required": ["doc_type", "date", "authority", "ecli",
                         "legal_area", "court_level"],
            "additionalProperties": False
        },
        "strict": True
    }
}

@retry(wait=wait_random_exponential(min=1, max=30), stop=stop_after_attempt(3))
def extract_metadata(llm_provider, text: str, vocabulary: dict) -> dict:
    """Extract structured metadata from first N pages of a legal document."""
    response = litellm.completion(
        model=llm_provider.completion_model,
        messages=[
            {"role": "system", "content": build_extraction_prompt(vocabulary)},
            {"role": "user", "content": text}
        ],
        response_format=METADATA_SCHEMA,
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)
```

### Pattern 5: Tree-Aware Chunking with Contextual Embedding
**What:** Extract leaf nodes from tree, split large leaves recursively, prepend tree path + metadata to each chunk before embedding.
**When to use:** Stages 4-5 of the pipeline.
**Example:**
```python
def chunk_tree_leaves(tree_json, pdf_pages, max_tokens=800, overlap_ratio=0.1):
    """Chunk document at tree leaf node boundaries."""
    leaf_nodes = get_leaf_nodes(tree_json)  # existing utility
    chunks = []

    for leaf in leaf_nodes:
        text = get_text_of_pdf_pages(pdf_pages, leaf["start_index"], leaf["end_index"])
        tree_path = build_tree_path(tree_json, leaf["node_id"])  # e.g. "Article 4 > Section 2 > Paragraph 3"
        token_count = llm_provider.count_tokens(text)

        if token_count <= max_tokens:
            chunks.append({
                "content": text,
                "node_id": leaf["node_id"],
                "tree_path": tree_path,
                "metadata": {"title": leaf.get("title"), "start_page": leaf["start_index"], "end_page": leaf["end_index"]}
            })
        else:
            # Recursive split: paragraphs -> sentences -> words
            sub_chunks = recursive_split(text, max_tokens, overlap_ratio)
            for i, sub_text in enumerate(sub_chunks):
                chunks.append({
                    "content": sub_text,
                    "node_id": leaf["node_id"],
                    "tree_path": tree_path,
                    "metadata": {"title": leaf.get("title"), "sub_chunk_index": i,
                                 "start_page": leaf["start_index"], "end_page": leaf["end_index"]}
                })
    return chunks


def build_embedding_text(chunk: dict, doc_metadata: dict) -> str:
    """Build the full text to embed: [metadata block] [tree path] [chunk content]."""
    meta_block = (
        f"Title: {doc_metadata.get('doc_name', '')}\n"
        f"Type: {doc_metadata.get('doc_type', '')}\n"
        f"Date: {doc_metadata.get('date', '')}\n"
        f"Court: {doc_metadata.get('authority', '')}\n"
        f"Legal Area: {', '.join(doc_metadata.get('legal_area', []))}\n"
        f"ECLI: {doc_metadata.get('ecli', '')}\n"
        f"Description: {doc_metadata.get('doc_description', '')}\n"
    )
    return f"{meta_block}\nSection: {chunk['tree_path']}\n\n{chunk['content']}"
```

### Anti-Patterns to Avoid
- **Combining text across leaf nodes into one chunk:** Violates the user's explicit decision that leaf nodes are primary semantic containers. Never merge text from different leaf nodes.
- **Using asyncio.run() inside ThreadPoolExecutor workers:** `page_index_main()` already calls `asyncio.run()` internally. Nesting event loops causes `RuntimeError`. ThreadPoolExecutor workers are fine because each thread gets its own event loop context.
- **Partial document state in database:** A document must be either fully ingested or not present at all. Never leave chunks without embeddings or metadata without chunks. Use CASCADE delete on failure.
- **Single massive embedding API call for all documents:** Embed chunks per-document, not globally. This respects rate limits and makes per-document rollback clean.
- **Hardcoding the embedding dimension:** The schema uses `vector(768)` but this must match `LLMProvider.embedding_dimensions`. Read from config, not from a constant.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM retry with backoff | Custom retry loops with sleep() | `tenacity` with `@retry(wait=wait_random_exponential(...), stop=stop_after_attempt(3))` | Jitter prevents thundering herd, decorator keeps code clean, supports custom retry predicates for rate limit errors |
| Structured JSON from LLM | Manual JSON parsing with `extract_json()` regex | LiteLLM `response_format={"type": "json_schema", ...}` | Provider-level JSON mode guarantees valid JSON. The existing `extract_json()` in utils.py is fragile for complex nested structures |
| Token counting | Character-based estimation (chars / 4) | `LLMProvider.count_tokens()` (delegates to LiteLLM `token_counter()`) | Already implemented in Phase 1, model-specific accuracy, handles non-Latin scripts (Italian) correctly |
| Provider-agnostic embedding | Direct Gemini SDK embedding calls | `LLMProvider.embed()` (wraps `litellm.embedding()`) | Already implemented in Phase 1, handles all providers, supports `dimensions` parameter |

**Key insight:** The Phase 1 codebase already provides the LLM and DB abstractions. Phase 2 should compose these existing pieces rather than bypassing them. The only new infrastructure piece is `tenacity` for retry logic.

## Common Pitfalls

### Pitfall 1: Nested asyncio.run() in ThreadPoolExecutor
**What goes wrong:** `page_index_main()` internally calls `asyncio.run()`. If the batch orchestrator also uses asyncio, you get `RuntimeError: This event loop is already running`.
**Why it happens:** Python's asyncio prohibits nested `asyncio.run()` calls.
**How to avoid:** Use `ThreadPoolExecutor` for document-level parallelism (user's preference). Each thread gets its own event loop context, so `page_index_main()` calling `asyncio.run()` works fine.
**Warning signs:** `RuntimeError: This event loop is already running` or `RuntimeError: cannot be called from a running event loop`.

### Pitfall 2: Gemini Embedding Rate Limits
**What goes wrong:** Gemini embedding-001 quota is measured in **tokens per minute per project**, not requests per minute. With max_workers > 1, multiple documents embedding concurrently can exhaust the quota.
**Why it happens:** Each document may have 50-200 chunks, each chunk ~500 tokens of embedding text. 100 chunks * 500 tokens = 50K tokens per document. With 4 workers, that's 200K tokens in parallel.
**How to avoid:** (a) Use tenacity retry on embedding calls with exponential backoff. (b) Limit batch size per embedding call (250 inputs max per Gemini API). (c) Consider a global rate limiter if max_workers > 2.
**Warning signs:** HTTP 429 errors from the embedding API.

### Pitfall 3: Embedding Text Exceeds Model Token Limit
**What goes wrong:** After prepending metadata block + tree path to chunk content, the total text exceeds the embedding model's 2048-token input limit per text. The embedding is silently truncated.
**Why it happens:** Metadata block (~100 tokens) + tree path (~20 tokens) + chunk (~800 tokens) should be under limit, but un-split leaf nodes or very deep trees can exceed it.
**How to avoid:** After building the full embedding text, validate its token count. If it exceeds the embedding model's limit (2048 tokens for Gemini), truncate the chunk content (not the metadata prefix). Set the chunk token limit to `embedding_max_tokens - estimated_prefix_tokens` (e.g., 2048 - 200 = ~1800 tokens max chunk).
**Warning signs:** Embeddings with unexpectedly low similarity scores for clearly relevant queries.

### Pitfall 4: Supabase Client Not Thread-Safe
**What goes wrong:** Multiple threads sharing a single Supabase client can cause connection pool issues or request interleaving.
**Why it happens:** The `get_client()` singleton returns one client for all threads.
**How to avoid:** The supabase-py client uses `httpx` under the hood, which handles connection pooling. Verify in testing with max_workers > 1. If issues arise, create one client per thread via `threading.local()`. **Confidence: MEDIUM** -- supabase-py docs don't explicitly document thread safety, but httpx is thread-safe.
**Warning signs:** Intermittent connection errors, request timeouts, or garbled responses under concurrent load.

### Pitfall 5: page_index_main() Produces Different Output Depending on Config
**What goes wrong:** The tree structure from `page_index_main()` may or may not have `text`, `summary`, `node_id`, `doc_description` fields depending on config options.
**Why it happens:** Config flags like `if_add_node_text`, `if_add_node_summary`, `if_add_node_id` control what gets populated.
**How to avoid:** The ingestion pipeline MUST set specific config options: `if_add_node_id='yes'` (needed for chunk traceability), `if_add_node_summary='yes'` (useful for description generation), `if_add_node_text='yes'` (needed for chunking -- we need leaf node text). This overrides whatever the user's default config.yaml says.
**Warning signs:** Empty or missing `text` fields on nodes, missing `node_id` fields.

### Pitfall 6: Foreign Key Violation on Rollback
**What goes wrong:** Trying to delete chunks before deleting the document, or vice versa, causes FK constraint violations.
**Why it happens:** The schema has `ON DELETE CASCADE` from documents to chunks and document_trees, but only if you delete the document row.
**How to avoid:** Always delete the document row (which cascades to chunks and trees). Never try to delete chunks independently during rollback -- just delete the document.
**Warning signs:** `ForeignKeyViolation` errors during cleanup.

## Code Examples

Verified patterns from official sources:

### LiteLLM Structured JSON Output (Gemini)
```python
# Source: https://docs.litellm.ai/docs/completion/json_mode
# Verified: works with gemini/ prefix models
import litellm

response = litellm.completion(
    model="gemini/gemini-2.0-flash",
    messages=[
        {"role": "system", "content": "Extract metadata from the Italian legal document."},
        {"role": "user", "content": document_text}
    ],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "legal_metadata",
            "schema": {
                "type": "object",
                "properties": {
                    "doc_type": {"type": ["string", "null"]},
                    "date": {"type": ["string", "null"]},
                    "ecli": {"type": ["string", "null"]},
                    "court_level": {"type": ["string", "null"]},
                    "legal_area": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["doc_type", "date", "ecli", "court_level", "legal_area"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    temperature=0,
)
metadata = json.loads(response.choices[0].message.content)
```

### LiteLLM Batch Embedding
```python
# Source: https://docs.litellm.ai/docs/embedding/supported_embedding
# The embed() method already supports list input
from pageindex.llm.provider import LLMProvider

provider = LLMProvider(config)
texts = ["chunk text 1", "chunk text 2", "chunk text 3"]  # up to 250 per call
embeddings = provider.embed(texts)  # returns list[list[float]]
# Note: Gemini embedding-001 supports max 2048 tokens per input, 250 inputs per call
```

### Tenacity Retry for LLM Calls
```python
# Source: https://tenacity.readthedocs.io/
from tenacity import retry, wait_random_exponential, stop_after_attempt, retry_if_exception_type

@retry(
    wait=wait_random_exponential(min=1, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((Exception,)),  # refine to specific LLM errors
)
def call_llm_with_retry(provider, messages, response_format=None):
    """LLM call with automatic retry on failure."""
    return litellm.completion(
        model=provider.completion_model,
        messages=messages,
        response_format=response_format,
        temperature=0,
    )
```

### Supabase Cascade Delete for Rollback
```python
# Source: https://supabase.com/docs/reference/python/llms/python
# CASCADE in schema means deleting document removes all related rows
from pageindex.db.client import get_client

def delete_document(doc_id: str) -> None:
    """Delete a document and all related data (trees, chunks) via CASCADE."""
    client = get_client()
    client.table("documents").delete().eq("doc_id", doc_id).execute()
```

### Recursive Text Splitter (Hand-Rolled)
```python
# Inspired by LangChain RecursiveCharacterTextSplitter pattern
# Source: https://python.langchain.com/docs/how_to/recursive_text_splitter/
# Custom implementation to avoid LangChain dependency

SEPARATORS = ["\n\n", "\n", ". ", " "]  # paragraphs -> lines -> sentences -> words

def recursive_split(text: str, max_tokens: int, overlap_ratio: float = 0.1,
                    count_tokens_fn=None) -> list[str]:
    """Recursively split text into chunks under max_tokens, with overlap."""
    if count_tokens_fn is None:
        raise ValueError("count_tokens_fn is required")

    if count_tokens_fn(text) <= max_tokens:
        return [text]

    # Try each separator level
    for separator in SEPARATORS:
        segments = text.split(separator)
        if len(segments) <= 1:
            continue

        chunks = []
        current = ""
        for segment in segments:
            candidate = current + separator + segment if current else segment
            if count_tokens_fn(candidate) <= max_tokens:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = segment

        if current:
            chunks.append(current)

        if len(chunks) > 1:
            # Add overlap between consecutive chunks
            return _add_overlap(chunks, overlap_ratio, count_tokens_fn)

    # Fallback: split by characters (should rarely happen with legal text)
    mid = len(text) // 2
    return recursive_split(text[:mid], max_tokens, overlap_ratio, count_tokens_fn) + \
           recursive_split(text[mid:], max_tokens, overlap_ratio, count_tokens_fn)


def _add_overlap(chunks: list[str], overlap_ratio: float, count_tokens_fn) -> list[str]:
    """Add overlap between consecutive chunks."""
    if len(chunks) <= 1 or overlap_ratio <= 0:
        return chunks

    result = [chunks[0]]
    for i in range(1, len(chunks)):
        prev_tokens = count_tokens_fn(chunks[i - 1])
        overlap_tokens = int(prev_tokens * overlap_ratio)
        # Take trailing words from previous chunk as prefix
        prev_words = chunks[i - 1].split()
        overlap_words = []
        token_count = 0
        for word in reversed(prev_words):
            token_count += count_tokens_fn(word)
            if token_count > overlap_tokens:
                break
            overlap_words.insert(0, word)
        prefix = " ".join(overlap_words)
        result.append(prefix + " " + chunks[i] if prefix else chunks[i])

    return result
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual JSON parsing from LLM (regex, `extract_json()`) | `response_format` with JSON schema (structured output) | 2024 -- OpenAI, then adopted by Gemini, Anthropic, all via LiteLLM | Eliminates JSON parsing failures. 100% valid JSON when provider supports it |
| Fixed-size character chunking | Token-aware recursive splitting with semantic separators | 2023-2024 -- LangChain popularized, now standard | Respects natural language boundaries, prevents mid-sentence/mid-clause cuts |
| Embedding raw chunk text only | Contextual embedding (metadata + structure prefix) | 2024 -- Anthropic popularized "contextual retrieval" | Significantly improves retrieval accuracy by giving embeddings document-level context |
| Per-call retry with `time.sleep()` | Decorator-based retry with jitter (`tenacity`) | Stable since 2020, standard in Python ecosystem | Cleaner code, prevents thundering herd, configurable strategies |

**Deprecated/outdated:**
- `extract_json()` in `utils.py`: Fragile regex-based JSON extraction. Use `response_format` JSON schema instead for new LLM calls. Keep `extract_json()` for backward compatibility with existing tree indexing code.
- Direct Gemini SDK calls for new features: Use `LLMProvider` / LiteLLM instead. Direct SDK calls are kept only in legacy `utils.py` functions.

## Open Questions

1. **Supabase-py thread safety**
   - What we know: httpx (underlying HTTP library) is thread-safe. The supabase-py client is a thin wrapper over httpx.
   - What's unclear: Whether the supabase-py `Client` object itself maintains any non-thread-safe state (e.g., session tokens, connection pools with thread affinity).
   - Recommendation: Start with shared singleton. Add integration test with max_workers=4. If issues arise, switch to `threading.local()` per-thread clients. **LOW risk** since httpx is robust.

2. **Gemini embedding-001 vs text-embedding-004**
   - What we know: Config currently specifies `gemini/gemini-embedding-001`. Google also offers `gemini/text-embedding-004`.
   - What's unclear: Whether `gemini-embedding-001` is the latest/recommended model or if `text-embedding-004` is preferred.
   - Recommendation: Use whatever is in config.yaml. The pipeline should be model-agnostic via `LLMProvider.embed()`.

3. **`ingestion_status` column vs separate table**
   - What we know: User decided on `ingestion_status` column on documents table. Research found a pattern using a separate `document_ingestion_status` table with stage-level tracking.
   - What's unclear: Whether a column is sufficient or if stage-level tracking adds value for debugging failures.
   - Recommendation: Follow user's decision -- add `ingestion_status` TEXT column + `needs_review` BOOLEAN column to documents table. This is simpler and sufficient for the skip-already-ingested pattern. Stage-level debugging can use the local log file.

4. **Tree text availability during chunking**
   - What we know: `page_index_main()` only populates `text` on nodes if `if_add_node_text='yes'`. Without it, nodes only have `start_index`/`end_index` page references.
   - What's unclear: Whether to re-extract text from PDF pages at chunking time or require `if_add_node_text='yes'` in the pipeline config.
   - Recommendation: Set `if_add_node_text='yes'` in the ingestion pipeline config so leaf node text is already available. This avoids re-reading the PDF. The text is stripped from the stored tree_json (to save DB space) but used during chunking before storage.

## Sources

### Primary (HIGH confidence)
- `/websites/litellm_ai` (Context7) -- JSON schema response_format, embedding API, Gemini model support. Verified: structured output with `response_format` works with `gemini/` prefix models.
- `/websites/supabase_reference_python` (Context7) -- Bulk insert, upsert, delete operations. Verified: cascade delete via FK, batch insert patterns.
- `/websites/langchain` (Context7) -- RecursiveCharacterTextSplitter pattern with tiktoken. Used as inspiration for hand-rolled splitter.
- Existing codebase analysis: `pageindex/llm/provider.py`, `pageindex/db/`, `pageindex/utils.py` -- Phase 1 implementations verified by reading code.

### Secondary (MEDIUM confidence)
- [Google Gemini Embedding Rate Limits](https://ai.google.dev/gemini-api/docs/rate-limits) -- Token-per-minute quota model for gemini-embedding-001. Max 2048 tokens per input, 250 inputs per request.
- [Tenacity Documentation](https://tenacity.readthedocs.io/) -- `wait_random_exponential`, `stop_after_attempt` patterns.
- [LangChain Text Splitter How-To](https://python.langchain.com/docs/how_to/recursive_text_splitter/) -- Recursive splitting pattern with token counting.

### Tertiary (LOW confidence)
- Supabase-py thread safety: Not explicitly documented. Inferred from httpx thread safety. Needs validation via integration testing.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All libraries already installed or well-established (tenacity only new addition)
- Architecture: HIGH -- Pipeline pattern derived from existing `page_index_main()` + user decisions in CONTEXT.md. All integration points verified in codebase.
- Pitfalls: HIGH for items 1,3,5,6 (verified in code/docs), MEDIUM for items 2,4 (rate limits and thread safety need empirical validation)

**Research date:** 2026-02-22
**Valid until:** 2026-03-22 (stable ecosystem, no fast-moving dependencies)
