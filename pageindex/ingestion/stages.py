"""Per-document pipeline stages for the ingestion pipeline.

Provides 6 sequential stages that transform a PDF into a fully indexed,
enriched, and embedded record in Supabase:

1. ``stage_tree_index``           -- build tree structure via page_index_main
2. ``stage_extract_metadata``     -- LLM-based Italian legal metadata extraction
3. ``stage_generate_description`` -- LLM-based one-sentence description
4. ``stage_chunk``                -- tree-aware recursive chunking
5. ``stage_embed``                -- batch embedding with token limit validation
6. ``stage_store``                -- persist everything to Supabase

Orchestrator: ``process_single_document`` runs all stages in sequence.
"""

from __future__ import annotations

import copy
import json
import logging
import os

import litellm
from tenacity import retry, stop_after_attempt, wait_random_exponential

from pageindex.ingestion.chunker import build_embedding_text, chunk_leaf_nodes
from pageindex.ingestion.models import DocumentPipeline
from pageindex.ingestion.prompts import (
    METADATA_JSON_SCHEMA,
    build_description_prompt,
    build_metadata_extraction_prompt,
    load_vocabulary,
)
from pageindex.llm.provider import LLMProvider
from pageindex.utils import ConfigLoader, get_leaf_nodes, get_text_of_pages

from pageindex.db.documents import insert_document, update_document
from pageindex.db.chunks import insert_chunks
from pageindex.db.trees import insert_tree

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stage 1: Tree Indexing
# ---------------------------------------------------------------------------


def stage_tree_index(pipeline: DocumentPipeline, config: dict) -> None:
    """Build the hierarchical tree structure for a PDF document.

    Calls ``page_index_main`` with forced options for node IDs, node text,
    and node summaries.  Stores the result in *pipeline.tree_json* and
    *pipeline.doc_name*.

    Parameters
    ----------
    pipeline : DocumentPipeline
        Mutable pipeline state.  Must have ``pdf_path`` set.
    config : dict
        Optional overrides for the tree-indexing config.  Keys must be valid
        ``config.yaml`` top-level keys (e.g. ``model``, ``max_page_num_each_node``).
    """
    from pageindex.page_index import page_index_main

    # Merge ingestion-specific overrides with caller-provided config
    ingestion_overrides = {
        "if_add_node_id": "yes",
        "if_add_node_text": "yes",
        "if_add_node_summary": "yes",
    }
    merged = {**config, **ingestion_overrides}

    opts = ConfigLoader().load(merged)
    result = page_index_main(pipeline.pdf_path, opt=opts)

    pipeline.tree_json = result["structure"]
    pipeline.doc_name = result["doc_name"]


# ---------------------------------------------------------------------------
# Stage 2: Metadata Extraction
# ---------------------------------------------------------------------------


@retry(wait=wait_random_exponential(min=1, max=30), stop=stop_after_attempt(3))
def _extract_metadata_llm(
    model: str,
    system_prompt: str,
    user_text: str,
) -> dict:
    """Call LiteLLM with structured JSON output for metadata extraction.

    Decorated with tenacity retry for transient failures.
    """
    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        response_format=METADATA_JSON_SCHEMA,
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)


def stage_extract_metadata(
    pipeline: DocumentPipeline,
    llm_provider: LLMProvider,
    metadata_pages: int = 3,
) -> None:
    """Extract Italian legal metadata from the first pages of the document.

    Uses structured JSON output via ``litellm.completion`` with
    ``response_format`` and the vocabulary-injected prompt.

    Parameters
    ----------
    pipeline : DocumentPipeline
        Must have ``pdf_path`` set.
    llm_provider : LLMProvider
        Used to resolve the completion model name.
    metadata_pages : int
        Number of pages from the start to use for extraction (default 3).
    """
    text = get_text_of_pages(pipeline.pdf_path, 1, metadata_pages, tag=False)

    vocabulary = load_vocabulary()
    system_prompt = build_metadata_extraction_prompt(vocabulary)

    metadata = _extract_metadata_llm(
        model=llm_provider.completion_model,
        system_prompt=system_prompt,
        user_text=text,
    )

    pipeline.metadata = metadata

    # Flag for review if critical fields are missing
    if metadata.get("doc_type") is None or metadata.get("date") is None or metadata.get("authority") is None:
        pipeline.needs_review = True


# ---------------------------------------------------------------------------
# Stage 3: Description Generation
# ---------------------------------------------------------------------------


@retry(wait=wait_random_exponential(min=1, max=30), stop=stop_after_attempt(3))
def _generate_description_llm(llm_provider: LLMProvider, system_prompt: str, user_text: str) -> str:
    """Call LLMProvider.complete() for description generation with retry."""
    return llm_provider.complete(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    )


