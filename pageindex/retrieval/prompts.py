"""Prompt templates and JSON schema for metadata filter generation.

Provides:
- ``_FILTER_FIELDS`` -- single source of truth for filter field definitions
  shared between ``FILTER_JSON_SCHEMA`` and :func:`build_filter_system_prompt`
- ``FILTER_JSON_SCHEMA`` -- ``response_format`` dict for LiteLLM structured output
- ``build_filter_system_prompt()`` -- system prompt with Italian legal vocabulary injection
- ``build_retry_prompt()`` -- retry prompt with validation error feedback
"""

from __future__ import annotations

from pageindex.ingestion.prompts import load_vocabulary

# ---------------------------------------------------------------------------
# Single source of truth for filter fields (Pitfall 3 prevention)
# ---------------------------------------------------------------------------

_FILTER_FIELDS: list[dict] = [
    {
        "name": "doc_type",
        "json_type": ["string", "null"],
        "description": "Tipo di documento giuridico (es. sentenza, ordinanza, decreto, legge). "
        "Corrisponde alla colonna `doc_type` nella tabella documenti.",
    },
    {
        "name": "date_from",
        "json_type": ["string", "null"],
        "description": "Data iniziale del range (formato ISO YYYY-MM-DD). "
        "Filtra documenti con `date >= date_from`.",
    },
    {
        "name": "date_to",
        "json_type": ["string", "null"],
        "description": "Data finale del range (formato ISO YYYY-MM-DD). "
        "Filtra documenti con `date <= date_to`.",
    },
    {
        "name": "authority",
        "json_type": ["string", "null"],
        "description": "Autorita' emittente (es. Corte di Cassazione, Tribunale di Milano). "
        "Corrisponde alla colonna `authority`.",
    },
    {
        "name": "court_level",
        "json_type": ["string", "null"],
        "description": "Livello del tribunale (es. Cassazione, Corte d'Appello, Tribunale, TAR). "
        "Corrisponde alla colonna `court_level`.",
    },
    {
        "name": "legal_area",
        "json_type": ["array", "null"],
        "items": {"type": "string"},
        "description": "Aree giuridiche (es. diritto_civile, diritto_penale). "
        "Array di stringhe; usa piu' valori quando la query menziona piu' aree. "
        "Corrisponde alla colonna array `legal_area`.",
    },
    {
        "name": "ecli",
        "json_type": ["string", "null"],
        "description": "European Case Law Identifier (ECLI). "
        "Corrisponde alla colonna `ecli`.",
    },
    {
        "name": "parties",
        "json_type": ["array", "null"],
        "items": {"type": "string"},
        "description": "Nomi delle parti coinvolte. Array di stringhe con i nomi "
        "delle parti da cercare nel campo JSONB `parties`.",
    },
]
"""Field definitions shared by the JSON schema and the system prompt builder.

Each dict must have ``name``, ``json_type``, ``description``.  Array types may
also include ``items``.
"""

# ---------------------------------------------------------------------------
# JSON schema for LiteLLM response_format
# ---------------------------------------------------------------------------


def _build_json_schema_properties() -> dict:
    """Derive JSON schema ``properties`` from ``_FILTER_FIELDS``."""
    props: dict = {}
    for f in _FILTER_FIELDS:
        prop: dict = {"type": f["json_type"]}
        if "items" in f:
            prop["items"] = f["items"]
        props[f["name"]] = prop
    return props


FILTER_JSON_SCHEMA: dict = {
    "type": "json_schema",
    "json_schema": {
        "name": "metadata_filter",
        "schema": {
            "type": "object",
            "properties": _build_json_schema_properties(),
            "required": [f["name"] for f in _FILTER_FIELDS],
            "additionalProperties": False,
        },
        "strict": True,
    },
}
"""LiteLLM ``response_format`` dict for structured filter output.

All fields are **required** (so the LLM always produces the full schema) but
**nullable** (``["type", "null"]``).  The LLM sets fields to ``null`` when the
user query does not mention them.
"""

# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------


def _format_vocabulary_section(vocabulary: dict) -> str:
    """Format vocabulary into a readable prompt section."""
    sections: list[str] = []

    # Document types
    doc_types = vocabulary.get("doc_types", [])
    if doc_types:
        lines = ["### Tipi di documento (doc_type)"]
        for dt in doc_types:
            lines.append(f"- **{dt['id']}**: {dt['descrizione']}")
        sections.append("\n".join(lines))

    # Legal areas
    legal_areas = vocabulary.get("legal_areas", {})
    if legal_areas:
        lines = ["### Aree giuridiche (legal_area)"]
        for area_key, area_data in legal_areas.items():
            desc = area_data.get("descrizione", "")
            sub = area_data.get("sotto_aree", [])
            lines.append(f"- **{area_key}**: {desc}")
            if sub:
                lines.append(f"  Sotto-aree: {', '.join(sub)}")
        sections.append("\n".join(lines))

    # Court levels
    court_levels = vocabulary.get("court_levels", {})
    if court_levels:
        lines = ["### Livelli del tribunale (court_level)"]
        for jurisdiction, levels in court_levels.items():
            lines.append(f"**{jurisdiction}:**")
            for lvl in levels:
                lines.append(f"  - {lvl['livello']} (ordine: {lvl['ordine']})")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


