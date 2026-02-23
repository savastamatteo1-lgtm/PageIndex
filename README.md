<div align="center">
  
<a href="https://vectify.ai/pageindex" target="_blank">
  <img src="https://github.com/user-attachments/assets/46201e72-675b-43bc-bfbd-081cc6b65a1d" alt="PageIndex Banner" />
</a>

<br/>
<br/>

<p align="center">
  <a href="https://trendshift.io/repositories/14736" target="_blank"><img src="https://trendshift.io/api/badge/repositories/14736" alt="VectifyAI%2FPageIndex | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
</p>

# PageIndex: Vectorless, Reasoning-based RAG

<p align="center"><b>Reasoning-based RAG&nbsp; ◦ &nbsp;No Vector DB&nbsp; ◦ &nbsp;No Chunking&nbsp; ◦ &nbsp;Human-like Retrieval</b></p>

<h4 align="center">
  <a href="https://vectify.ai">🏠 Homepage</a>&nbsp; • &nbsp;
  <a href="https://chat.pageindex.ai">🖥️ Chat Platform</a>&nbsp; • &nbsp;
  <a href="https://pageindex.ai/mcp">🔌 MCP</a>&nbsp; • &nbsp;
  <a href="https://docs.pageindex.ai">📚 Docs</a>&nbsp; • &nbsp;
  <a href="https://discord.com/invite/VuXuf29EUj">💬 Discord</a>&nbsp; • &nbsp;
  <a href="https://ii2abc2jejf.typeform.com/to/tK3AXl8T">✉️ Contact</a>&nbsp;
</h4>
  
</div>


<details open>
<summary><h3>📢 Latest Updates</h3></summary>

 **🔥 Releases:**
