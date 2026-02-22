# Architecture

**Analysis Date:** 2026-02-15

## Pattern Overview

**Overall:** Hierarchical Tree Indexing with LLM-Driven Document Parsing

**Key Characteristics:**
- Multi-stage document parsing pipeline using Gemini for reasoning-based retrieval
- Hierarchical tree structure generation (ToC-like indexing) without vector databases
- Async-concurrent processing for scalable LLM API calls
- Two input modes: PDF files and Markdown documents
- Configurable node splitting based on page/token limits and hierarchical depth

## Layers

**PDF Parsing Layer:**
- Purpose: Extract page-level text and metadata from PDF documents
- Location: `pageindex/utils.py` (functions like `get_page_tokens`, `get_text_of_pages`)
- Contains: PDF extraction using PyPDF2 and PyMuPDF, token counting via Gemini API
- Depends on: External PDF parsing libraries (PyPDF2, pymupdf), Gemini API
- Used by: Main pipeline in `page_index_main`

**LLM Reasoning Layer:**
- Purpose: Use Gemini to understand document structure and validate extracted sections
- Location: `pageindex/utils.py` (Gemini_API, Gemini_API_async) and `pageindex/page_index.py`
- Contains: Prompts for table-of-contents detection, section mapping, title validation, description generation
- Depends on: Gemini API (async and sync clients), environment variables for API keys
- Used by: ToC detection, index extraction, summary generation, validation

**ToC Processing Layer:**
- Purpose: Detect, extract, and parse table-of-contents from document
- Location: `pageindex/page_index.py` (functions: `check_toc`, `find_toc_pages`, `toc_extractor`, `toc_transformer`, `toc_index_extractor`)
- Contains: Three processing modes based on ToC presence and page number availability
- Depends on: LLM Reasoning Layer for detection and parsing
- Used by: Meta processor for branching logic

**Metadata Processor (Meta Layer):**
- Purpose: Orchestrate different document parsing strategies and validate results
- Location: `pageindex/page_index.py` (async function `meta_processor`)
- Contains: Mode routing (`process_toc_with_page_numbers`, `process_toc_no_page_numbers`, `process_no_toc`), fallback logic, accuracy checking, correction attempts
- Depends on: ToC Processing Layer, Validation Layer
- Used by: Tree Parser

**Tree Building Layer:**
- Purpose: Convert flat list of sections with page indices into hierarchical tree structure
- Location: `pageindex/utils.py` (`post_processing`, `list_to_tree`) and `pageindex/page_index_md.py` (`build_tree_from_nodes`)
- Contains: Stack-based hierarchy construction, recursive node processing for large documents
- Depends on: Page index data with start/end boundaries
- Used by: Tree Parser

**Enrichment Layer:**
- Purpose: Add optional metadata to tree nodes (summaries, IDs, descriptions)
- Location: `pageindex/utils.py` and `pageindex/page_index_md.py` (async functions like `generate_summaries_for_structure`, `generate_node_summary`)
- Contains: Node ID assignment, summary generation via LLM, document description generation
- Depends on: LLM Reasoning Layer
- Used by: Pipeline finalization

**Markdown Parsing Layer:**
- Purpose: Parse markdown files and convert to tree structure (alternative to PDF)
- Location: `pageindex/page_index_md.py` (async function `md_to_tree`)
- Contains: Header extraction, node hierarchy building, optional tree thinning based on token thresholds
- Depends on: Markdown header parsing, tree building logic
- Used by: Run script as alternative entry point

## Data Flow

**PDF Document Processing:**

1. **Load & Tokenize** (`page_index_main`):
   - Input: PDF file path or BytesIO object
   - Output: `page_list` = list of (text, token_count) tuples via `get_page_tokens`
   - Location: `pageindex/page_index.py:1058-1072`

2. **Detect ToC** (`tree_parser` → `check_toc`):
   - Input: `page_list`, configuration
   - Output: `check_toc_result` with `{toc_content, toc_page_list, page_index_given_in_toc}`
   - Uses LLM to detect ToC presence and extract pages (first ~20 pages by default)
   - Location: `pageindex/page_index.py:688-724`

