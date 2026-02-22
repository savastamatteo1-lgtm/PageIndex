# Testing Patterns

**Analysis Date:** 2026-02-15

## Test Framework

**Runner:**
- No test framework detected (pytest, unittest, or other test runners)
- No test configuration files found (`pytest.ini`, `setup.cfg`, `tox.ini`, `pyproject.toml`)

**Assertion Library:**
- Not applicable - no testing framework configured

**Run Commands:**
- No standard test commands defined
- Tests appear to be manual or integrated into example scripts in `/cookbook` directory

## Test File Organization

**Location:**
- Test files directory exists at `/Users/matteo/Desktop/PAI/PageIndex/tests/`
- Contains subdirectories: `pdfs/` (test PDFs) and `results/` (test output JSON files)
- No Python test files (`.py`) found in tests directory

**Naming:**
- No test naming convention established
- Results stored as `{document_name}_structure.json` in `tests/results/`

**Structure:**
```
tests/
├── pdfs/              # Test PDF documents
│   ├── 2023-annual-report.pdf
│   ├── PRML.pdf
│   ├── four-lectures.pdf
│   ├── etc.
├── results/           # Test output JSON structures
│   ├── PRML_structure.json
│   ├── 2023-annual-report_structure.json
│   └── ...
```

## Test Structure

**Suite Organization:**
- No formal test suites defined
- Manual testing approach: `run_pageindex.py` script used to test PDF/Markdown processing

**Patterns:**
- **No setup/teardown:** Testing relies on file I/O and API calls; no fixture setup/teardown
- **No assertion pattern:** Tests are implicit - valid JSON output indicates success
- **Manual verification:** Test results stored as JSON files for visual inspection

## Mocking

**Framework:**
- No mocking framework detected (unittest.mock or pytest-mock)

**Patterns:**
- No mocking observed in codebase
- All API calls to Gemini are real (use actual GOOGLE_API_KEY from environment)
- No mock objects for external services

**What to Mock:**
- Gemini API calls (`Gemini_API`, `Gemini_API_async`, `Gemini_API_with_finish_reason`)
- PDF parsing to speed up tests and avoid file I/O
- LLM responses for deterministic test outcomes

**What NOT to Mock:**
- JSON parsing and extraction logic (needs real test data)
- Tree structure building and transformation
- Core document indexing algorithms

## Fixtures and Factories

**Test Data:**
- No test fixtures defined in Python
- Real PDF files stored in `tests/pdfs/` directory
- Sample expected outputs stored in `tests/results/` as JSON files

**Example test PDF files:**
- `PRML.pdf` - Machine learning textbook
- `2023-annual-report.pdf` - Corporate annual report
- `earthmover.pdf` - Research paper
- `four-lectures.pdf` - Educational material

**Location:**
- Test PDFs: `/Users/matteo/Desktop/PAI/PageIndex/tests/pdfs/`
- Expected results: `/Users/matteo/Desktop/PAI/PageIndex/tests/results/`

## Coverage

**Requirements:**
- No coverage tool configured or enforced
- No coverage targets defined

**View Coverage:**
- Not applicable - no coverage measurement infrastructure

## Test Types

**Unit Tests:**
- No unit tests present in codebase
- Utility functions like `extract_json()`, `write_node_id()`, `structure_to_list()` lack isolated tests
- These could be tested independently without API calls

**Integration Tests:**
- Implicit integration testing via `run_pageindex.py` script
- Tests complete workflows: PDF loading → TOC detection → indexing → JSON output
- Uses real PDFs and Gemini API calls
- Results stored for manual inspection

**Example integration test flow (`run_pageindex.py`, lines 46-79):**
```python
# 1. Load PDF file
pdf_path = args.pdf_path

# 2. Create configuration
opt = config(
    model=args.model,
    toc_check_page_num=args.toc_check_pages,
    max_page_num_each_node=args.max_pages_per_node,
    max_token_num_each_node=args.max_tokens_per_node,
    # ... other options
)

# 3. Process PDF
toc_with_page_number = page_index_main(args.pdf_path, opt)

# 4. Save and verify output
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(toc_with_page_number, f, indent=2)
```

**E2E Tests:**
- Markdown processing tested via `md_to_tree()` function in `run_pageindex.py` (lines 81-132)
- Example: `--md_path` argument processes markdown files end-to-end
- Output compared against expected JSON structure format

**Test invocation:**
```bash
# PDF E2E test
python run_pageindex.py --pdf_path tests/pdfs/PRML.pdf --model gemini-3.1-pro-preview

# Markdown E2E test
python run_pageindex.py --md_path example.md --if-thinning yes
```

## Common Patterns

**Async Testing:**
- Async functions used extensively for concurrent API calls
- Example: `check_title_appearance_in_start_concurrent()` (page_index.py, lines 74-102)
- Uses `asyncio.gather(*tasks, return_exceptions=True)` to handle multiple concurrent operations

**Async pattern example (page_index_md.py, lines 19-29):**
```python
async def generate_summaries_for_structure_md(structure, summary_token_threshold, model=None):
    nodes = structure_to_list(structure)
    tasks = [get_node_summary(node, summary_token_threshold=summary_token_threshold, model=model) for node in nodes]
    summaries = await asyncio.gather(*tasks)

    for node, summary in zip(nodes, summaries):
        if not node.get('nodes'):
            node['summary'] = summary
        else:
            node['prefix_summary'] = summary
    return structure
```

**Error Testing:**
- JSON extraction has fallback/cleanup logic (utils.py, lines 125-156)
- Handles malformed JSON responses from LLM
- Retries with modified chat history for incomplete TOC extraction

**Error handling pattern (utils.py, lines 125-156):**
```python
def extract_json(content):
    try:
        # First attempt with delimiters
        json_content = content[start_idx:end_idx].strip()
        return json.loads(json_content)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to extract JSON: {e}")
        try:
            # Retry with cleanup
            json_content = json_content.replace(',]', ']').replace(',}', '}')
            return json.loads(json_content)
        except:
            logging.error("Failed to parse JSON even after cleanup")
            return {}  # Return empty dict on final failure
```

---

*Testing analysis: 2026-02-15*
