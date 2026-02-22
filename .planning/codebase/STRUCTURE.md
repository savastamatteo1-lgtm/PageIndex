# Codebase Structure

**Analysis Date:** 2026-02-15

## Directory Layout

```
PageIndex/
├── pageindex/                 # Core library module
│   ├── __init__.py           # Public API exports
│   ├── page_index.py         # PDF parsing and tree building (1143 lines)
│   ├── page_index_md.py      # Markdown parsing and tree building (338 lines)
│   ├── utils.py              # Utilities: API calls, helpers, tree ops (711 lines)
│   └── config.yaml           # Default configuration
├── run_pageindex.py          # Command-line entry point
├── requirements.txt          # Python dependencies
├── cookbook/                 # Example notebooks
│   ├── pageindex_RAG_simple.ipynb
│   ├── vision_RAG_pageindex.ipynb
│   ├── agentic_retrieval.ipynb
│   └── pageIndex_chat_quickstart.ipynb
├── tests/
│   ├── pdfs/                 # Sample PDF files for testing
│   └── results/              # Output tree structures (generated)
├── tutorials/                # Usage guides
│   ├── doc-search/
│   └── tree-search/
├── .planning/codebase/       # GSD planning documents
├── README.md
├── LICENSE
└── CHANGELOG.md
```

## Directory Purposes

