# Phase 2: Ingestion Pipeline - Context

**Gathered:** 2026-02-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Batch processing of Italian legal PDFs through the full pipeline: tree indexing (existing PageIndex), LLM metadata extraction, LLM description generation, recursive chunking at tree leaf boundaries, contextual embedding, and Supabase storage. User runs ingestion as a Python function against a directory of PDFs with configurable concurrency. Individual document failures don't halt the batch.

</domain>

<decisions>
## Implementation Decisions

### Batch Invocation
- **Interface**: Python function (not CLI). Call `ingest(directory_path)` from code or REPL, following the existing `run_pageindex.py` pattern
- **No CLI wrapper** in this phase — CLI is Phase 5 (Public API) territory
- **Concurrency**: Configurable `max_workers` parameter for parallel document processing (e.g., ThreadPoolExecutor). Default to sequential (1) with option to increase

### Progress Reporting
- **Structured logging** via Python `logging` module — per-document status lines (INFO: Processing doc 47/1000 — sentenza_12345.pdf)
- Machine-parseable, redirectable to files
- No progress bars or interactive UI — this is a library, not a CLI tool

### Resume & Idempotency
- **Skip already-ingested**: Check Supabase for existing `doc_id` before processing each document
- If document already exists in database with `complete` status, skip it
- Re-running a batch safely picks up where it left off without reprocessing

### Metadata Extraction
- **Input scope**: First N pages of the PDF (configurable, default ~3 pages). Italian legal documents have identifying info in headers/preambles
- **Two separate LLM calls**: First call extracts structured metadata (JSON output). Second call generates a one-sentence description. Separate prompts, easier to debug
- **Vocabulary injection**: Include the full `legal_vocabulary.yaml` in the extraction prompt so the LLM uses consistent terminology (doc_types, legal_areas, court_levels)
- **Missing metadata handling**: Store `null` for fields that can't be extracted + set a `needs_review` boolean flag on the document. Batch continues without blocking

### Chunking Strategy
- **Leaf node is the primary semantic container**: Never combine text from different leaf nodes into a single chunk
- **Token limit check**: If leaf node text is under embedding model limit (~800 tokens), embed as a single chunk
- **Recursive splitting for large nodes**: If exceeds limit, split recursively: paragraphs (`\n\n`) first, then sentences (`. `), then words. Never cut a legal clause in half
- **Overlap**: 10-15% overlap between sub-chunks of the same leaf node. Chunk A = tokens 0-1000, Chunk B = tokens 900-1900
- **Traceability**: Sub-chunks stored as individual rows in chunks table with `leaf_node_id` foreign key back to the original tree node

### Contextual Embedding
- **Tree hierarchy prefix**: Prepend the tree path (e.g., "Article 4 > Section 2 > Paragraph 3") to each chunk's text before embedding
- **Full metadata block prefix**: Additionally prepend document title + doc_type + date + court + legal_area + ECLI + one-sentence description to each chunk before embedding
- **Batch per document**: Embed all chunks of one document in a single API call (or batched calls), then move to next document
- Embedding text = `[metadata block] [tree path] [chunk content]` — gives embeddings maximum structural and domain context

### Failure Handling
- **Dual tracking**: Database `ingestion_status` column (pending, processing, complete, failed) + local batch log file with paths and error messages
- **Rollback per document**: If any pipeline stage fails, delete all data for that document from Supabase. A document is either fully ingested or not present — no partial states
- **LLM retry**: Automatic retry up to 3 times with exponential backoff for LLM call failures (rate limits, timeouts). After 3 failures, mark document as failed and move on
- **Batch summary**: Log a structured final summary — X succeeded, Y failed, Z skipped (already ingested). List failed document paths and error types

### Claude's Discretion
- Exact recursive text splitter implementation details
- Token counting approach (tiktoken, model-specific, or character-based estimation)
- ThreadPoolExecutor vs asyncio for concurrency
- Exact retry backoff parameters (base delay, max delay, jitter)
- Local log file format (JSON lines, CSV, or plain text)
- Pipeline stage ordering optimizations
- How to extract text from first N pages of PDF
- Exact embedding text template formatting

</decisions>

<specifics>
## Specific Ideas

- Chunking should follow a "respect the leaf node" philosophy — the tree structure from PageIndex is the primary semantic boundary, sub-chunking only happens when size forces it
- The contextual embedding approach prepends document metadata to EVERY chunk before embedding — this is deliberate to give the embedding model awareness of which document and legal domain each chunk belongs to
- Metadata extraction and description generation are deliberately separated into two LLM calls for independent debugging and prompt iteration
- The "skip already-ingested" pattern makes ingestion naturally idempotent — safe to re-run after crashes or additions to the PDF directory

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-ingestion-pipeline*
*Context gathered: 2026-02-22*
