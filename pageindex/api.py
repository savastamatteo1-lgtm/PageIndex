"""Public API types for PageIndex.

Defines the pydantic-settings configuration model (:class:`PageIndexSettings`),
public return types (:class:`SearchResponse`, :class:`IngestionResult`,
:class:`DocumentInfo`), and their supporting nested models.

Usage::

    from pageindex.api import PageIndexSettings, SearchResponse, IngestionResult

    settings = PageIndexSettings(supabase={"url": "...", "key": "..."})
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


# ---------------------------------------------------------------------------
# Nested configuration sub-models (plain BaseModel, NOT BaseSettings)
# ---------------------------------------------------------------------------


class LLMSettings(BaseModel):
    """LLM provider configuration."""

    completion_model: str = "gemini/gemini-2.0-flash"
    embedding_model: str = "gemini/gemini-embedding-001"
    embedding_dimensions: int = 768
    temperature: float = 0


class SupabaseSettings(BaseModel):
    """Supabase connection settings.

    ``url`` and ``key`` are required with no defaults -- they must be
    provided via constructor kwargs, environment variables, or a
    combination of the two.

    Uses ``extra="ignore"`` so that the YAML ``url_env`` / ``key_env``
    helper fields are silently discarded (the actual values come from
    env vars or kwargs, never from the YAML indirection).
    """

    model_config = ConfigDict(extra="ignore")

    url: str
    key: str

    @field_validator("url", "key")
    @classmethod
    def _reject_empty(cls, v: str, info) -> str:
        if not v.strip():
            raise ValueError(
                f"{info.field_name} must not be empty -- provide a real value "
                "via constructor kwargs or environment variables"
            )
        return v


class IngestionSettings(BaseModel):
    """Ingestion pipeline tunables."""

    metadata_pages: int = 3
    chunk_max_tokens: int = 800
    chunk_overlap: float = 0.1
    max_workers: int = 1
    max_embedding_batch: int = 250


class RetrievalSettings(BaseModel):
    """Retrieval / fusion strategy tunables."""

    model_config = ConfigDict(extra="ignore")

    default_top_k: int = 10
    default_strategy: str = "auto"
    rrf_k: int = 60
    engine_weights: dict[str, float] = {
        "metadata": 1.0,
        "semantic": 1.0,
        "description": 1.0,
    }
    global_min_score: float = 0.01
    internal_fetch_multiplier: int = 2


# ---------------------------------------------------------------------------
# Top-level settings model
# ---------------------------------------------------------------------------


class PageIndexSettings(BaseSettings):
    """Layered configuration for PageIndex.

    Resolution priority (highest wins):
        1. Constructor kwargs
        2. Environment variables (``PAGEINDEX_`` prefix, ``__`` nested delimiter)
        3. YAML config file (``pageindex/config.yaml``)
        4. Field defaults

    For the most common env vars (Supabase connection), both the prefixed
    nested form (``PAGEINDEX_SUPABASE__URL``) and the standard flat form
    (``SUPABASE_URL``) are accepted.  The flat form is checked via a
    ``model_validator`` as a convenience fallback.
    """

    model_config = SettingsConfigDict(
        env_prefix="PAGEINDEX_",
        env_nested_delimiter="__",
        yaml_file=str(Path(__file__).parent / "config.yaml"),
        yaml_file_encoding="utf-8",
        extra="ignore",
    )

    supabase: SupabaseSettings
    llm: LLMSettings = LLMSettings()
    ingestion: IngestionSettings = IngestionSettings()
    retrieval: RetrievalSettings = RetrievalSettings()

    @model_validator(mode="before")
    @classmethod
    def _populate_supabase_from_env(cls, values: dict) -> dict:
        """Accept flat ``SUPABASE_URL`` / ``SUPABASE_KEY`` env vars.

        When the user has not provided supabase settings via init kwargs
        or ``PAGEINDEX_SUPABASE__*`` env vars, fall back to the standard
        ``SUPABASE_URL`` and ``SUPABASE_KEY`` environment variables that
        many Supabase tools expect.
        """
        # Only fill in if supabase is not already fully provided
        supabase = values.get("supabase")

        # Read flat env vars (ignore empty strings)
        env_url = os.environ.get("SUPABASE_URL", "").strip() or None
        env_key = os.environ.get("SUPABASE_KEY", "").strip() or None

        if isinstance(supabase, dict):
            # Partially provided -- fill missing keys from env
            if "url" not in supabase and env_url:
                supabase["url"] = env_url
            if "key" not in supabase and env_key:
                supabase["key"] = env_key
        elif supabase is None:
            # Not provided at all -- try flat env vars
            if env_url or env_key:
                sb: dict[str, str] = {}
                if env_url:
                    sb["url"] = env_url
                if env_key:
                    sb["key"] = env_key
                values["supabase"] = sb

        return values

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Set source priority: init kwargs > env vars > YAML file."""
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls),
        )