3. **Route Processing** (`tree_parser` → `meta_processor`):
   - Three paths based on ToC detection:
     - **Path A**: ToC with page numbers → `process_toc_with_page_numbers`
     - **Path B**: ToC without page numbers → `process_toc_no_page_numbers`
     - **Path C**: No ToC → `process_no_toc` (default, uses LLM to infer structure)
   - Location: `pageindex/page_index.py:1021-1040`

4. **Extract & Map Sections** (Path-specific processors):
   - Input: Page text with metadata
   - Output: Flat list of sections with `{title, physical_index, start_index, end_index}`
   - Uses LLM to:
     - Transform raw ToC to JSON structure
     - Find physical page indices for sections
     - Validate title appearances
     - Correct errors if accuracy > 60%
   - Location: `pageindex/page_index.py:600-990`

5. **Verify Accuracy** (`verify_toc`):
   - Concurrently checks if extracted sections actually appear at physical indices
   - Returns accuracy score and list of incorrect mappings
   - Location: `pageindex/page_index.py` (async concurrent verification)

6. **Error Correction** (`fix_incorrect_toc_with_retries`):
   - For each incorrect section, re-runs LLM extraction on page range between previous/next correct sections
   - Retries up to 3 times before accepting result
   - Location: `pageindex/page_index.py:752-850`

7. **Build Hierarchy** (`post_processing`):
   - Converts flat list to tree based on section ordering
   - Assigns start/end indices to each node
   - Location: `pageindex/utils.py:460-479`

8. **Handle Large Nodes** (`process_large_node_recursively`):
   - Recursively subdivides nodes exceeding token/page limits
   - Re-applies meta_processor to large node's page range
   - Location: `pageindex/page_index.py:992-1019`

9. **Enrich Structure** (Optional):
   - Add node IDs via `write_node_id`
   - Add text content via `add_node_text`
   - Generate summaries via `generate_summaries_for_structure`
   - Generate document description via `generate_doc_description`
   - Location: `pageindex/page_index.py:1074-1098` and `pageindex/utils.py`

10. **Output**:
    - Format: JSON with structure `{doc_name, [doc_description], structure: [tree]}`
    - Saved to `./results/{pdf_name}_structure.json`

**Markdown Document Processing:**

