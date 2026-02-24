"""Configuration loader for the LLM abstraction layer.

Reads the ``llm`` section from ``pageindex/config.yaml`` and returns a plain
dict suitable for constructing an :class:`~pageindex.llm.provider.LLMProvider`.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

# Sensible defaults matching the project's primary provider (Google AI Studio).
_DEFAULTS: dict = {
    "completion_model": "gemini/gemini-2.0-flash",
    "embedding_model": "gemini/gemini-embedding-001",
    "embedding_dimensions": 768,
    "temperature": 0,
    "tree_indexing_model": None,
    "num_retries": 10,
}

_CONFIG_PATH: Path = Path(__file__).parent.parent / "config.yaml"

# Bridge GOOGLE_API_KEY → GEMINI_API_KEY so LiteLLM's gemini/ provider works
# regardless of which env var the user sets.
if not os.environ.get("GEMINI_API_KEY") and os.environ.get("GOOGLE_API_KEY"):
    os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]


def load_llm_config(config_path: str | Path | None = None) -> dict:
    """Load LLM configuration from *config_path* (default: ``pageindex/config.yaml``).

    Extracts the ``llm`` section from the YAML file and fills in any missing
    keys from ``_DEFAULTS``.

    Parameters
    ----------
    config_path : str | Path | None
        Override for the config file location.  When ``None`` the file is
        resolved relative to the package directory.

    Returns
    -------
    dict
        Keys: ``completion_model``, ``embedding_model``,
        ``embedding_dimensions``, ``temperature``.
    """
    path = Path(config_path) if config_path is not None else _CONFIG_PATH

    llm_section: dict = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        llm_section = raw.get("llm", {}) or {}

    # Merge with defaults -- config values take precedence.
    return {**_DEFAULTS, **llm_section}
