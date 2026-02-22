# External Integrations

**Analysis Date:** 2026-02-15

## APIs & External Services

**Google Gemini API:**
- Service: Google Gemini (Gemini models for reasoning-based document analysis)
- What it's used for: Core intelligence for:
  - Table of Contents detection (`toc_detector_single_page()` in `pageindex/page_index.py`)
  - Section title appearance checking (`check_title_appearance()`)
  - Document structure generation and refinement
  - Node summary generation (`generate_node_summary()` in `pageindex/utils.py:605`)
  - Document description generation (`generate_doc_description()` in `pageindex/utils.py:649`)
  - Markdown structure processing
  - All reasoning-native retrieval operations
  - SDK/Client: `google-genai>=1.47.0` (Google Gemini Python SDK)
  - Auth: Environment variable `GOOGLE_API_KEY`
  - Endpoints used:
    - Content generation: `_gemini_client.models.generate_content()`
    - Async variant: `_gemini_client.aio.models.generate_content()`

## Data Storage

**Databases:**
- None detected - Application is stateless. No database integration.

**File Storage:**
- Local filesystem only
  - Input: PDF files or Markdown files (user-provided)
  - Output: JSON tree structure files saved to `./results/` directory
  - No cloud storage integration detected

**Caching:**
- None - Every run processes document fresh. No caching layer present.

## Authentication & Identity

**Auth Provider:**
- Custom - API key-based authentication

**Implementation:**
- Gemini API key loaded from environment via `python-dotenv`
- In `pageindex/utils.py:20`: `GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")`
- Key is passed to all Gemini API calls: `Gemini_API(model, prompt, api_key=GOOGLE_API_KEY)`
- Async variant: `Gemini_API_async(model, prompt, api_key=GOOGLE_API_KEY)`
- No authentication token refresh mechanism implemented
- API key must be valid for entire processing session

## Monitoring & Observability

**Error Tracking:**
- None detected - No external error tracking service (Sentry, DataDog, etc.)

**Logs:**
- Standard Python logging module (`import logging`)
- Log level setup in multiple modules:
  - `pageindex/utils.py:329` - JsonLogger class for structured logging
  - Error logging in retry loops: `logging.error(f"Error: {e}")`
  - Application prints progress to stdout: `print()` statements in `run_pageindex.py`
- No centralized log aggregation service

## CI/CD & Deployment

**Hosting:**
- Self-hosted only - Application designed for local/on-premise execution
- Cloud service options available separately (mentioned in README: chat.pageindex.ai, MCP integration, API)
- No Docker configuration detected in this repository

**CI Pipeline:**
- None detected - No GitHub Actions, GitLab CI, or other automated testing/deployment

## Environment Configuration

**Required env vars:**
- `GOOGLE_API_KEY` - Gemini API key (must be valid, no fallback provided)

**Optional env vars:**
- None explicitly defined beyond `GOOGLE_API_KEY`

**Secrets location:**
- `.env` file in project root (loaded by `python-dotenv` at startup)
- `.env*` pattern ignored in `.gitignore` to prevent accidental commits

**Configuration file location:**
- `pageindex/config.yaml` - Default parameters for document processing
- Overridable via command-line arguments in `run_pageindex.py`

## Webhooks & Callbacks

**Incoming:**
- None - Application does not expose HTTP endpoints or webhook receivers

**Outgoing:**
- None - Application makes one-way API calls to Gemini only. No callbacks or polling mechanisms.

## API Rate Limiting & Quotas

**Gemini API Considerations:**
- Rate limits: Subject to Google Gemini API account quotas
- Retry strategy: 10 retries with 1-second linear backoff per failed API call
- No rate limit handling: Application does not implement token bucket, exponential backoff for rate limits, or adaptive retry delays
- Cost implications:
  - Model: `gemini-3.1-pro-preview`
  - Costs scale with document size: longer documents = more API calls for tree generation
  - Token counting via Gemini built-in `count_tokens` API
- Error handling: Returns "Error" string on max retries exceeded (caller responsible for handling)

## Data Flow During Processing

**PDF Processing Pipeline:**
1. User provides PDF path via `run_pageindex.py --pdf_path`
2. `pymupdf` extracts text from all pages: `pageindex/utils.py:extract_text_from_pdf()`
3. Gemini API counts tokens via `_gemini_client.models.count_tokens()` per page and section
4. Gemini API called to:
   - Detect table of contents in first N pages (`toc_check_page_num: 20`)
   - Extract and structure TOC into tree
   - Verify section titles appear in expected pages
   - Generate summaries for nodes exceeding token thresholds
   - Generate document description (optional)
5. Tree structure output to JSON: `results/{filename}_structure.json`

**Markdown Processing Pipeline:**
1. User provides Markdown path via `run_pageindex.py --md_path`
2. `page_index_md.py:extract_nodes_from_markdown()` parses headers
3. Optional tree thinning: merges small nodes if below `min_token_threshold`
4. Async calls to Gemini for summaries: `asyncio.gather()` for concurrent processing
5. Document description generated if `if_add_doc_description='yes'`
6. Tree structure output to JSON: `results/{filename}_structure.json`

## Token & Context Management

**Token Budgets:**
- Per-node limit: `max_token_num_each_node: 20000` (from config)
- Summary generation threshold: `summary_token_threshold: 200` (configurable)
- Token counting: Uses Gemini API built-in token counting via `_gemini_client.models.count_tokens(model, contents)`

**Concurrent API Calls:**
- Used in: `pageindex/page_index.py` - concurrent PDF page processing
- Method: `concurrent.futures.ThreadPoolExecutor` for multi-page processing
- Used in: `pageindex/page_index_md.py` - parallel node summary generation
- Method: `asyncio.gather()` for async Gemini calls

---

*Integration audit: 2026-02-15*