**pageindex/**
- Purpose: Main library package for PageIndex tree generation
- Contains: PDF/Markdown parsing, LLM orchestration, tree building
- Key files: `page_index.py`, `utils.py`, `page_index_md.py`

**tests/pdfs/**
- Purpose: Sample PDF documents for testing and demonstrations
- Contains: Example financial reports, documents
- Generated: No, committed examples

**tests/results/**
- Purpose: Output location for generated tree structures from test PDFs
- Contains: JSON files with tree output (e.g., `filename_structure.json`)
- Generated: Yes, created by running `run_pageindex.py` on test PDFs

**cookbook/**
- Purpose: Jupyter notebooks demonstrating library usage
- Contains: Simple RAG, vision-based RAG, agentic retrieval examples
- Generated: No, committed examples

**tutorials/**
- Purpose: Documentation and guides for different retrieval patterns
- Contains: Document search and tree search tutorials
- Generated: No, committed examples

**.planning/codebase/**
- Purpose: GSD orchestrator planning documents (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Generated: Yes, created by mapping commands

## Key File Locations

**Entry Points:**
- `run_pageindex.py`: Command-line interface for processing PDF or Markdown files
- `pageindex/__init__.py`: Programmatic library imports (exports `page_index`, `md_to_tree`)

**Configuration:**
- `pageindex/config.yaml`: Default configuration (model, page limits, token limits, output options)
- `requirements.txt`: Python dependencies (google-genai, pymupdf, PyPDF2, python-dotenv, pyyaml)

**Core Logic:**
- `pageindex/page_index.py`: PDF document parsing, ToC detection, section extraction, tree building, node recursion
- `pageindex/page_index_md.py`: Markdown parsing, header extraction, tree thinning, summary generation
- `pageindex/utils.py`: LLM API wrappers, token counting, PDF utilities, tree transformation, configuration loader

**Testing:**
- `tests/pdfs/`: Test PDF files (actual content files for validation)
- `tests/results/`: Sample output JSON structures

## Naming Conventions

**Files:**
- `page_index.py`: Main PDF processing module
- `page_index_md.py`: Markdown-specific processing module (suffix `_md`)
- `utils.py`: Utility functions (no prefix)
- `config.yaml`: Configuration in YAML format
- `run_pageindex.py`: Executable script (verb prefix `run_`)

**Directories:**
- `pageindex/`: Lowercase package name matching module name
- `cookbook/`, `tests/`, `tutorials/`: Lowercase, semantic purpose names
- `results/`: Output directory for generated files

**Functions:**
- `page_index_main()`: Primary orchestration function (underscore-separated, descriptive)
- `get_page_tokens()`: Getter pattern for retrieving data (`get_*`)
- `check_toc()`: Checker functions for validation (`check_*`)
- `extract_json()`: Extraction functions (`extract_*`)
- `generate_summaries_for_structure()`: Generator functions (`generate_*`)
- `async def tree_parser()`: Async functions prefixed with `async def`
- `class ConfigLoader`: Classes use PascalCase

**Variables:**
- `page_list`: List variables use underscore-separated names
- `opt`: Configuration object (short name for frequent use)
- `toc_with_page_number`: Descriptive names indicating structure
- `model`: LLM model identifier (frequent parameter)

**Types:**
- `SimpleNamespace as config`: Configuration wrapper (from `types`)
- Implicit dictionaries for tree nodes (no class wrapper)
- Implicit lists for page collections

## Where to Add New Code

**New PDF Processing Feature:**
- Primary code: `pageindex/page_index.py`
- If it's a new processing mode/strategy:
  - Add function alongside `process_toc_with_page_numbers`, `process_no_toc`, etc.
  - Update `meta_processor()` to route to new mode
  - Location: `pageindex/page_index.py` around line 950+

**New Markdown Feature:**
- Primary code: `pageindex/page_index_md.py`
- Example: Additional tree transformation logic
- Location: Add function before `md_to_tree()` around line 240

**New Utility Function:**
- Shared helpers: `pageindex/utils.py`
- Examples: LLM API wrappers, tree manipulation, PDF parsing helpers
- Location: `pageindex/utils.py` (organized by purpose: APIs at top, tree ops in middle, PDF helpers below)

**New Configuration Options:**
- Config defaults: `pageindex/config.yaml`
- Config loading logic: `ConfigLoader` class in `pageindex/utils.py:681-709`
- Command-line args: `run_pageindex.py` argparse section

**Tests and Examples:**
- Test PDFs: `tests/pdfs/` (add PDF files directly)
- Example output: `tests/results/` (will be auto-generated)
- Jupyter notebooks: `cookbook/` (add `.ipynb` files with examples)
- Guides: `tutorials/` (add markdown or directory with guides)

**Command-Line Interface:**
- Entry point: `run_pageindex.py`
- Add argument via argparse:
  ```python
  parser.add_argument('--new-option', type=str, default='default_value', help='Description')
  ```
- Wire to config: Pass in `opt = config_loader.load(user_opt)` or `opt = config(...)`

## Special Directories

**pageindex/**
- Purpose: Package directory containing all source code
- Generated: No, committed
- Committed: Yes

**.planning/codebase/**
- Purpose: GSD orchestrator documentation
- Generated: Yes (created by `/gsd:map-codebase`)
- Committed: Yes (preserved for reference)

**tests/results/**
- Purpose: Generated tree structure outputs
- Generated: Yes, created when running `run_pageindex.py` on PDFs
- Committed: Yes, contains example outputs for validation

**results/** (root level, created at runtime)
- Purpose: Output directory when running `run_pageindex.py` from project root
- Generated: Yes, dynamically created
- Committed: No (in .gitignore)

**.env** (not visible, referenced in utils.py)
- Purpose: Environment variables for API keys (GOOGLE_API_KEY)
- Generated: No, user-created
- Committed: No (in .gitignore for security)

## File Organization Patterns

**PDF Processing Pipeline:**
- Detection phase: `check_toc()`, `find_toc_pages()`, `toc_detector_single_page()`
- Extraction phase: `toc_extractor()`, `toc_transformer()`, `toc_index_extractor()`
- Processing phase: `process_toc_with_page_numbers()`, `process_toc_no_page_numbers()`, `process_no_toc()`
- Validation phase: `verify_toc()`, `check_title_appearance()`
- Correction phase: `fix_incorrect_toc()`, `fix_incorrect_toc_with_retries()`
- All in: `pageindex/page_index.py` (organized top-to-bottom by pipeline stage)

**Markdown Pipeline:**
- Extraction: `extract_nodes_from_markdown()`, `extract_node_text_content()`
- Refinement: `update_node_list_with_text_token_count()`, `tree_thinning_for_index()`
- Building: `build_tree_from_nodes()`, `clean_tree_for_output()`
- Enrichment: `get_node_summary()`, `generate_summaries_for_structure_md()`
- Main orchestrator: `md_to_tree()`
- All in: `pageindex/page_index_md.py` (organized by stage)

**Utilities by Category (pageindex/utils.py):**
- **LLM API**: `Gemini_API()`, `Gemini_API_async()`, `Gemini_API_with_finish_reason()` (lines 22-109)
- **JSON/Response**: `extract_json()`, `get_json_content()`, `extract_text_from_pdf()` (lines 111-250)
- **PDF Operations**: `get_page_tokens()`, `get_number_of_pages()`, `get_text_of_pages()` (lines 413-500)
- **Tree Operations**: `list_to_tree()`, `post_processing()`, `add_node_text()`, `structure_to_list()` (lines 350-625)
- **Node Enhancement**: `write_node_id()`, `generate_summaries_for_structure()`, `generate_doc_description()` (lines 158-659)
- **Config**: `ConfigLoader` class (lines 681-709)
- **Output**: `print_toc()`, `print_json()`, `reorder_dict()`, `format_structure()` (lines 507-678)

## Module Dependencies

**pageindex/__init__.py** (Public API):
- Imports from: `page_index.py`, `page_index_md.py`
- Exports: `page_index()`, `page_index_main()`, `md_to_tree()`, `config()`

**pageindex/page_index.py** (PDF Pipeline):
- Imports from: `utils.py` (all utilities)
- Uses: Async/await, concurrent.futures
- External: google-genai, pymupdf, PyPDF2

**pageindex/page_index_md.py** (Markdown Pipeline):
- Imports from: `utils.py` (helpers)
- Uses: Async/await, regex
- External: None (pure Python with utils dependency)

**pageindex/utils.py** (Utilities):
- Imports from: Standard library, config.yaml
- Exports to: `page_index.py`, `page_index_md.py`, `run_pageindex.py`
- External: google-genai, pymupdf, PyPDF2, pyyaml

**run_pageindex.py** (CLI):
- Imports from: `pageindex/__init__.py`, `pageindex/utils.py` (ConfigLoader)
- External: argparse, asyncio

## How to Find Things

**"Where do I add a new PDF processing feature?"**
- Answer: `pageindex/page_index.py` around line 950+ in `meta_processor()` for routing, or new function before it

**"Where is the Gemini API call?"**
- Answer: `pageindex/utils.py:61-108` (`Gemini_API()`, `Gemini_API_async()`)

**"Where are tree nodes created?"**
- Answer: `pageindex/utils.py:350` (`list_to_tree()`) for PDF, `pageindex/page_index_md.py:190` (`build_tree_from_nodes()`) for Markdown

**"Where is the main orchestration?"**
- Answer: `pageindex/page_index.py:1058` (`page_index_main()`) for PDF, `pageindex/page_index_md.py:243` (`md_to_tree()`) for Markdown

**"Where are configuration defaults?"**
- Answer: `pageindex/config.yaml` for YAML defaults, `pageindex/utils.py:681` (`ConfigLoader`) for loading

**"Where does command-line argument parsing happen?"**
- Answer: `run_pageindex.py:9-37` (argparse setup)

---

*Structure analysis: 2026-02-15*