def stage_generate_description(
    pipeline: DocumentPipeline,
    llm_provider: LLMProvider,
) -> None:
    """Generate a one-sentence description of the document.

    Builds a clean version of the tree (without ``text`` fields to save
    tokens) and passes it along with the system prompt to the LLM.

    Parameters
    ----------
    pipeline : DocumentPipeline
        Must have ``tree_json`` set (from stage 1).
    llm_provider : LLMProvider
        Used for the completion call.
    """
    # Build clean tree structure for the prompt (remove text fields)
    clean_tree = _strip_text_from_tree(pipeline.tree_json)

    system_prompt = build_description_prompt()
    user_text = json.dumps(clean_tree, ensure_ascii=False, indent=2)

    pipeline.description = _generate_description_llm(
        llm_provider=llm_provider,
        system_prompt=system_prompt,
        user_text=user_text,
    )


# ---------------------------------------------------------------------------
# Stage 4: Chunking
# ---------------------------------------------------------------------------


def stage_chunk(
    pipeline: DocumentPipeline,
    llm_provider: LLMProvider,
    max_tokens: int = 800,
    overlap_ratio: float = 0.1,
) -> None:
    """Chunk the document tree into embeddable pieces.

    Uses tree-aware recursive chunking that respects leaf node boundaries.

    Parameters
    ----------
    pipeline : DocumentPipeline
        Must have ``tree_json`` and ``pdf_path`` set.
    llm_provider : LLMProvider
        Provides ``count_tokens`` for accurate token counting.
    max_tokens : int
        Maximum tokens per chunk (default 800).
    overlap_ratio : float
        Overlap fraction between consecutive sub-chunks (default 0.1).
    """
    leaf_nodes = get_leaf_nodes(pipeline.tree_json)

    pipeline.chunks = chunk_leaf_nodes(
        leaf_nodes=leaf_nodes,
        page_list_or_pdf_path=pipeline.pdf_path,
        tree_json=pipeline.tree_json,
        max_tokens=max_tokens,
        overlap_ratio=overlap_ratio,
        count_tokens_fn=llm_provider.count_tokens,
    )


# ---------------------------------------------------------------------------
# Stage 5: Embedding
# ---------------------------------------------------------------------------

# Gemini embedding API limits
_EMBED_BATCH_SIZE = 250
_EMBED_MAX_TOKENS = 2048


