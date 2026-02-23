# Phase 3: Retrieval Engines - Context

**Gathered:** 2026-02-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Four independent retrieval strategies (metadata, semantic, tree search, description) that each accept a query and return ranked Italian legal documents or document sections. Each engine works independently against the ingested Supabase corpus. Strategy orchestration and combination logic belong to Phase 4.

</domain>

<decisions>
## Implementation Decisions

### SQL safety model (metadata engine)
- **No raw SQL generation.** The LLM fills a structured JSON filter schema via tool calling / structured outputs (supported across Gemini, OpenAI, Anthropic via LiteLLM)
- The JSON schema is flat: each field is equality, list (implicit OR / `IN`), or date range (`date_from`, `date_to`). Cross-field is implicit AND
- String fields use Supabase `.ilike()` for partial matching (not exact equality) since legal entity names vary in form
- Upgrade Supabase schema with `pg_trgm` indexes for fuzzy matching at the database layer — no vocabulary coupling at query time
- Full metadata schema injected into LLM prompt so it generates correct field names and types
- On validation failure: retry with feedback up to 2 retries (3 total attempts), then return error
- **Transparency:** Return the parsed filter JSON alongside matched documents so callers can see how the query was interpreted

### Result ranking & cutoffs
- Default top-K: 10 results (user-overridable per query)
- Minimum DocScore threshold: results below threshold are excluded even if top-K isn't filled
- Description search uses **embedding similarity** (embed query, compare against pre-embedded descriptions via cosine similarity) — fast, reuses existing infrastructure, no extra LLM call per query
- Empty results return an empty list + reason string explaining why (e.g., "No documents match the metadata filters" or "All scores below threshold")

### Tree search invocation
- **Auto-chained** after other engines return results — not standalone user-triggered
- Tree search runs on the **top 5 documents** from the preceding engine's results
- **Wraps existing PageIndex tree search implementation** (page_index.py search methods), adapted for multi-doc use
- **Parallel execution:** concurrent tree search across all 5 documents simultaneously (async)

### Engine result contract
- **Uniform base + engine-specific extras:** Common base type shared by all engines, with engine-specific fields added on top
- Base fields: `doc_id`, `score`, `metadata` (full legal metadata), `engine_name`, `confidence` (high/medium/low label derived from score threshold)
- Tree search adds: section titles, page ranges
- Metadata engine adds: parsed filter JSON
- **Metadata engine scoring:** score = number of filter fields that matched (a doc matching 4 of 5 filters scores higher than one matching 2 of 5)

### Claude's Discretion
- Exact DocScore threshold value (tunable default)
- Confidence label bucket boundaries
- Structured output JSON schema design details
- Async concurrency limits for parallel tree search

</decisions>

<specifics>
## Specific Ideas

- "The LLM shouldn't be writing SQL at all — it should be filling out a JSON form" via tool calling / structured outputs
- "Pass the LLM's output as-is, upgrade the Supabase schema to use pg_trgm indexes so the database handles misspellings automatically"
- "You can achieve 95% of the expressiveness of complex booleans by keeping the schema perfectly flat, but allowing Lists for equality fields"
- Keep an eye on ilike() query latency and migrate to `.text_search()` with a GIN index when the corpus gets too large

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-retrieval-engines*
*Context gathered: 2026-02-22*
