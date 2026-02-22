"""Batch orchestration layer for the ingestion pipeline.

Provides the user-facing ``ingest()`` function that batch-processes a directory
of Italian legal PDFs with configurable concurrency, idempotent resume,
per-document rollback, and structured logging.

Usage::

    from pageindex.ingestion import ingest

    results = ingest("/path/to/pdfs", max_workers=4)
    print(results)
    # {"succeeded": 42, "failed": 2, "skipped": 5, "errors": [...]}
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from pageindex.db.documents import delete_document, get_document_by_name
from pageindex.ingestion.models import DocumentPipeline
from pageindex.ingestion.stages import process_single_document
from pageindex.llm.provider import LLMProvider, get_provider

logger = logging.getLogger("pageindex.ingestion")

# ---------------------------------------------------------------------------
# Configuration loader
# ---------------------------------------------------------------------------

_CONFIG_PATH: Path = Path(__file__).parent.parent / "config.yaml"

_INGESTION_DEFAULTS: dict = {
    "metadata_pages": 3,
    "chunk_max_tokens": 800,
    "chunk_overlap": 0.1,
    "max_workers": 1,
    "max_embedding_batch": 250,
}


def load_ingestion_config(config_path: str | Path | None = None) -> dict:
    """Load ingestion configuration from *config_path* (default: ``pageindex/config.yaml``).

    Extracts the ``ingestion`` section from the YAML file and fills in any
    missing keys from ``_INGESTION_DEFAULTS``.

    Parameters
    ----------
    config_path : str | Path | None
        Override for the config file location.  When ``None`` the file is
        resolved relative to the package directory.

    Returns
    -------
    dict
        Keys: ``metadata_pages``, ``chunk_max_tokens``, ``chunk_overlap``,
        ``max_workers``, ``max_embedding_batch``.
    """
    import yaml

    path = Path(config_path) if config_path is not None else _CONFIG_PATH

    ingestion_section: dict = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        ingestion_section = raw.get("ingestion", {}) or {}

    # Merge with defaults -- config values take precedence.
    return {**_INGESTION_DEFAULTS, **ingestion_section}


# ---------------------------------------------------------------------------
# Rollback wrapper
# ---------------------------------------------------------------------------


def _process_with_rollback(
    pdf_path: str,
    llm_provider: LLMProvider,
    config: dict,
) -> DocumentPipeline:
    """Process a single document and roll back on failure.

    Wraps :func:`process_single_document` with error handling that deletes
    any partially-created document from Supabase via
    :func:`delete_document` (which cascades to trees and chunks).

    Parameters
    ----------
    pdf_path : str
        Absolute path to the source PDF file.
    llm_provider : LLMProvider
        LLM provider instance for completion, embedding, and token counting.
    config : dict
        Pipeline configuration dict passed through to ``process_single_document``.

    Returns
    -------
    DocumentPipeline
        The fully processed pipeline on success.

    Raises
    ------
    Exception
        Re-raises the original exception after rollback so the batch handler
        can log the failure.
    """
    try:
        return process_single_document(pdf_path, llm_provider, config)
    except Exception:
        # Attempt rollback: if a document row was created, delete it
        doc_name = Path(pdf_path).name
        try:
            existing = get_document_by_name(doc_name)
            if existing is not None:
                doc_id = existing["doc_id"]
                delete_document(doc_id)
                logger.info("Rolled back document %s (doc_id=%s)", doc_name, doc_id)
        except Exception as rollback_err:
            logger.warning(
                "Rollback failed for %s: %s", doc_name, rollback_err
            )
        raise


# ---------------------------------------------------------------------------
# Batch orchestrator
# ---------------------------------------------------------------------------


def ingest(
    directory: str,
    max_workers: int | None = None,
    metadata_pages: int | None = None,
    chunk_max_tokens: int | None = None,
    chunk_overlap: float | None = None,
) -> dict:
    """Batch-process all PDFs in *directory* through the ingestion pipeline.

    This is the primary user-facing entry point for the ingestion pipeline.
    It discovers PDFs, skips already-ingested documents, processes the
    remaining with configurable concurrency via :class:`ThreadPoolExecutor`,
    rolls back failed documents, writes error details to a local JSONL file,
    and returns a structured summary.

    Parameters
    ----------
    directory : str
        Path to a directory containing PDF files to ingest.
    max_workers : int, optional
        Number of concurrent document-processing threads.  Defaults to the
        value in ``config.yaml`` (typically 1 = sequential).
    metadata_pages : int, optional
        Number of pages to scan for metadata extraction.  Defaults to the
        value in ``config.yaml`` (typically 3).
    chunk_max_tokens : int, optional
        Maximum tokens per chunk before splitting.  Defaults to the value
        in ``config.yaml`` (typically 800).
    chunk_overlap : float, optional
        Overlap ratio between consecutive sub-chunks.  Defaults to the
        value in ``config.yaml`` (typically 0.1).

    Returns
    -------
    dict
        ``{"succeeded": int, "failed": int, "skipped": int,
        "errors": [{"path": str, "error": str}]}``
    """
    # Load config defaults from config.yaml, then override with explicit args
    cfg = load_ingestion_config()
    effective_max_workers = max_workers if max_workers is not None else cfg["max_workers"]
    effective_metadata_pages = metadata_pages if metadata_pages is not None else cfg["metadata_pages"]
    effective_chunk_max_tokens = chunk_max_tokens if chunk_max_tokens is not None else cfg["chunk_max_tokens"]
    effective_chunk_overlap = chunk_overlap if chunk_overlap is not None else cfg["chunk_overlap"]

    # 1. Discover PDFs
    dir_path = Path(directory)
    all_pdfs = sorted(dir_path.glob("*.pdf"))
    logger.info("Found %d PDFs in %s", len(all_pdfs), directory)

    if not all_pdfs:
        return {"succeeded": 0, "failed": 0, "skipped": 0, "errors": []}

    # 2. Filter already-ingested
    to_process: list[Path] = []
    skipped = 0
    for pdf_path in all_pdfs:
        existing = get_document_by_name(pdf_path.name)
        if existing is not None and existing.get("ingestion_status") == "complete":
            skipped += 1
        else:
            to_process.append(pdf_path)

    total = len(to_process)
    logger.info("Processing %d, skipping %d already-ingested", total, skipped)

    if total == 0:
        return {"succeeded": 0, "failed": 0, "skipped": skipped, "errors": []}

    # 3. Initialize LLM provider
    provider = get_provider()

    # 4. Build config dict for pipeline stages
    pipeline_config: dict = {
        "metadata_pages": effective_metadata_pages,
        "chunk_max_tokens": effective_chunk_max_tokens,
        "chunk_overlap": effective_chunk_overlap,
        # PageIndex config overrides
        "if_add_node_id": "yes",
        "if_add_node_text": "yes",
        "if_add_node_summary": "yes",
    }

    # 5. Process with ThreadPoolExecutor
    results: dict = {
        "succeeded": 0,
        "failed": 0,
        "skipped": skipped,
        "errors": [],
    }

    with ThreadPoolExecutor(max_workers=effective_max_workers) as executor:
        futures = {
            executor.submit(
                _process_with_rollback, str(path), provider, pipeline_config
            ): path
            for path in to_process
        }
        for i, future in enumerate(as_completed(futures), 1):
            path = futures[future]
            try:
                future.result()
                results["succeeded"] += 1
                logger.info("[%d/%d] SUCCESS: %s", i, total, path.name)
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"path": str(path), "error": str(e)})
                logger.error("[%d/%d] FAILED: %s - %s", i, total, path.name, e)

    # 6. Log batch summary
    logger.info(
        "Batch complete: %d succeeded, %d failed, %d skipped",
        results["succeeded"],
        results["failed"],
        results["skipped"],
    )
    for err in results["errors"]:
        logger.error("  Failed: %s -- %s", err["path"], err["error"])

    # 7. Write local batch log file (dual tracking with DB ingestion_status)
    if results["errors"]:
        errors_path = dir_path / "ingest_errors.jsonl"
        with open(errors_path, "a", encoding="utf-8") as fh:
            for err in results["errors"]:
                line = json.dumps(
                    {
                        "path": err["path"],
                        "error": err["error"],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    ensure_ascii=False,
                )
                fh.write(line + "\n")
        logger.info("Error details written to %s", errors_path)

    # 8. Return results dict
    return results