@retry(wait=wait_random_exponential(min=1, max=30), stop=stop_after_attempt(3))
def _embed_batch(llm_provider: LLMProvider, texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts with retry."""
    return llm_provider.embed(texts)


def stage_embed(
    pipeline: DocumentPipeline,
    llm_provider: LLMProvider,
) -> None:
    """Generate embeddings for all chunks.

    Builds contextual embedding text (metadata prefix + tree path + content)
    for each chunk, validates token limits, and embeds in batches of 250.

    Parameters
    ----------
    pipeline : DocumentPipeline
        Must have ``chunks``, ``metadata``, ``doc_name``, and ``description`` set.
    llm_provider : LLMProvider
        Provides ``embed()`` and ``count_tokens()`` methods.
    """
    # Build combined metadata dict for embedding text builder
    combined_metadata = {
        "doc_name": pipeline.doc_name,
        "doc_description": pipeline.description or "",
    }
    if pipeline.metadata:
        combined_metadata.update({
            "doc_type": pipeline.metadata.get("doc_type", ""),
            "date": pipeline.metadata.get("date", ""),
            "authority": pipeline.metadata.get("authority", ""),
            "legal_area": pipeline.metadata.get("legal_area", []),
            "ecli": pipeline.metadata.get("ecli", ""),
        })

    # Build embedding texts with token limit validation
    embedding_texts: list[str] = []
    for chunk in pipeline.chunks:
        embed_text = build_embedding_text(chunk, combined_metadata)

        # Validate token limit -- truncate chunk content if necessary
        token_count = llm_provider.count_tokens(embed_text)
        if token_count > _EMBED_MAX_TOKENS:
            # Calculate how many tokens to trim from chunk content
            overhead = token_count - _EMBED_MAX_TOKENS
            # Rebuild with truncated content
            words = chunk.content.split()
            while words and llm_provider.count_tokens(
                build_embedding_text(
                    type(chunk)(
                        content=" ".join(words),
                        node_id=chunk.node_id,
                        tree_path=chunk.tree_path,
                        metadata=chunk.metadata,
                    ),
                    combined_metadata,
                )
            ) > _EMBED_MAX_TOKENS:
                # Remove words from the end
                words = words[: len(words) - max(1, overhead // 4)]
                overhead = llm_provider.count_tokens(
                    build_embedding_text(
                        type(chunk)(
                            content=" ".join(words),
                            node_id=chunk.node_id,
                            tree_path=chunk.tree_path,
                            metadata=chunk.metadata,
                        ),
                        combined_metadata,
                    )
                ) - _EMBED_MAX_TOKENS
            embed_text = build_embedding_text(
                type(chunk)(
                    content=" ".join(words),
                    node_id=chunk.node_id,
                    tree_path=chunk.tree_path,
                    metadata=chunk.metadata,
                ),
                combined_metadata,
            )

        embedding_texts.append(embed_text)

    # Batch embed (Gemini API limit: 250 texts per call)
    all_embeddings: list[list[float]] = []
    for i in range(0, len(embedding_texts), _EMBED_BATCH_SIZE):
        batch = embedding_texts[i : i + _EMBED_BATCH_SIZE]
        batch_embeddings = _embed_batch(llm_provider, batch)
        all_embeddings.extend(batch_embeddings)

    pipeline.embeddings = all_embeddings


# ---------------------------------------------------------------------------
# Stage 6: Storage
# ---------------------------------------------------------------------------


def stage_store(pipeline: DocumentPipeline) -> None:
    """Persist the fully processed document to Supabase.

    Updates the document row with metadata and description, inserts the
    tree (with text fields stripped), inserts all chunks with embeddings,
    and marks the document as complete.

    Parameters
    ----------
    pipeline : DocumentPipeline
        Must have all fields populated from stages 1-5.
    """
    # Update document with metadata and description
    update_fields: dict = {}
    if pipeline.metadata:
        for key in ("doc_type", "date", "authority", "ecli", "gu_number",
                     "legal_area", "parties", "court_level", "cross_references"):
            if pipeline.metadata.get(key) is not None:
                update_fields[key] = pipeline.metadata[key]
    if pipeline.description:
        update_fields["doc_description"] = pipeline.description
    if pipeline.needs_review:
        update_fields["needs_review"] = True

    if update_fields:
        update_document(pipeline.doc_id, update_fields)

    # Store tree (strip text fields to save DB space)
    stripped_tree = _strip_text_from_tree(pipeline.tree_json)
    insert_tree(pipeline.doc_id, stripped_tree)

    # Store chunks with embeddings
    chunk_dicts: list[dict] = []
    for idx, chunk in enumerate(pipeline.chunks):
        chunk_dict: dict = {
            "doc_id": pipeline.doc_id,
            "content": chunk.content,
            "node_id": chunk.node_id,
            "metadata": {
                "tree_path": chunk.tree_path,
                **chunk.metadata,
            },
        }
        if idx < len(pipeline.embeddings):
            chunk_dict["embedding"] = pipeline.embeddings[idx]
        chunk_dicts.append(chunk_dict)

    if chunk_dicts:
        insert_chunks(chunk_dicts)

    # Mark document as complete
    update_document(pipeline.doc_id, {"ingestion_status": "complete"})


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def process_single_document(
    pdf_path: str,
    llm_provider: LLMProvider,
    config: dict | None = None,
    metadata_pages: int = 3,
    chunk_max_tokens: int = 800,
    chunk_overlap: float = 0.1,
) -> DocumentPipeline:
    """Process a single PDF through all 6 pipeline stages.

    Creates a ``DocumentPipeline``, inserts the document record with
    ``status=processing``, runs stages 1-6 in sequence, and returns
    the completed pipeline.

    Exceptions are NOT caught here -- the batch orchestrator (Plan 03)
    handles rollback.

    Parameters
    ----------
    pdf_path : str
        Absolute path to the source PDF file.
    llm_provider : LLMProvider
        LLM provider for completion, embedding, and token counting.
    config : dict, optional
        Optional overrides for tree-indexing config.  Keys must be valid
        ``config.yaml`` top-level keys.
    metadata_pages : int
        Number of pages to scan for metadata extraction (default 3).
    chunk_max_tokens : int
        Maximum tokens per chunk (default 800).
    chunk_overlap : float
        Overlap ratio between consecutive sub-chunks (default 0.1).

    Returns
    -------
    DocumentPipeline
        The fully processed pipeline with all fields populated.
    """
    if config is None:
        config = {}

    pipeline = DocumentPipeline(
        pdf_path=pdf_path,
        doc_name=os.path.basename(pdf_path),
    )

    # Insert document record with status=processing
    doc_row = insert_document(pipeline.doc_name, {"ingestion_status": "processing"})
    pipeline.doc_id = doc_row["doc_id"]

    # Stage 1: Tree indexing
    stage_tree_index(pipeline, config)

    # Stage 2: Metadata extraction
    stage_extract_metadata(pipeline, llm_provider, metadata_pages=metadata_pages)

    # Stage 3: Description generation
    stage_generate_description(pipeline, llm_provider)

    # Stage 4: Chunking
    stage_chunk(pipeline, llm_provider, max_tokens=chunk_max_tokens, overlap_ratio=chunk_overlap)

    # Stage 5: Embedding
    stage_embed(pipeline, llm_provider)

    # Stage 6: Storage
    stage_store(pipeline)

    return pipeline


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _strip_text_from_tree(tree_json: dict | list) -> dict | list:
    """Deep-copy the tree structure and remove ``text`` keys from all nodes.

    This reduces storage size in the database since the text content is
    already stored in the chunks table.

    Parameters
    ----------
    tree_json : dict or list
        The tree structure to strip.

    Returns
    -------
    dict or list
        A deep copy with all ``text`` keys removed.
    """
    cleaned = copy.deepcopy(tree_json)
    _remove_text_keys(cleaned)
    return cleaned


def _remove_text_keys(node: dict | list) -> None:
    """Recursively remove ``text`` keys from a tree structure in place."""
    if isinstance(node, dict):
        node.pop("text", None)
        for value in node.values():
            if isinstance(value, (dict, list)):
                _remove_text_keys(value)
    elif isinstance(node, list):
        for item in node:
            _remove_text_keys(item)
