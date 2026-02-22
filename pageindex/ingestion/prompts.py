"""LLM prompt templates for Italian legal metadata extraction and description generation.

Provides:
- ``build_metadata_extraction_prompt(vocabulary)`` -- system prompt with vocabulary injection
- ``build_description_prompt()`` -- system prompt for one-sentence description
- ``METADATA_JSON_SCHEMA`` -- JSON schema dict for LiteLLM ``response_format``
- ``load_vocabulary()`` -- loads and caches ``legal_vocabulary.yaml``
"""

from __future__ import annotations

import yaml
from pathlib import Path

# ---------------------------------------------------------------------------
# Vocabulary loader (cached at module level)
# ---------------------------------------------------------------------------

_vocabulary_cache: dict | None = None


def load_vocabulary() -> dict:
    """Load the Italian legal vocabulary from ``pageindex/schema/legal_vocabulary.yaml``.

    The result is cached at module level so subsequent calls avoid disk I/O.

    Returns
    -------
    dict
        Parsed YAML content with keys: doc_types, legal_areas, court_levels,
        party_roles, cross_reference_types.
    """
    global _vocabulary_cache
    if _vocabulary_cache is not None:
        return _vocabulary_cache

    vocab_path = Path(__file__).resolve().parent.parent / "schema" / "legal_vocabulary.yaml"
    with open(vocab_path, "r", encoding="utf-8") as f:
        _vocabulary_cache = yaml.safe_load(f)
    return _vocabulary_cache


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def build_metadata_extraction_prompt(vocabulary: dict) -> str:
    """Build a system prompt for Italian legal metadata extraction.

    The prompt instructs the LLM to extract structured metadata fields and
    injects the full vocabulary dict so it uses consistent terminology.

    Parameters
    ----------
    vocabulary : dict
        The parsed legal_vocabulary.yaml content (doc_types, legal_areas,
        court_levels, party_roles, cross_reference_types).

    Returns
    -------
    str
        A system prompt string.
    """
    # Format vocabulary sections for inclusion in the prompt
    doc_types_text = _format_doc_types(vocabulary.get("doc_types", []))
    legal_areas_text = _format_legal_areas(vocabulary.get("legal_areas", {}))
    court_levels_text = _format_court_levels(vocabulary.get("court_levels", {}))
    party_roles_text = _format_party_roles(vocabulary.get("party_roles", []))
    xref_types_text = _format_xref_types(vocabulary.get("cross_reference_types", []))

    return f"""You are analyzing an Italian legal document. Extract structured metadata from the text provided.

Return a JSON object with the following fields:

- **doc_type** (string or null): The type of legal document. Use one of the standard values below when applicable, or null if undetermined.
- **date** (string or null): The document date in ISO 8601 format (YYYY-MM-DD). Return null if not found.
- **authority** (string or null): The issuing authority (e.g., court name, legislative body).
- **ecli** (string or null): The European Case Law Identifier, if present.
- **gu_number** (string or null): The Gazzetta Ufficiale number, if applicable.
- **legal_area** (array of strings): Legal areas covered by the document. Use standard values below.
- **parties** (array of objects): Parties involved, each with "name" (string) and "role" (string). Use standard role values below.
- **court_level** (string or null): The court level. Use standard values below when applicable.
- **cross_references** (array of objects): Legal cross-references found in the text, each with "ref" (string) and "type" (string). Use standard type values below.

Return null for any field whose value cannot be determined from the text. For array fields, return an empty array if no values are found.

---

## Standard Vocabulary

### Document Types (doc_type)
{doc_types_text}

### Legal Areas (legal_area)
{legal_areas_text}

### Court Levels (court_level)
{court_levels_text}

### Party Roles (parties[].role)
{party_roles_text}

### Cross-Reference Types (cross_references[].type)
{xref_types_text}
"""


def build_description_prompt() -> str:
    """Build a system prompt for one-sentence document description generation.

    Returns
    -------
    str
        A system prompt string.
    """
    return (
        "Generate a single, concise sentence that describes what this Italian legal "
        "document is about and what distinguishes it from other documents. Focus on "
        "the subject matter, parties involved, and legal outcome."
    )


# ---------------------------------------------------------------------------
# JSON schema for structured LLM output (LiteLLM response_format)
# ---------------------------------------------------------------------------

METADATA_JSON_SCHEMA: dict = {
    "type": "json_schema",
    "json_schema": {
        "name": "legal_metadata",
        "schema": {
            "type": "object",
            "properties": {
                "doc_type": {"type": ["string", "null"]},
                "date": {"type": ["string", "null"]},
                "authority": {"type": ["string", "null"]},
                "ecli": {"type": ["string", "null"]},
                "gu_number": {"type": ["string", "null"]},
                "legal_area": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "parties": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "role": {"type": "string"},
                        },
                        "required": ["name", "role"],
                        "additionalProperties": False,
                    },
                },
                "court_level": {"type": ["string", "null"]},
                "cross_references": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "ref": {"type": "string"},
                            "type": {"type": "string"},
                        },
                        "required": ["ref", "type"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": [
                "doc_type",
                "date",
                "authority",
                "ecli",
                "gu_number",
                "legal_area",
                "parties",
                "court_level",
                "cross_references",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },
}


# ---------------------------------------------------------------------------
# Internal helpers for vocabulary formatting
# ---------------------------------------------------------------------------


def _format_doc_types(doc_types: list[dict]) -> str:
    """Format the doc_types vocabulary section for prompt inclusion."""
    lines = []
    for dt in doc_types:
        lines.append(f"- **{dt['id']}**: {dt['descrizione']}")
    return "\n".join(lines) if lines else "(nessun tipo definito)"


def _format_legal_areas(legal_areas: dict) -> str:
    """Format the legal_areas vocabulary section for prompt inclusion."""
    lines = []
    for area_key, area_data in legal_areas.items():
        desc = area_data.get("descrizione", "")
        sub = area_data.get("sotto_aree", [])
        sub_text = ", ".join(sub) if sub else ""
        lines.append(f"- **{area_key}**: {desc}")
        if sub_text:
            lines.append(f"  Sotto-aree: {sub_text}")
    return "\n".join(lines) if lines else "(nessuna area definita)"


def _format_court_levels(court_levels: dict) -> str:
    """Format the court_levels vocabulary section for prompt inclusion."""
    lines = []
    for jurisdiction, levels in court_levels.items():
        lines.append(f"**{jurisdiction}:**")
        for lvl in levels:
            lines.append(f"  - {lvl['livello']} (ordine: {lvl['ordine']})")
    return "\n".join(lines) if lines else "(nessun livello definito)"


def _format_party_roles(party_roles: list[dict]) -> str:
    """Format the party_roles vocabulary section for prompt inclusion."""
    lines = []
    for role in party_roles:
        lines.append(f"- **{role['id']}**: {role['descrizione']}")
    return "\n".join(lines) if lines else "(nessun ruolo definito)"


def _format_xref_types(xref_types: list[dict]) -> str:
    """Format the cross_reference_types vocabulary section for prompt inclusion."""
    lines = []
    for xrt in xref_types:
        examples = ", ".join(xrt.get("esempi", []))
        lines.append(f"- **{xrt['id']}**: {xrt['descrizione']}")
        if examples:
            lines.append(f"  Esempi: {examples}")
    return "\n".join(lines) if lines else "(nessun tipo definito)"
