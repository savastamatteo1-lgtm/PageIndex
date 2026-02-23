"""Metadata retrieval engine.

Translates natural language queries into structured JSON filters via LLM,
validates them against :class:`~pageindex.retrieval.models.MetadataFilter`,
and executes them as Supabase PostgREST filter chains.  No raw SQL is
generated at any point.

Public API
----------
- :func:`search_metadata` -- main entry point (query -> list[MetadataResult])
- :func:`generate_filters` -- LLM filter generation with retry-on-validation-failure
- :func:`build_metadata_query` -- translate MetadataFilter to Supabase query
- :func:`score_metadata_results` -- score documents by filter field match fraction
"""

from __future__ import annotations

import json
import logging

import litellm
from tenacity import retry, stop_after_attempt, wait_random_exponential

from pageindex.db.client import get_client
from pageindex.llm.config import load_llm_config
from pageindex.retrieval.config import (
    DEFAULT_TOP_K,
    METADATA_MAX_RETRIES,
    METADATA_MIN_THRESHOLD,
    load_retrieval_config,
)
from pageindex.retrieval.models import MetadataFilter, MetadataResult, assign_confidence
from pageindex.retrieval.prompts import (
    FILTER_JSON_SCHEMA,
    build_filter_system_prompt,
    build_retry_prompt,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Filter generation
# ---------------------------------------------------------------------------


@retry(wait=wait_random_exponential(min=1, max=30), stop=stop_after_attempt(3))
def _llm_completion(model: str, messages: list[dict]) -> str:
    """Call LiteLLM completion with ``response_format`` and API-level retry.

    Network errors and rate limits are retried via tenacity (up to 3
    attempts with exponential backoff).  Validation failures are handled
    at the caller level (:func:`generate_filters`).
    """
    response = litellm.completion(
        model=model,
        messages=messages,
        response_format=FILTER_JSON_SCHEMA,
        temperature=0,
    )
    return response.choices[0].message.content


def generate_filters(query: str, model: str | None = None) -> MetadataFilter:
    """Generate structured metadata filters from a natural language query.

    Uses LiteLLM structured outputs to have the LLM produce a flat JSON
    filter object.  On validation failure, retries with feedback up to
    ``METADATA_MAX_RETRIES`` total attempts (per locked decision).

    Parameters
    ----------
    query : str
        Natural language search query (e.g. "sentenze della Corte di
        Cassazione dal 2020 in materia penale").
    model : str | None
        LLM model to use.  When ``None`` falls back to config.yaml ->
        hardcoded default.

    Returns
    -------
    MetadataFilter
        Validated filter object.

    Raises
    ------
    ValueError
        If all attempts fail validation.
    """
    if model is None:
        model = load_llm_config().get("completion_model", "gemini/gemini-2.0-flash")

    system_prompt = build_filter_system_prompt()
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]

    last_error: str = ""
    last_output: str = ""

    for attempt in range(1, METADATA_MAX_RETRIES + 1):
        logger.info("Filter generation attempt %d/%d", attempt, METADATA_MAX_RETRIES)

        raw = _llm_completion(model, messages)
        last_output = raw

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            last_error = f"Invalid JSON: {exc}"
            logger.warning("Attempt %d: %s", attempt, last_error)
            # Rebuild messages with retry prompt for next attempt
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": build_retry_prompt(query, raw, last_error)},
            ]
            continue

        try:
            filters = MetadataFilter.from_dict(parsed)
        except Exception as exc:
            last_error = f"Validation error: {exc}"
            logger.warning("Attempt %d: %s", attempt, last_error)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": build_retry_prompt(query, raw, last_error)},
            ]
            continue

        logger.info(
            "Filters generated: %d non-null fields", filters.field_count()
        )
        return filters

    raise ValueError(
        f"Filter generation failed after {METADATA_MAX_RETRIES} attempts. "
        f"Last error: {last_error}. Last output: {last_output}"
    )


# ---------------------------------------------------------------------------
# 2. Query builder
# ---------------------------------------------------------------------------


def build_metadata_query(
    filters: MetadataFilter, limit: int = DEFAULT_TOP_K
) -> list[dict]:
    """Translate a :class:`MetadataFilter` into a Supabase PostgREST query.

    Each non-``None`` field maps to a specific filter method:

    - String fields -> ``.ilike()`` for partial matching
    - Date fields -> ``.gte()`` / ``.lte()``
    - ``legal_area`` (array) -> ``.overlaps()`` for implicit OR
    - ``parties`` (JSONB) -> cast to text + ``.ilike()`` per party name

    Parameters
    ----------
    filters : MetadataFilter
        Validated filter object.
    limit : int
        Maximum number of results (default ``DEFAULT_TOP_K``).

    Returns
    -------
    list[dict]
        Raw document rows from Supabase.
    """
    client = get_client()
    query = client.table("documents").select("*")

    if filters.doc_type is not None:
        query = query.ilike("doc_type", f"%{filters.doc_type}%")

    if filters.date_from is not None:
        query = query.gte("date", filters.date_from)

    if filters.date_to is not None:
        query = query.lte("date", filters.date_to)

    if filters.authority is not None:
        query = query.ilike("authority", f"%{filters.authority}%")

    if filters.court_level is not None:
        query = query.ilike("court_level", f"%{filters.court_level}%")

    if filters.legal_area is not None:
        query = query.overlaps("legal_area", filters.legal_area)

    if filters.ecli is not None:
        query = query.ilike("ecli", f"%{filters.ecli}%")

    if filters.parties is not None:
        for party_name in filters.parties:
            query = query.filter("parties::text", "ilike", f"%{party_name}%")

    response = query.limit(limit).execute()
    return response.data