1. **Parse Headers** (`extract_nodes_from_markdown`):
   - Extract markdown headers (## through ######) respecting code blocks
   - Output: List of nodes with title and line number
   - Location: `pageindex/page_index_md.py:32-59`

2. **Extract Content** (`extract_node_text_content`):
   - For each header, extract text until next header of same/higher level
   - Compute token counts for each node
   - Location: `pageindex/page_index_md.py:62-87`

3. **Optional Thinning** (`tree_thinning_for_index`):
   - Merge nodes with text below minimum token threshold with parent
   - Recursively process to find all descendants
   - Location: `pageindex/page_index_md.py:135-187`

4. **Build Tree** (`build_tree_from_nodes`):
   - Stack-based hierarchy construction from flat node list
   - Assign node IDs
   - Location: `pageindex/page_index_md.py:190-221`

5. **Generate Summaries** (Optional, async):
   - For nodes exceeding token threshold, use LLM to generate summary
   - Store summary or full text based on children presence
   - Location: `pageindex/page_index_md.py:10-29`

6. **Output**:
   - Format: JSON with structure `{doc_name, structure: [tree], [doc_description]}`
   - Saved to `./results/{md_name}_structure.json`

**State Management:**
- **Page List**: Immutable throughout pipeline, passed to all processing functions
- **ToC Structure**: Built iteratively, modified in-place during processing
- **Configuration**: Loaded once from `config.yaml`, passed as `SimpleNamespace` object
- **Logging**: `JsonLogger` tracks decision points and accuracy metrics

## Key Abstractions

**PageIndexNode:**
- Purpose: Represents hierarchical document section
- Location: Implicit dictionary structure in all functions
- Pattern: Nested dictionaries with keys: `title`, `node_id`, `start_index`, `end_index`, `physical_index`, `summary`, `nodes[]`, `text`, `line_num`
- Example from README:
  ```json
  {
    "title": "Financial Stability",
    "node_id": "0006",
    "start_index": 21,
    "end_index": 22,
    "summary": "...",
    "nodes": [...]
  }
  ```

**ProcessingMode:**
- Purpose: Strategy pattern for different document structures
- Values: `'process_toc_with_page_numbers'`, `'process_toc_no_page_numbers'`, `'process_no_toc'`
- Implementation: `meta_processor` function branches on mode parameter

**ConfigLoader:**
- Purpose: Centralized configuration management with YAML defaults
- Location: `pageindex/utils.py:681-709`
- Pattern: Loads `config.yaml`, merges with user options, validates against known keys

## Entry Points

**Command-Line Entry:**
- Location: `run_pageindex.py`
- Triggers: `python run_pageindex.py --pdf_path <path>` or `--md_path <path>`
- Responsibilities:
  - Parse command-line arguments
  - Validate file paths
  - Create configuration via `config()` or `ConfigLoader`
  - Call `page_index_main()` for PDF or `asyncio.run(md_to_tree())` for Markdown
  - Save results to `./results/{name}_structure.json`

**Programmatic API Entry:**
- Location: `pageindex/page_index.py:1103-1111` (`page_index()` function)
- Triggers: `from pageindex import page_index; page_index(doc_path, model='gemini-3.1-pro-preview', ...)`
- Responsibilities:
  - Accept optional keyword arguments for all configuration options
  - Load config with user overrides
  - Call `page_index_main()`

**Library Import Entry:**
- Location: `pageindex/__init__.py`
- Exports: `page_index`, `page_index_main`, `md_to_tree`, `config()`

## Error Handling

**Strategy:** Multi-level fallback with LLM-assisted validation

**Patterns:**

**API Errors (Retry Loop):**
- Location: `Gemini_API()`, `Gemini_API_async()` in `pageindex/utils.py:29-108`
- Mechanism: Up to 10 retries with 1-second delays between attempts
- Fallback: Log error and return "Error" string after max retries

**ToC Extraction Errors (Mode Fallback):**
- Location: `meta_processor()` in `pageindex/page_index.py:951-989`
- Mechanism: If accuracy < 60%, fallback to next processing mode (with numbers → no numbers → no ToC)
- Validation: `verify_toc()` checks accuracy before mode switch

**Incorrect Section Mapping (Correction Attempts):**
- Location: `fix_incorrect_toc_with_retries()` in `pageindex/page_index.py`
- Mechanism: Re-extract incorrect section indices with bounded page range, retry up to 3 times

**Physical Index Truncation:**
- Location: `validate_and_truncate_physical_indices()` in `pageindex/page_index.py:1114-1142`
- Mechanism: Validate extracted indices don't exceed actual document length; set invalid indices to None

**JSON Parsing (Cleanup & Fallback):**
- Location: `extract_json()` in `pageindex/utils.py:125-163`
- Mechanism: Extract JSON from markdown code blocks, normalize whitespace, handle Python None → JSON null conversion, remove trailing commas

## Cross-Cutting Concerns

**Logging:**
- Framework: Custom `JsonLogger` class (defined in `utils.py`)
- Approach: Logs key decision points (ToC detection, accuracy checks, mode switches) as structured JSON
- Usage: Pass logger to async functions for concurrent operation tracking

**Validation:**
- Approach: LLM-assisted validation via `verify_toc()` function
- Checks: Does extracted title actually appear on its physical page?
- Concurrency: Async checks for all sections in parallel

**Token Management:**
- Framework: Gemini API built-in `count_tokens` for accurate token counting
- Usage: Count tokens for each page, used to decide node subdivision
- Location: `count_tokens()` in `pageindex/utils.py:22-27`

**Async Concurrency:**
- Framework: `asyncio` for concurrent LLM API calls
- Patterns: `asyncio.gather()` for parallel task execution, `ThreadPoolExecutor` for legacy code
- Usage: Concurrent validation, concurrent summary generation

---

*Architecture analysis: 2026-02-15*