def _format_field_descriptions() -> str:
    """Format filter field descriptions from ``_FILTER_FIELDS``."""
    lines: list[str] = []
    for f in _FILTER_FIELDS:
        lines.append(f"- **{f['name']}**: {f['description']}")
    return "\n".join(lines)


def build_filter_system_prompt() -> str:
    """Build the system prompt for metadata filter generation.

    Loads the Italian legal vocabulary from ``legal_vocabulary.yaml`` via
    :func:`~pageindex.ingestion.prompts.load_vocabulary` and injects the full
    metadata schema with column names, types, and example values.

    Returns
    -------
    str
        A system prompt instructing the LLM to produce a structured JSON
        filter object.
    """
    vocabulary = load_vocabulary()
    vocab_section = _format_vocabulary_section(vocabulary)
    field_descriptions = _format_field_descriptions()

    return f"""Sei un assistente specializzato nel diritto italiano. Il tuo compito e' tradurre una query in linguaggio naturale in un oggetto JSON di filtri strutturati per cercare documenti giuridici italiani.

## Campi del filtro

{field_descriptions}

## Regole

1. Imposta a `null` ogni campo che la query NON menziona esplicitamente o implicitamente.
2. Usa i termini italiani per `doc_type`, `authority`, `court_level` (corrispondenti al vocabolario sotto).
3. Usa il formato ISO (YYYY-MM-DD) per `date_from` e `date_to`. Se la query dice "dal 2020", usa `date_from: "2020-01-01"` e `date_to: null`.
4. Se la query menziona piu' aree giuridiche, inseriscile tutte come lista in `legal_area`.
5. Estrai i nomi delle parti nella lista `parties`.
6. Per `court_level` usa il nome del livello (es. "Cassazione", "Tribunale", "TAR"), non il nome completo dell'autorita'.

## Vocabolario giuridico di riferimento

{vocab_section}

Output ONLY the JSON object. Do not explain."""


# ---------------------------------------------------------------------------
# Retry prompt builder
# ---------------------------------------------------------------------------


def build_retry_prompt(query: str, previous_output: str, error: str) -> str:
    """Build a retry prompt after a validation failure.

    Parameters
    ----------
    query : str
        The original user query.
    previous_output : str
        The JSON string that failed validation.
    error : str
        The validation error message.

    Returns
    -------
    str
        A user message asking the LLM to fix its previous output.
    """
    return f"""La tua risposta precedente non ha superato la validazione.

Query originale: {query}

Tuo output precedente:
```json
{previous_output}
```

Errore di validazione: {error}

Correggi l'output rispettando lo schema JSON richiesto. Tutti i campi sono obbligatori (usa null per i campi non applicabili). Output ONLY the corrected JSON object."""


# ---------------------------------------------------------------------------
# Query intent classification
# ---------------------------------------------------------------------------

CLASSIFICATION_SYSTEM_PROMPT: str = """\
You are a query intent classifier for an Italian legal document retrieval system.

Classify the user's query into one of three categories:

1. **structured** -- The query primarily asks for documents matching specific structured criteria.
   Indicators: dates or date ranges, legal identifiers (ECLI, GU numbers, law numbers), \
court/authority names, document type keywords (sentenza, decreto, ordinanza, circolare, legge, \
regolamento, direttiva).

2. **conceptual** -- The query asks about a legal topic, concept, or principle without specifying \
structured identifiers.
   Indicators: abstract legal questions, topical queries, "what is...", "how does...", \
legal principle names, conceptual descriptions.

3. **mixed** -- The query combines structured identifiers WITH conceptual/topical elements.
   Example: "sentenze della Cassazione dal 2020 sulla responsabilita' medica"
   (has doc_type + court + date range + legal topic)

Rules:
- If the query has ANY structured indicator AND a conceptual element, classify as "mixed".
- If the query has ONLY structured indicators, classify as "structured".
- If the query has NO structured indicators, classify as "conceptual".
- List the specific structured indicators you detected.

Output ONLY the JSON object."""
"""System prompt for LLM query intent classification.

Instructs the LLM to classify queries as ``structured``, ``conceptual``, or
``mixed`` using explicit Italian legal indicator rules.
"""

CLASSIFICATION_SCHEMA: dict = {
    "type": "json_schema",
    "json_schema": {
        "name": "query_classification",
        "schema": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "enum": ["structured", "conceptual", "mixed"],
                },
                "reasoning": {"type": "string"},
                "structured_indicators": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["intent", "reasoning", "structured_indicators"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}
"""LiteLLM ``response_format`` dict for query classification structured output.

Follows the same convention as :data:`FILTER_JSON_SCHEMA` above.  Fields:
``intent`` (enum), ``reasoning`` (free text), ``structured_indicators`` (list).
"""