- [**PageIndex Chat**](https://chat.pageindex.ai): The first human-like document-analysis agent [platform](https://chat.pageindex.ai) built for professional long documents. Can also be integrated via [MCP](https://pageindex.ai/mcp) or [API](https://docs.pageindex.ai/quickstart) (beta).
<!-- - [**PageIndex Chat API**](https://docs.pageindex.ai/quickstart): An API that brings PageIndex's advanced long-document intelligence directly into your applications and workflows. -->
<!-- - [PageIndex MCP](https://pageindex.ai/mcp): Bring PageIndex into Claude, Cursor, or any MCP-enabled agent. Chat with long PDFs in a reasoning-based, human-like way. -->
 
 **📝 Articles:**
- [**PageIndex Framework**](https://pageindex.ai/blog/pageindex-intro): Introduces the PageIndex framework — an *agentic, in-context* *tree index* that enables LLMs to perform *reasoning-based*, *human-like retrieval* over long documents, without vector DB or chunking.
<!-- - [Do We Still Need OCR?](https://pageindex.ai/blog/do-we-need-ocr): Explores how vision-based, reasoning-native RAG challenges the traditional OCR pipeline, and why the future of document AI might be *vectorless* and *vision-based*. -->

 **🧪 Cookbooks:**
- [Vectorless RAG](https://docs.pageindex.ai/cookbook/vectorless-rag-pageindex): A minimal, hands-on example of reasoning-based RAG using PageIndex. No vectors, no chunking, and human-like retrieval.
- [Vision-based Vectorless RAG](https://docs.pageindex.ai/cookbook/vision-rag-pageindex): OCR-free, vision-only RAG with PageIndex's reasoning-native retrieval workflow that works directly over PDF page images.
</details>

---

# 📑 Introduction to PageIndex

Are you frustrated with vector database retrieval accuracy for long professional documents? Traditional vector-based RAG relies on semantic *similarity* rather than true *relevance*. But **similarity ≠ relevance** — what we truly need in retrieval is **relevance**, and that requires **reasoning**. When working with professional documents that demand domain expertise and multi-step reasoning, similarity search often falls short.

Inspired by AlphaGo, we propose **[PageIndex](https://vectify.ai/pageindex)** — a **vectorless**, **reasoning-based RAG** system that builds a **hierarchical tree index** from long documents and uses LLMs to **reason** *over that index* for **agentic, context-aware retrieval**.
It simulates how *human experts* navigate and extract knowledge from complex documents through *tree search*, enabling LLMs to *think* and *reason* their way to the most relevant document sections. PageIndex performs retrieval in two steps:

1. Generate a “Table-of-Contents” **tree structure index** of documents
2. Perform reasoning-based retrieval through **tree search**

<div align="center">
  <a href="https://pageindex.ai/blog/pageindex-intro" target="_blank" title="The PageIndex Framework">
    <img src="https://docs.pageindex.ai/images/cookbook/vectorless-rag.png" width="70%">
  </a>
</div>

### 🎯 Core Features 

Compared to traditional vector-based RAG, **PageIndex** features:
- **No Vector DB**: Uses document structure and LLM reasoning for retrieval, instead of vector similarity search.
- **No Chunking**: Documents are organized into natural sections, not artificial chunks.
- **Human-like Retrieval**: Simulates how human experts navigate and extract knowledge from complex documents.
- **Better Explainability and Traceability**: Retrieval is based on reasoning — traceable and interpretable, with page and section references. No more opaque, approximate vector search (“vibe retrieval”).

PageIndex powers a reasoning-based RAG system that achieved **state-of-the-art** [98.7% accuracy](https://github.com/VectifyAI/Mafin2.5-FinanceBench) on FinanceBench, demonstrating superior performance over vector-based RAG solutions in professional document analysis (see our [blog post](https://vectify.ai/blog/Mafin2.5) for details).

### 📍 Explore PageIndex

To learn more, please see a detailed introduction of the [PageIndex framework](https://pageindex.ai/blog/pageindex-intro). Check out this GitHub repo for open-source code, and the [cookbooks](https://docs.pageindex.ai/cookbook), [tutorials](https://docs.pageindex.ai/tutorials), and [blog](https://pageindex.ai/blog) for additional usage guides and examples. 

The PageIndex service is available as a ChatGPT-style [chat platform](https://chat.pageindex.ai), or can be integrated via [MCP](https://pageindex.ai/mcp) or [API](https://docs.pageindex.ai/quickstart).

### 🛠️ Deployment Options
- Self-host — run locally with this open-source repo.
- Cloud Service — try instantly with our [Chat Platform](https://chat.pageindex.ai/), or integrate with [MCP](https://pageindex.ai/mcp) or [API](https://docs.pageindex.ai/quickstart).
- _Enterprise_ — private or on-prem deployment. [Contact us](https://ii2abc2jejf.typeform.com/to/tK3AXl8T) or [book a demo](https://calendly.com/pageindex/meet) for more details.

### 🧪 Quick Hands-on

- Try the [**Vectorless RAG**](https://github.com/VectifyAI/PageIndex/blob/main/cookbook/pageindex_RAG_simple.ipynb) notebook — a *minimal*, hands-on example of reasoning-based RAG using PageIndex.
- Experiment with [*Vision-based Vectorless RAG*](https://github.com/VectifyAI/PageIndex/blob/main/cookbook/vision_RAG_pageindex.ipynb) — no OCR; a minimal, reasoning-native RAG pipeline that works directly over page images.
  
<div align="center">
  <a href="https://colab.research.google.com/github/VectifyAI/PageIndex/blob/main/cookbook/pageindex_RAG_simple.ipynb" target="_blank" rel="noopener">
    <img src="https://img.shields.io/badge/Open_In_Colab-Vectorless_RAG-orange?style=for-the-badge&logo=googlecolab" alt="Open in Colab: Vectorless RAG" />
  </a>
  &nbsp;&nbsp;
  <a href="https://colab.research.google.com/github/VectifyAI/PageIndex/blob/main/cookbook/vision_RAG_pageindex.ipynb" target="_blank" rel="noopener">
    <img src="https://img.shields.io/badge/Open_In_Colab-Vision_RAG-orange?style=for-the-badge&logo=googlecolab" alt="Open in Colab: Vision RAG" />
  </a>
</div>

---

# 🌲 PageIndex Tree Structure
PageIndex can transform lengthy PDF documents into a semantic **tree structure**, similar to a _"table of contents"_ but optimized for use with Large Language Models (LLMs). It's ideal for: financial reports, regulatory filings, academic textbooks, legal or technical manuals, and any document that exceeds LLM context limits.

Below is an example PageIndex tree structure. Also see more example [documents](https://github.com/VectifyAI/PageIndex/tree/main/tests/pdfs) and generated [tree structures](https://github.com/VectifyAI/PageIndex/tree/main/tests/results).

```jsonc
...
{
  "title": "Financial Stability",
  "node_id": "0006",
  "start_index": 21,
  "end_index": 22,
  "summary": "The Federal Reserve ...",
  "nodes": [
    {
      "title": "Monitoring Financial Vulnerabilities",
      "node_id": "0007",
      "start_index": 22,
      "end_index": 28,
      "summary": "The Federal Reserve's monitoring ..."
    },
    {
      "title": "Domestic and International Cooperation and Coordination",
      "node_id": "0008",
      "start_index": 28,
      "end_index": 31,
      "summary": "In 2023, the Federal Reserve collaborated ..."
    }
  ]
}
...
```

You can generate the PageIndex tree structure with this open-source repo, or use our [API](https://docs.pageindex.ai/quickstart) 

---

# ⚙️ Package Usage

### 1. Install dependencies

```bash
pip3 install --upgrade -r requirements.txt
```

Key dependencies: `google-genai`, `pymupdf`, `PyPDF2`, `python-dotenv`, `pyyaml`, `litellm` (multi-provider LLM), `supabase` (database client), `pydantic-settings` (layered configuration), `tenacity` (retry logic).

### 2. Set up credentials

Create a `.env` file in the root directory:

```bash
# Required — Supabase connection for document storage and retrieval
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key

# LLM provider (default: Google Gemini)
GOOGLE_API_KEY=your_google_api_key_here
```

> **Multi-provider support:** PageIndex uses [LiteLLM](https://github.com/BerriAI/litellm) under the hood, so you can use any supported provider. Set the appropriate API key (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.) and update the model name in `pageindex/config.yaml` or pass it as a constructor kwarg.

### 3. Quick Start — PageIndex API

The `PageIndex` class is the primary entry point for multi-document ingestion, search, and retrieval:

```python
from pageindex import PageIndex

pi = PageIndex(supabase_url="https://xxx.supabase.co", supabase_key="xxx")

# Ingest a PDF (runs the full 6-stage pipeline)
result = pi.ingest(path="/path/to/document.pdf")
print(result.document_id, result.chunks_created)

# Search with automatic strategy selection
resp = pi.search("sentenze della Corte di Cassazione dal 2020")
print(resp.strategy_used, resp.timing, len(resp.results))

# Retrieve a specific document by ID
doc = pi.retrieve(doc_id="...")
print(doc.name, doc.metadata)

# List all stored documents
docs = pi.list_documents(limit=50)
```

See the [Multi-Document Legal Retrieval](#-multi-document-legal-retrieval) section below for full API details, configuration options, and search strategies.

<details>
<summary><strong>Alternative: Tree Structure Generation (CLI)</strong></summary>
<br>

You can also use PageIndex as a standalone CLI to generate tree structures from individual documents (the original single-document workflow):

```bash
python3 run_pageindex.py --pdf_path /path/to/your/document.pdf
```

<details>
<summary>Optional parameters</summary>
<br>

```
--model                 LLM model to use (default: gemini-3.1-pro-preview)
--toc-check-pages       Pages to check for table of contents (default: 20)
--max-pages-per-node    Max pages per node (default: 10)
--max-tokens-per-node   Max tokens per node (default: 20000)
--if-add-node-id        Add node ID (yes/no, default: yes)
--if-add-node-summary   Add node summary (yes/no, default: yes)
--if-add-doc-description Add doc description (yes/no, default: no)
```
</details>

<details>
<summary>Markdown support</summary>
<br>

We also provide markdown support for PageIndex. You can use the `-md_path` flag to generate a tree structure for a markdown file.

```bash
python3 run_pageindex.py --md_path /path/to/your/document.md
```

> Note: in this function, we use "#" to determine node heading and their levels. For example, "##" is level 2, "###" is level 3, etc. Make sure your markdown file is formatted correctly. If your Markdown file was converted from a PDF or HTML, we don't recommend using this function, since most existing conversion tools cannot preserve the original hierarchy. Instead, use our [PageIndex OCR](https://pageindex.ai/blog/ocr), which is designed to preserve the original hierarchy, to convert the PDF to a markdown file and then use this function.
</details>

</details>

---

# 📂 Multi-Document Legal Retrieval

PageIndex extends beyond single-document indexing with a **multi-document storage and retrieval layer** designed for Italian legal documents. The system provides a complete pipeline from PDF ingestion through to multi-strategy search.

### Ingestion Pipeline

The `ingest()` method runs a **6-stage pipeline** that transforms a raw PDF into a fully indexed, searchable record:

| Stage | Description |
|-------|-------------|
| 1. Tree Index | Builds a hierarchical tree structure via LLM reasoning |
| 2. Metadata Extraction | LLM-based extraction of Italian legal metadata (doc_type, authority, ECLI, legal_area, parties) |
| 3. Description Generation | LLM-based one-sentence document description |
| 4. Chunking | Tree-aware recursive chunking that respects document structure |
| 5. Embedding | Batch embedding with token-limit validation |
| 6. Storage | Persists document, tree, chunks, and embeddings to Supabase |

```python
from pageindex import PageIndex

pi = PageIndex(supabase_url="https://xxx.supabase.co", supabase_key="xxx")

result = pi.ingest(
    path="/path/to/decreto_legislativo.pdf",
    additional_fields={"source": "EUR-Lex", "year": 2024},
)
print(result.status)          # "succeeded"
print(result.chunks_created)  # e.g. 142
print(result.document_id)     # UUID
```

### Search Strategies

PageIndex supports four retrieval strategies. In `"auto"` mode (default), an LLM classifies the query intent and selects the optimal strategy automatically.

| Strategy | Description | Best for |
|----------|-------------|----------|
| `metadata` | Structured filter search on legal fields | "decreti legislativi del 2023 in materia civile" |
| `semantic` | Vector similarity search over chunk embeddings | "principio di proporzionalità nelle sanzioni" |
| `hybrid` | Fuses metadata + semantic + description via Reciprocal Rank Fusion | Broad queries mixing structure and meaning |
| `auto` | LLM-based intent classification → dispatches to above | General use (recommended) |

```python
# Automatic strategy selection (default)
resp = pi.search("sentenze penali della Cassazione 2023")
print(resp.strategy_used)  # e.g. "hybrid"
print(resp.reasoning)      # LLM's strategy reasoning

# Force a specific strategy
resp = pi.search("art. 2043 codice civile", strategy="metadata")

# Engine-specific searches (bypass strategy orchestration)
results = pi.search_semantic("principio di proporzionalità", limit=5)
results = pi.search_metadata("decreti legislativi 2023", limit=10)
results = pi.search_description("riforma del processo penale", limit=5)
results = pi.search_tree("clausola di salvaguardia", doc_ids=["uuid-1", "uuid-2"])
```

### Configuration

PageIndex uses a **layered configuration system** with four priority levels (highest wins):

1. **Constructor kwargs** — `PageIndex(llm={"completion_model": "..."})`
2. **Environment variables** — `PAGEINDEX_LLM__COMPLETION_MODEL=...` (prefix `PAGEINDEX_`, `__` for nesting)
3. **YAML config file** — `pageindex/config.yaml`
4. **Field defaults** — built-in sensible defaults

The configuration is organized into four sub-models:

| Sub-model | Key parameters | Defaults |
|-----------|---------------|----------|
| `supabase` | `url`, `key` | _(required — no defaults)_ |
| `llm` | `completion_model`, `embedding_model`, `temperature` | `gemini/gemini-2.0-flash`, `gemini/gemini-embedding-001`, `0` |
| `ingestion` | `chunk_max_tokens`, `chunk_overlap`, `max_embedding_batch` | `800`, `0.1`, `250` |
| `retrieval` | `default_strategy`, `default_top_k`, `rrf_k` | `"auto"`, `10`, `60` |

Three constructor forms are supported:

```python
from pageindex import PageIndex, PageIndexSettings

# 1. Flat kwargs (convenience)
pi = PageIndex(supabase_url="https://xxx.supabase.co", supabase_key="xxx")

# 2. Nested dicts (explicit)
pi = PageIndex(
    supabase={"url": "https://xxx.supabase.co", "key": "xxx"},
    llm={"completion_model": "openai/gpt-4o"},
    retrieval={"default_strategy": "semantic", "default_top_k": 20},
)

# 3. Pre-built settings object (advanced)
settings = PageIndexSettings(
    supabase={"url": "https://xxx.supabase.co", "key": "xxx"},
)
pi = PageIndex(settings=settings)
```

For the most common env vars (Supabase connection), both the prefixed nested form (`PAGEINDEX_SUPABASE__URL`) and the standard flat form (`SUPABASE_URL`) are accepted.

### Database Setup

PageIndex stores data in [Supabase](https://supabase.com/) (PostgreSQL + pgvector). Three migrations set up the schema:

| Migration | Creates |
|-----------|---------|
| `001_initial_schema.sql` | `documents`, `document_trees`, `chunks` tables; `match_chunks` RPC; pgvector extension |
| `002_ingestion_status.sql` | Ingestion status tracking columns |
| `003_retrieval.sql` | Retrieval-specific indexes and functions |

Run the migrations in order in your Supabase SQL Editor (or via the Supabase CLI). The three core tables are:

| Table | Purpose |
|-------|---------|
| `documents` | Document registry with legal metadata (doc_type, authority, ECLI, legal_area, parties, etc.) |
| `chunks` | Text segments with `embedding vector(768)` for similarity search |
| `document_trees` | Serialized PageIndex tree structures per document |

### Provider-Agnostic LLM Abstraction

All LLM calls go through a unified [LiteLLM](https://github.com/BerriAI/litellm) abstraction layer, supporting Gemini, OpenAI, Anthropic, and local models. To switch providers, pass it as a constructor kwarg or update `pageindex/config.yaml`:

```yaml
llm:
  completion_model: "openai/gpt-4o"        # or "anthropic/claude-sonnet-4-20250514"
  embedding_model: "openai/text-embedding-3-small"
```

### Exception Handling

All PageIndex operations raise typed exceptions that can be caught at the desired granularity:

```python
from pageindex import PageIndex, PageIndexError, ConfigError, IngestionError, SearchError

try:
    pi = PageIndex(supabase_url="...", supabase_key="...")
    pi.ingest(path="/path/to/doc.pdf")
    pi.search("query")
except ConfigError:
    ...          # Invalid or missing configuration
except IngestionError:
    ...          # Document processing failed
except SearchError:
    ...          # Search operation failed
except PageIndexError:
    ...          # Any PageIndex error (base class)
```

### Project Structure

```
pageindex/
├── __init__.py                # Public exports (PageIndex, exceptions, settings)
├── api.py                     # PageIndex class facade, PageIndexSettings, return types
├── exceptions.py              # Exception hierarchy (PageIndexError, ConfigError, ...)
├── config.yaml                # Layered YAML configuration
├── page_index.py              # Core PDF tree structure generator
├── page_index_md.py           # Markdown tree structure generator
├── utils.py                   # Shared utilities (ConfigLoader, llm_complete, llm_embed)
├── db/                        # Supabase data access layer
│   ├── client.py              #   Connection management
│   ├── documents.py           #   Document CRUD operations
│   ├── chunks.py              #   Chunk storage and vector search
│   ├── trees.py               #   Tree structure persistence
│   └── migrations/            #   SQL schema (001, 002, 003)
├── ingestion/                 # 6-stage document processing pipeline
│   ├── pipeline.py            #   Batch orchestration
│   ├── stages.py              #   Sequential processing stages
│   ├── chunker.py             #   Tree-aware recursive chunking
│   ├── models.py              #   Pipeline data models (DocumentPipeline)
│   └── prompts.py             #   LLM prompt templates & vocabulary
├── llm/                       # Provider-agnostic LLM abstraction
│   ├── provider.py            #   LLMProvider class (completion + embedding)
│   └── config.py              #   LLM configuration loader
├── retrieval/                 # Multi-strategy search engines
│   ├── strategy.py            #   Strategy dispatcher (auto/metadata/semantic/hybrid)
│   ├── semantic.py            #   Vector similarity search
│   ├── metadata.py            #   Structured metadata filter search
│   ├── description.py         #   Document description embedding search
│   ├── tree_search.py         #   Tree-structure reasoning search
│   ├── models.py              #   Result dataclasses (FusedResult, SearchResponse, ...)
│   ├── config.py              #   Retrieval configuration loader
│   └── prompts.py             #   LLM prompt templates
└── schema/                    # Reference data
    └── legal_vocabulary.yaml  #   Italian legal terminology
```

<!--
# ☁️ Improved Tree Generation with PageIndex OCR

This repo is designed for generating PageIndex tree structure for simple PDFs, but many real-world use cases involve complex PDFs that are hard to parse by classic Python tools. However, extracting high-quality text from PDF documents remains a non-trivial challenge. Most OCR tools only extract page-level content, losing the broader document context and hierarchy.

To address this, we introduced PageIndex OCR — the first long-context OCR model designed to preserve the global structure of documents. PageIndex OCR significantly outperforms other leading OCR tools, such as those from Mistral and Contextual AI, in recognizing true hierarchy and semantic relationships across document pages.

- Experience next-level OCR quality with PageIndex OCR at our [Dashboard](https://dash.pageindex.ai/).
- Integrate PageIndex OCR seamlessly into your stack via our [API](https://docs.pageindex.ai/quickstart).

<p align="center">
  <img src="https://github.com/user-attachments/assets/eb35d8ae-865c-4e60-a33b-ebbd00c41732" width="80%">
</p>
-->

---

# 📈 Case Study: PageIndex Leads Finance QA Benchmark

[Mafin 2.5](https://vectify.ai/mafin) is a reasoning-based RAG system for financial document analysis, powered by **PageIndex**. It achieved a state-of-the-art [**98.7% accuracy**](https://vectify.ai/blog/Mafin2.5) on the [FinanceBench](https://arxiv.org/abs/2311.11944) benchmark, significantly outperforming traditional vector-based RAG systems.

PageIndex's hierarchical indexing and reasoning-driven retrieval enable precise navigation and extraction of relevant context from complex financial reports, such as SEC filings and earnings disclosures.

Explore the full [benchmark results](https://github.com/VectifyAI/Mafin2.5-FinanceBench) and our [blog post](https://vectify.ai/blog/Mafin2.5) for detailed comparisons and performance metrics.

<div align="center">
  <a href="https://github.com/VectifyAI/Mafin2.5-FinanceBench">
    <img src="https://github.com/user-attachments/assets/571aa074-d803-43c7-80c4-a04254b782a3" width="70%">
  </a>
</div>

---

# 🧭 Resources

* 🧪 [Cookbooks](https://docs.pageindex.ai/cookbook/vectorless-rag-pageindex): hands-on, runnable examples and advanced use cases.
* 📖 [Tutorials](https://docs.pageindex.ai/doc-search): practical guides and strategies, including *Document Search* and *Tree Search*.
* 📝 [Blog](https://pageindex.ai/blog): technical articles, research insights, and product updates.
* 🔌 [MCP setup](https://pageindex.ai/mcp#quick-setup) & [API docs](https://docs.pageindex.ai/quickstart): integration details and configuration options.

---

# ⭐ Support Us
Please cite this work as:
```
Mingtian Zhang, Yu Tang and PageIndex Team,
"PageIndex: Next-Generation Vectorless, Reasoning-based RAG",
PageIndex Blog, Sep 2025.
```

Or use the BibTeX citation:

```
@article{zhang2025pageindex,
  author = {Mingtian Zhang and Yu Tang and PageIndex Team},
  title = {PageIndex: Next-Generation Vectorless, Reasoning-based RAG},
  journal = {PageIndex Blog},
  year = {2025},
  month = {September},
  note = {https://pageindex.ai/blog/pageindex-intro},
}
```

Leave us a star 🌟 if you like our project. Thank you!  

<p>
  <img src="https://github.com/user-attachments/assets/eae4ff38-48ae-4a7c-b19f-eab81201d794" width="80%">
</p>

### Connect with Us

[![Twitter](https://img.shields.io/badge/Twitter-000000?style=for-the-badge&logo=x&logoColor=white)](https://x.com/PageIndexAI)&nbsp;
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/company/vectify-ai/)&nbsp;
[![Discord](https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com/invite/VuXuf29EUj)&nbsp;
[![Contact Us](https://img.shields.io/badge/Contact_Us-3B82F6?style=for-the-badge&logo=envelope&logoColor=white)](https://ii2abc2jejf.typeform.com/to/tK3AXl8T)

---

© 2025 [Vectify AI](https://vectify.ai)
