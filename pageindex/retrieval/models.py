"""Uniform result contract for all retrieval engines.

Every engine (metadata, semantic, description, tree_search) returns results
that extend :class:`RetrievalResult`.  Engine-specific subclasses add their
own fields on top of the common base.  :class:`MetadataFilter` represents the
structured JSON filter schema produced by the LLM for metadata queries.

All types use Python stdlib ``dataclasses`` (not pydantic) for lightweight,
dependency-free result containers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pageindex.retrieval.config import CONFIDENCE_THRESHOLDS


# ---------------------------------------------------------------------------
# Base result type
# ---------------------------------------------------------------------------


@dataclass
class RetrievalResult:
    """Base result returned by all retrieval engines.

    Attributes
    ----------
    doc_id : str
        Document UUID.
    score : float
        Engine-specific relevance score.
    metadata : dict
        Full legal metadata from the documents table.
    engine_name : str
        One of ``"metadata"``, ``"semantic"``, ``"description"``,
        ``"tree_search"``.
    confidence : str
        ``"high"``, ``"medium"``, or ``"low"`` -- derived from score
        thresholds in :mod:`pageindex.retrieval.config`.
    """

    doc_id: str
    score: float
    metadata: dict
    engine_name: str
    confidence: str


# ---------------------------------------------------------------------------
# Engine-specific result types
# ---------------------------------------------------------------------------


@dataclass
class MetadataResult(RetrievalResult):
    """Metadata engine result -- adds the parsed filter for transparency."""

    parsed_filters: dict = field(default_factory=dict)


@dataclass
class SemanticResult(RetrievalResult):
    """Semantic engine result -- adds contributing chunk count."""

    chunk_count: int = 0


@dataclass
class DescriptionResult(RetrievalResult):
    """Description engine result -- adds the matched description text."""

    doc_description: str = ""


@dataclass
class TreeSearchResult(RetrievalResult):
    """Tree search engine result -- adds matched section details.

    Each section dict has the shape::

        {"title": str, "start_page": int, "end_page": int, "node_id": str}
    """

    sections: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Metadata filter schema
# ---------------------------------------------------------------------------


@dataclass
class MetadataFilter:
    """Structured filter schema for metadata retrieval.

    Represents the flat JSON object that the LLM produces from a natural
    language query.  String fields use ``None`` to indicate *not specified*.
    """

    doc_type: str | None = None
    date_from: str | None = None  # ISO date string
    date_to: str | None = None  # ISO date string
    authority: str | None = None
    court_level: str | None = None
    legal_area: list[str] | None = None
    ecli: str | None = None
    parties: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return only non-``None`` fields as a plain dict."""
        return {k: v for k, v in self.__dict__.items() if v is not None}

    def field_count(self) -> int:
        """Return how many fields are non-``None`` (for metadata scoring)."""
        return sum(1 for v in self.__dict__.values() if v is not None)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MetadataFilter:
        """Parse a dict into a :class:`MetadataFilter`.

        Unknown keys are silently ignored.  Missing keys default to ``None``.
        """
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in known_fields and v is not None}
        return cls(**filtered)


# ---------------------------------------------------------------------------
# Confidence assignment helper
# ---------------------------------------------------------------------------


def assign_confidence(score: float, engine_name: str) -> str:
    """Map a numeric score to ``"high"`` / ``"medium"`` / ``"low"``.

    Uses per-engine thresholds from
    :data:`pageindex.retrieval.config.CONFIDENCE_THRESHOLDS`.  If the engine
    name is unknown, falls back to conservative default thresholds.
    """
    default_thresholds = {"high": 0.8, "medium": 0.5}
    thresholds = CONFIDENCE_THRESHOLDS.get(engine_name, default_thresholds)

    if score >= thresholds["high"]:
        return "high"
    if score >= thresholds["medium"]:
        return "medium"
    return "low"