# ---------------------------------------------------------------------------
# 3. Result scoring
# ---------------------------------------------------------------------------


def score_metadata_results(
    results: list[dict], filters: MetadataFilter
) -> list[dict]:
    """Score documents by how many filter fields matched.

    For each document, checks each non-null filter field against the
    document's actual values.  The score is the fraction of non-null filter
    fields that matched (0.0 to 1.0).

    Parameters
    ----------
    results : list[dict]
        Raw document rows from Supabase.
    filters : MetadataFilter
        The filter object used for the query.

    Returns
    -------
    list[dict]
        Documents with an added ``score`` key, sorted by score descending.
    """
    total_filters = filters.field_count()
    if total_filters == 0:
        # No filters applied -- everything scores 0
        for doc in results:
            doc["score"] = 0.0
        return results

    for doc in results:
        match_count = 0

        # String fields: case-insensitive substring match (mirrors ilike)
        if filters.doc_type is not None and doc.get("doc_type"):
            if filters.doc_type.lower() in doc["doc_type"].lower():
                match_count += 1

        if filters.authority is not None and doc.get("authority"):
            if filters.authority.lower() in doc["authority"].lower():
                match_count += 1

        if filters.court_level is not None and doc.get("court_level"):
            if filters.court_level.lower() in doc["court_level"].lower():
                match_count += 1

        if filters.ecli is not None and doc.get("ecli"):
            if filters.ecli.lower() in doc["ecli"].lower():
                match_count += 1

        # Date fields: check if document date is within range
        doc_date = doc.get("date")
        if filters.date_from is not None and doc_date:
            if doc_date >= filters.date_from:
                match_count += 1

        if filters.date_to is not None and doc_date:
            if doc_date <= filters.date_to:
                match_count += 1

        # Array field (legal_area): check if any filter value appears
        if filters.legal_area is not None and doc.get("legal_area"):
            doc_areas = [a.lower() for a in doc["legal_area"]]
            if any(fa.lower() in doc_areas for fa in filters.legal_area):
                match_count += 1

        # Parties: check if party name appears in parties JSON text
        if filters.parties is not None and doc.get("parties"):
            parties_text = json.dumps(doc["parties"]).lower()
            if any(p.lower() in parties_text for p in filters.parties):
                match_count += 1

        doc["score"] = match_count / total_filters

    return sorted(results, key=lambda x: x["score"], reverse=True)


# ---------------------------------------------------------------------------
# 4. Main entry point
# ---------------------------------------------------------------------------


def search_metadata(
    query: str,
    limit: int | None = None,
    model: str | None = None,
) -> list[MetadataResult]:
    """Search documents by structured metadata filters.

    Main entry point combining filter generation, query execution, scoring,
    threshold filtering, and result conversion.

    Parameters
    ----------
    query : str
        Natural language search query.
    limit : int | None
        Maximum results.  When ``None`` uses ``DEFAULT_TOP_K`` from config.
    model : str | None
        LLM model for filter generation.  When ``None`` uses config.yaml
        default.

    Returns
    -------
    list[MetadataResult]
        Scored and filtered results with ``engine_name="metadata"`` and
        ``parsed_filters`` for caller transparency.  Empty list if no
        results match.
    """
    # Resolve config overrides
    cfg = load_retrieval_config()
    effective_limit = limit if limit is not None else cfg.get("default_top_k", DEFAULT_TOP_K)
    min_threshold = cfg.get("metadata_min_threshold", METADATA_MIN_THRESHOLD)

    # Step 1: Generate filters from query via LLM
    filters = generate_filters(query, model=model)
    logger.info("Generated filters: %s", filters.to_dict())

    # Step 2: Execute query via Supabase PostgREST
    raw_results = build_metadata_query(filters, limit=effective_limit)
    logger.info("Query returned %d documents", len(raw_results))

    if not raw_results:
        return []

    # Step 3: Score results by filter field match fraction
    scored_results = score_metadata_results(raw_results, filters)

    # Step 4: Filter below threshold
    scored_results = [r for r in scored_results if r["score"] >= min_threshold]

    if not scored_results:
        return []

    # Step 5: Convert to MetadataResult objects
    parsed_filters_dict = filters.to_dict()
    metadata_results: list[MetadataResult] = []

    for doc in scored_results:
        confidence = assign_confidence(doc["score"], "metadata")
        metadata_results.append(
            MetadataResult(
                doc_id=doc.get("doc_id", ""),
                score=doc["score"],
                metadata={
                    k: v
                    for k, v in doc.items()
                    if k not in ("doc_id", "score")
                },
                engine_name="metadata",
                confidence=confidence,
                parsed_filters=parsed_filters_dict,
            )
        )

    return metadata_results
