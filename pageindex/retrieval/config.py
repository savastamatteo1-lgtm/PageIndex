"""Retrieval configuration with sensible defaults.

Centralises tunable retrieval parameters (thresholds, top-K, concurrency
limits) and exposes :func:`load_retrieval_config` to override them via the
``retrieval`` section of ``pageindex/config.yaml``.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Hardcoded defaults
# ---------------------------------------------------------------------------

DEFAULT_STRATEGY: str = "auto"
"""Default retrieval strategy when caller does not specify one."""

RRF_K: int = 60
"""RRF constant (dampening factor).  Higher values flatten rank differences."""

ENGINE_WEIGHTS: dict[str, float] = {"metadata": 1.0, "semantic": 1.0, "description": 1.0}
"""Per-engine weight multiplier for RRF fusion (default equal contribution)."""

GLOBAL_MIN_SCORE: float = 0.01
"""Minimum fused RRF score to include a result (RRF scores are small ~0.01-0.05)."""

INTERNAL_FETCH_MULTIPLIER: int = 2
"""Fetch this many times top_k from each engine before fusion."""

METADATA_FALLBACK_THRESHOLD: int = 3
"""Threshold for 'few results' in metadata-first fallback (triggers semantic supplement)."""

DEFAULT_TOP_K: int = 10
"""Default number of results returned per retrieval query (user-overridable)."""

DOCSCORE_MIN_THRESHOLD: float = 0.3
"""Minimum DocScore to include a document in semantic search results."""

METADATA_MIN_THRESHOLD: float = 0.25
"""Minimum metadata match fraction to include in results."""

DESCRIPTION_MIN_THRESHOLD: float = 0.6
"""Minimum description cosine similarity to include in results."""

CONFIDENCE_THRESHOLDS: dict[str, dict[str, float]] = {
    "metadata": {"high": 0.7, "medium": 0.4},
    "semantic": {"high": 0.6, "medium": 0.35},
    "description": {"high": 0.8, "medium": 0.6},
    "tree_search": {"high": 0.7, "medium": 0.4},
    "hybrid": {"high": 0.03, "medium": 0.015},
}
"""Per-engine score boundaries for confidence labels.

Scores ``>= high`` are labelled ``"high"``, ``>= medium`` are ``"medium"``,
everything else is ``"low"``.
"""

TREE_SEARCH_TOP_N: int = 5
"""Number of top documents to run tree search on."""

TREE_SEARCH_MAX_CONCURRENCY: int = 5
"""Async concurrency limit for parallel tree search."""

METADATA_MAX_RETRIES: int = 3
"""Total attempts for LLM filter generation (initial + up to 2 retries)."""

# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

_CONFIG_PATH: Path = Path(__file__).parent.parent / "config.yaml"

_RETRIEVAL_DEFAULTS: dict = {
    "default_top_k": DEFAULT_TOP_K,
    "default_strategy": DEFAULT_STRATEGY,
    "rrf_k": RRF_K,
    "engine_weights": ENGINE_WEIGHTS,
    "global_min_score": GLOBAL_MIN_SCORE,
    "internal_fetch_multiplier": INTERNAL_FETCH_MULTIPLIER,
    "metadata_fallback_threshold": METADATA_FALLBACK_THRESHOLD,
    "docscore_min_threshold": DOCSCORE_MIN_THRESHOLD,
    "metadata_min_threshold": METADATA_MIN_THRESHOLD,
    "description_min_threshold": DESCRIPTION_MIN_THRESHOLD,
    "confidence_thresholds": CONFIDENCE_THRESHOLDS,
    "tree_search_top_n": TREE_SEARCH_TOP_N,
    "tree_search_max_concurrency": TREE_SEARCH_MAX_CONCURRENCY,
    "metadata_max_retries": METADATA_MAX_RETRIES,
}


def load_retrieval_config(config_path: str | Path | None = None) -> dict:
    """Load retrieval configuration from *config_path*.

    Reads the ``retrieval`` section from the YAML config file and fills in
    any missing keys from the hardcoded defaults above.  Follows the same
    pattern as :func:`~pageindex.llm.config.load_llm_config` and
    :func:`~pageindex.ingestion.pipeline.load_ingestion_config`.

    Parameters
    ----------
    config_path : str | Path | None
        Override for the config file location.  When ``None`` the file is
        resolved relative to the package directory
        (``pageindex/config.yaml``).

    Returns
    -------
    dict
        All retrieval settings with defaults filled in.
    """
    path = Path(config_path) if config_path is not None else _CONFIG_PATH

    retrieval_section: dict = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        retrieval_section = raw.get("retrieval", {}) or {}

    # Merge with defaults -- config values take precedence.
    return {**_RETRIEVAL_DEFAULTS, **retrieval_section}
