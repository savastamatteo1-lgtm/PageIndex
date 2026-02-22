# Coding Conventions

**Analysis Date:** 2026-02-15

## Naming Patterns

**Files:**
- Lowercase with underscores: `page_index.py`, `page_index_md.py`, `utils.py`
- Python module files follow PEP 8 standard

**Functions:**
- Lowercase with underscores: `check_title_appearance()`, `extract_json()`, `get_pdf_title()`
- Async functions use `async def` prefix: `check_title_appearance_in_start_concurrent()`, `Gemini_API_async()`
- Helper/nested functions use lowercase: `find_node()`, `find_all_children()`
- Private/internal functions do not use leading underscore (example: `extract_json()` is public despite internal use)

**Variables:**
- Snake_case for variable names: `pdf_reader`, `page_list`, `toc_content`, `max_retries`
- Dictionary keys use snake_case: `'physical_index'`, `'node_id'`, `'start_index'`, `'end_index'`
- Loop variables use snake_case: `page_num`, `line_num`, `node_id`

**Types/Classes:**
- PascalCase for class names: `JsonLogger`, `ConfigLoader`
- Classes use `__init__()` and standard Python conventions
- SimpleNamespace imported as `config` and used as lightweight config object: `config(**merged)`

## Code Style

**Formatting:**
- No explicit linting/formatting tool detected (no `.eslintrc`, `.prettierrc`, `black` config, or `isort` config)
- Indentation appears to be 4 spaces (Python standard)
- Line length is variable with some long lines (e.g., long f-strings with prompts)

**Linting:**
- No active linting tool configured
- Code shows manual adherence to PEP 8 conventions

## Import Organization

**Order:**
1. Standard library imports: `os`, `json`, `copy`, `math`, `random`, `re`, `logging`, `time`, `asyncio`
2. Third-party imports: `google.genai`, `PyPDF2`, `pymupdf`, `yaml`, `pathlib`
3. Relative imports: `from .utils import *`, `from .page_index import *`

**Example from `utils.py` (lines 1-18):**
```python
from google import genai
from google.genai import types
import logging
import os
from datetime import datetime
import time
import json
import PyPDF2
import copy
import asyncio
import pymupdf
from io import BytesIO
from dotenv import load_dotenv
load_dotenv()
import logging  # duplicated - indicates possible oversight
import yaml
from pathlib import Path
from types import SimpleNamespace as config
```

**Path Aliases:**
- Uses relative imports with dot notation: `from .utils import *`, `from .page_index import *`
- No explicit path alias configuration; relies on package structure

**Notable Pattern:**
- Wildcard imports (`from .utils import *`) used in `page_index.py` and `page_index_md.py`
- This indicates high interdependency between modules

## Error Handling

**Patterns:**
- Generic exception handling with `try/except` blocks (lines 29-57 in `utils.py`)
- Retry logic with exponential delay: max 10 retries with 1-second wait between attempts
- Graceful degradation: returns `"Error"` string on max retries rather than raising exception
- Try/except for JSON parsing with fallback cleanup steps (lines 125-156 in `utils.py`)
- Returns empty dict `{}` on JSON parsing failure

**Example from `Gemini_API()` (lines 61-87 in `utils.py`):**
```python
for i in range(max_retries):
    try:
        # operation
        return response.text
    except Exception as e:
        print('************* Retrying *************')
        logging.error(f"Error: {e}")
        if i < max_retries - 1:
            time.sleep(1)
        else:
            logging.error('Max retries reached for prompt: ' + prompt)
            return "Error"
```

## Logging

**Framework:** Python standard `logging` module

**Patterns:**
- `logging.error()` for error messages
- `logging.info()` for informational messages
- Print statements also used (`print()`) for console output
- Custom `JsonLogger` class (lines 309-345 in `utils.py`) wraps logs in JSON format

**Custom Logger:**
```python
class JsonLogger:
    def log(self, level, message, **kwargs):
        if isinstance(message, dict):
            self.log_data.append(message)
        else:
            self.log_data.append({'message': message})
        # Writes to JSON file in ./logs/
```

**When/how to log:**
- API errors and retries logged as errors
- Processing steps logged as info (e.g., "Checking title appearance in start concurrently")
- JSON logger used for structured output to JSON files

## Comments

**When to Comment:**
- Comments used for section headers with repeated `#` characters: `################### check title in page #########################################################`
- Comments used for clarification of non-obvious logic
- Inline comments sparingly used; code is mostly self-documenting through naming

**JSDoc/TSDoc:**
- Not used (Python codebase)
- No docstrings observed in function definitions
- Prompts to LLM serve as inline documentation for AI-driven operations

## Function Design

**Size:**
- Functions vary from small (10-20 lines) to large (100+ lines)
- Large functions: `page_index_main()` (1143 lines across file), `Gemini_API()` (26 lines)
- Async functions tend to be smaller due to concurrent patterns

**Parameters:**
- Optional parameters with sensible defaults: `model=None`, `logger=None`, `start_index=1`, `chat_history=None`
- Parameters use keyword arguments: `count_tokens(text, model=None)`
- Tuple returns common: `return response, "max_output_reached"`

**Return Values:**
- Dictionaries returned for structured data: `{'list_index': ..., 'answer': ..., 'title': ...}`
- Lists returned for collections: `get_nodes()` returns list of nodes
- Simple strings/booleans for status: `'yes'` or `'no'` for boolean-like responses
- None for missing values: checked with `if item.get('physical_index') is None`

## Module Design

**Exports:**
- `__init__.py` (line 1-2) uses explicit imports: `from .page_index import *` and `from .page_index_md import md_to_tree`
- All public functions available at package level through `__init__.py`

**Barrel Files:**
- Single `__init__.py` serves as barrel file, importing from all major modules
- Enables usage like: `from pageindex import check_title_appearance`, `from pageindex import md_to_tree`

---

*Convention analysis: 2026-02-15*
