# Technology Stack

**Analysis Date:** 2026-02-15

## Languages

**Primary:**
- Python 3 - Core application language for document processing, tree generation, and API interactions

**Secondary:**
- JSON - Configuration and output format for tree structures

## Runtime

**Environment:**
- Python 3.x (version not explicitly pinned in requirements.txt, but dependencies indicate 3.8+)

**Package Manager:**
- pip (Python package manager)
- Lockfile: `requirements.txt` (simple pinned dependencies without hash verification)

## Frameworks

**Core:**
- OpenAI Python Client (`openai==1.101.0`) - Integration with OpenAI's API for LLM-based document analysis and reasoning

**PDF Processing:**
- PyMuPDF (`pymupdf==1.26.4`) - PDF text extraction and page processing
- PyPDF2 (`PyPDF2==3.0.1`) - PDF manipulation and page handling (secondary to PyMuPDF)

**Token Counting:**
- tiktoken (`tiktoken==0.11.0`) - Token counting for OpenAI models to manage context windows

**Configuration:**
- python-dotenv (`python-dotenv==1.1.0`) - Environment variable loading for API keys and secrets
- PyYAML (`pyyaml==6.0.2`) - Configuration file parsing (used for `config.yaml`)

**Utilities:**
- asyncio (Python standard library) - Asynchronous programming for concurrent API calls and processing
- concurrent.futures (Python standard library) - Thread pooling for parallel PDF processing

## Key Dependencies

**Critical:**
- `openai==1.101.0` - Enables all reasoning-based document analysis features. Application cannot function without valid API key.
- `pymupdf==1.26.4` - Primary PDF text extraction. Heavily used in `pageindex/page_index.py` for PDF parsing.
- `tiktoken==0.11.0` - Token counting essential for managing LLM context limits and tracking node token budgets.

**Infrastructure:**
- `python-dotenv==1.1.0` - Loads `CHATGPT_API_KEY` environment variable at application startup
- `pyyaml==6.0.2` - Loads default configuration from `pageindex/config.yaml`
- `PyPDF2==3.0.1` - Fallback/supplementary PDF handling, used alongside PyMuPDF

## Configuration

**Environment:**
- Configuration loaded via `python-dotenv` from `.env` file (listed in `.gitignore`)
- Primary env var: `CHATGPT_API_KEY` - Required for all OpenAI API calls
- Config file: `pageindex/config.yaml` - Default settings for document processing parameters

**Key Configuration Values (from `pageindex/config.yaml`):**
```yaml
model: "gpt-4o-2024-11-20"
toc_check_page_num: 20
max_page_num_each_node: 10
max_token_num_each_node: 20000
if_add_node_id: "yes"
if_add_node_summary: "yes"
if_add_doc_description: "no"
if_add_node_text: "no"
```

**Build:**
- No explicit build configuration (pure Python, no compilation needed)
- Entry point: `run_pageindex.py` - Command-line interface for document processing

## Platform Requirements

**Development:**
- Python 3.8 or higher
- pip package manager
- OpenAI API account with valid API key
- ~50MB disk space for dependencies

**Production:**
- Same Python runtime requirements
- Network connectivity for OpenAI API calls
- API rate limits: Application implements 10-retry logic with exponential backoff

## API Behavior & Resilience

**OpenAI Integration Patterns:**
- Synchronous calls via `ChatGPT_API()` in `pageindex/utils.py:52-75`
- Asynchronous calls via `ChatGPT_API_async()` in `pageindex/utils.py:76-92`
- Retry mechanism: 10 attempts with 1-second delays between retries
- Temperature: 0 (deterministic responses for consistent document analysis)
- Error handling: Logs failures, returns "Error" string on max retry exhaustion

**Token Management:**
- Uses `tiktoken.encoding_for_model(model)` to get accurate token counts
- Enforces `max_token_num_each_node: 20000` for context window management
- Node summaries generated only when token count exceeds `summary_token_threshold`

---

*Stack analysis: 2026-02-15*
