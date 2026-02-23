---
phase: 02-ingestion-pipeline
verified: 2026-02-22T12:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 2: Ingestion Pipeline Verification Report

**Phase Goal:** PDFs can be batch-processed through the full pipeline (tree indexing, metadata extraction, description generation, chunking, embedding) and stored in Supabase
**Verified:** 2026-02-22
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can run a batch ingestion command against a directory of Italian legal PDFs and each document is processed end-to-end into Supabase | VERIFIED | `ingest(directory)` in `pageindex/ingestion/pipeline.py` discovers PDFs, calls `process_single_document` per file, writes to Supabase via DB layer; all 6 stages confirmed wired |
| 2 | Each ingested document has automatically extracted Italian legal metadata (ECLI, court, date, legal area, doc_type) populated from the document text via LLM | VERIFIED | `stage_extract_metadata` in `stages.py` uses `litellm.completion` with `METADATA_JSON_SCHEMA` response_format and vocabulary-injected system prompt; all 9 fields required in JSON schema including ecli, authority, date, legal_area, doc_type |
| 3 | Each ingested document has a one-sentence LLM-generated description stored alongside its metadata | VERIFIED | `stage_generate_description` is a separate LLM call (`llm_provider.complete`) from metadata extraction; result stored in `pipeline.description`; persisted via `update_document` in `stage_store` as `doc_description` |
| 4 | Each ingested document has chunks with vector embeddings stored in pgvector, where chunk boundaries follow tree leaf nodes | VERIFIED | `stage_chunk` calls `chunk_leaf_nodes` which iterates `get_leaf_nodes(tree_json)`; `stage_embed` builds contextual embedding text and calls `llm_provider.embed`; `stage_store` calls `insert_chunks` with embeddings aligned 1:1 with chunks |
| 5 | Ingestion failures for individual documents do not halt the batch, and failed documents can be identified and retried | VERIFIED | `ThreadPoolExecutor` with `as_completed` catches per-document exceptions; `_process_with_rollback` deletes partial DB state on failure; failed documents written to `ingest_errors.jsonl` for identification; re-running `ingest()` picks up previously-failed (deleted) documents automatically |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pageindex/db/migrations/002_ingestion_status.sql` | DDL adding ingestion_status and needs_review columns | VERIFIED | Valid `ALTER TABLE documents ADD COLUMN IF NOT EXISTS` with correct defaults and B-tree index |
| `pageindex/ingestion/__init__.py` | Package re-export of ingest(), DocumentPipeline, ChunkData, process_single_document | VERIFIED | All 4 symbols re-exported; `from .pipeline import ingest` confirmed |
| `pageindex/ingestion/models.py` | DataClasses DocumentPipeline and ChunkData | VERIFIED | Both dataclasses substantively implemented; `DocumentPipeline(pdf_path='/test.pdf', doc_name='test.pdf')` instantiates correctly |
| `pageindex/ingestion/prompts.py` | Prompt builders with vocabulary injection, JSON schema, vocabulary loader | VERIFIED | `build_metadata_extraction_prompt`, `build_description_prompt`, `METADATA_JSON_SCHEMA`, `load_vocabulary` all present and functional |
| `pageindex/ingestion/chunker.py` | Recursive splitter, tree path builder, embedding text builder | VERIFIED | `chunk_leaf_nodes`, `recursive_split`, `build_tree_path`, `build_embedding_text` all present; split produces 5 chunks on long text; tree path correctly traverses nested structure |
| `pageindex/ingestion/stages.py` | All 6 pipeline stages + `process_single_document` orchestrator | VERIFIED | All 6 stage functions plus orchestrator implemented with tenacity retry; each stage mutates DocumentPipeline in-place |
| `pageindex/ingestion/pipeline.py` | Batch `ingest()`, `_process_with_rollback()`, `load_ingestion_config()` | VERIFIED | `ingest()` discovers PDFs, skips completed, processes with ThreadPoolExecutor, writes ingest_errors.jsonl, returns summary dict |
| `pageindex/db/documents.py` | `update_document()` and `delete_document()` | VERIFIED | Both functions present with correct Supabase client calls; `_METADATA_COLUMNS` includes `ingestion_status` and `needs_review` |
| `pageindex/config.yaml` | `ingestion` section with pipeline defaults | VERIFIED | Section present with all 5 keys: `metadata_pages: 3`, `chunk_max_tokens: 800`, `chunk_overlap: 0.1`, `max_workers: 1`, `max_embedding_batch: 250` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `pageindex/ingestion/prompts.py` | `pageindex/schema/legal_vocabulary.yaml` | YAML loading for vocabulary injection | WIRED | Path resolution `Path(__file__).resolve().parent.parent / "schema" / "legal_vocabulary.yaml"` verified; vocabulary loads with keys `doc_types, legal_areas, court_levels, party_roles, cross_reference_types` |
| `pageindex/ingestion/chunker.py` | `pageindex/llm/provider.py` | `count_tokens_fn` for token-aware splitting | WIRED | `chunk_leaf_nodes` accepts `count_tokens_fn` callable; raises `ValueError` if `None`; used on every leaf node and in `recursive_split` |
| `pageindex/ingestion/stages.py` | `pageindex/page_index.py` | `page_index_main()` call for tree indexing | WIRED | `from pageindex.page_index import page_index_main` (lazy import); called with `if_add_node_id=yes`, `if_add_node_text=yes`, `if_add_node_summary=yes` overrides |
| `pageindex/ingestion/stages.py` | `pageindex/llm/provider.py` | `provider.complete()` and `provider.embed()` for LLM calls | WIRED | `llm_provider.complete()` used in `_generate_description_llm`; `llm_provider.embed()` used in `_embed_batch`; both decorated with tenacity retry |
| `pageindex/ingestion/stages.py` | `pageindex/ingestion/chunker.py` | `chunk_leaf_nodes()` for tree-aware chunking | WIRED | `from pageindex.ingestion.chunker import build_embedding_text, chunk_leaf_nodes` at top of file; called in `stage_chunk` |
| `pageindex/ingestion/stages.py` | `pageindex/ingestion/prompts.py` | `build_metadata_extraction_prompt()`, `METADATA_JSON_SCHEMA` | WIRED | Both imported at file top; used in `stage_extract_metadata` |
| `pageindex/ingestion/stages.py` | `pageindex/db/documents.py` | `insert_document()`, `update_document()` | WIRED | Both imported and called in `process_single_document` and `stage_store` |
| `pageindex/ingestion/stages.py` | `pageindex/db/chunks.py` | `insert_chunks()` for batch chunk storage | WIRED | Imported and called in `stage_store` with chunk dicts including embedding vectors |
| `pageindex/ingestion/stages.py` | `pageindex/db/trees.py` | `insert_tree()` for tree storage | WIRED | Imported and called in `stage_store` with text-stripped tree |
| `pageindex/ingestion/pipeline.py` | `pageindex/ingestion/stages.py` | `process_single_document()` per PDF | WIRED | `from pageindex.ingestion.stages import process_single_document`; called inside `_process_with_rollback` |
| `pageindex/ingestion/pipeline.py` | `pageindex/db/documents.py` | `get_document_by_name()` for skip check, `delete_document()` for rollback | WIRED | Both imported and used: skip check in `ingest()`, rollback in `_process_with_rollback()` |
| `pageindex/ingestion/__init__.py` | `pageindex/ingestion/pipeline.py` | re-export of `ingest()` | WIRED | `from .pipeline import ingest` confirmed present |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| FOUND-04 | 02-01, 02-02, 02-03 | Batch ingestion pipeline: tree indexing → metadata extraction → embedding → Supabase storage | SATISFIED | `ingest(directory)` orchestrates all stages end-to-end; all 6 stages substantively implemented and wired |
| SEM-01 | 02-01, 02-02 | Chunk documents using tree leaf nodes as natural boundaries; embeddings stored in pgvector | SATISFIED | `chunk_leaf_nodes` iterates `get_leaf_nodes(tree_json)` respecting tree boundaries; `insert_chunks` stores with `embedding` field for pgvector |
| ENRICH-01 | 02-01, 02-02 | Automatically extract Italian legal metadata (ECLI, court, date, legal area, parties, doc_type) via LLM | SATISFIED | `stage_extract_metadata` uses structured JSON output with vocabulary-injected prompt; all 9 metadata fields in schema; `needs_review` flag set when critical fields null |
| ENRICH-02 | 02-01, 02-02 | Generate one-sentence LLM descriptions for each document during ingestion | SATISFIED | `stage_generate_description` makes a separate LLM call from metadata extraction; result stored as `doc_description` in Supabase |

All 4 requirement IDs fully satisfied with substantive implementation evidence.

### Anti-Patterns Found

None. Scanned all 8 modified files for TODO, FIXME, XXX, HACK, PLACEHOLDER, `return null`, `return {}`, `return []`, and empty handler patterns. Zero occurrences.

### Human Verification Required

#### 1. End-to-End Integration Test Against Live Supabase

**Test:** Call `ingest("/path/to/italian_legal_pdfs")` against a directory containing at least one real Italian legal PDF and a live Supabase instance with the schema applied (both migrations 001 and 002).
**Expected:** Document row appears in `documents` table with `ingestion_status = 'complete'`, populated metadata fields, `doc_description` filled, and corresponding rows in `chunks` with non-null `embedding` vectors and in `document_trees` with the tree structure.
**Why human:** Integration test requires live Supabase credentials and API keys for Gemini. Cannot be verified programmatically without external service access.

#### 2. Metadata Extraction Quality on Italian Legal Documents

**Test:** Run ingestion on a known Italian legal document (e.g., a Corte di Cassazione sentenza with an ECLI number) and inspect the `metadata` column.
**Expected:** `ecli`, `authority`, `date`, `doc_type`, `court_level`, and `legal_area` fields populated correctly; vocabulary terms match `legal_vocabulary.yaml` entries.
**Why human:** LLM extraction quality depends on prompt effectiveness which cannot be verified by static analysis — only by observing actual LLM responses on real documents.

#### 3. Failure Isolation and Retry Behaviour

**Test:** Introduce a document that will fail (e.g., a corrupted or empty PDF), run `ingest()` alongside valid documents, verify the batch continues, check `ingest_errors.jsonl` is created, then re-run `ingest()` and verify valid documents are skipped while the failed document is re-attempted.
**Expected:** Batch succeeds for valid documents; `ingest_errors.jsonl` contains the failed document path; re-run picks up the failed document (since its row was deleted during rollback).
**Why human:** Requires a live environment to verify cascade delete and idempotent resume behaviour end-to-end.

### Notes

**One design decision to be aware of:** Failed documents are rolled back by deleting their Supabase row entirely (not by setting `ingestion_status = 'failed'`). This means the DB cannot be used alone to identify failed documents — `ingest_errors.jsonl` is the primary record. This is intentional per the CONTEXT.md "dual tracking" decision and the Plans explicitly describe this pattern. Retry works automatically: since the row is deleted, a subsequent `ingest()` call will re-process the document (the skip check only excludes rows with `ingestion_status = 'complete'`).

---

_Verified: 2026-02-22_
_Verifier: Claude (gsd-verifier)_
