# Phase 1: Schema and LLM Abstraction - Context

**Gathered:** 2026-02-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Supabase database schema for Italian legal documents (documents, chunks, document_trees tables), Italian legal metadata definitions with domain vocabulary, and provider-agnostic LLM abstraction layer using LiteLLM. This phase delivers the storage and inference foundation that all subsequent phases depend on.

</domain>

<decisions>
## Implementation Decisions

### Italian Legal Document Taxonomy
- **Document types (doc_type)**: Full legal corpus — sentenze, ordinanze, decreti, leggi, decreti legislativi, decreti legge, regolamenti, circolari, pareri, delibere, atti parlamentari, and any other document type encountered
- **Legal areas (legal_area)**: Granular sub-areas with nested taxonomy (e.g., diritto civile > obbligazioni, famiglia, successioni, reale; diritto penale > reati contro la persona, reati informatici, etc.)
- **Legal area multiplicity**: A document can have multiple legal areas (array field) — many documents span topics
- **Court levels (court_level)**: Court tier only, not individual courts — Cassazione, Corte d'Appello, Tribunale, Giudice di Pace, Corte Costituzionale, TAR, Consiglio di Stato, and other levels as encountered
- **Enum style**: Open text with documented conventions — no hardcoded enums. Standard values are documented but new values can be added freely without schema migrations. The LLM extractor uses the documented conventions as guidance.

### Complex Field Structure
- **Parties**: Structured JSONB objects with name and role — `[{name: 'Mario Rossi', role: 'ricorrente'}, {name: 'Luigi Bianchi', role: 'resistente'}]`. Roles include ricorrente, resistente, imputato, parte civile, etc.
- **Cross-references**: Structured JSONB with reference, source, and type — `[{ref: 'art. 2043', source: 'codice civile', type: 'legislation'}, {ref: '12345/2020', source: 'Cassazione', type: 'case_law'}]`. Types: legislation, case_law, regulation, EU law, etc.
- **JSONB additional_fields**: Overflow only — safety valve for rare document types. All common fields get dedicated columns. JSONB is not an experimental ground for testing new fields.
- **Legal area storage**: Array column (text[]) since documents can belong to multiple granular sub-areas

### Embedding Model Configuration
- **Default model**: Gemini text-embedding-004 (multilingual, supports Italian legal text)
- **Swappability**: Embedding model configurable via config, same as LLM provider — allows experimenting with different models without code changes
- **Vector dimensions**: Configurable via config (read from model settings), not hardcoded. Changing model means re-embedding the entire corpus.
- **Corpus scale**: Designed for 10K+ documents — HNSW index recommended from the start for scalable approximate nearest neighbor search
- **LLM abstraction**: LiteLLM as specified in requirements (FOUND-03)

### Claude's Discretion
- Exact Supabase table structure and column types (within the constraints above)
- Migration strategy and SQL implementation
- LiteLLM wrapper design and configuration file format
- HNSW index parameters (m, ef_construction) — optimize for the scale
- How to handle the tree JSON structure storage in document_trees table
- Read-only database role setup for query safety

</decisions>

<specifics>
## Specific Ideas

- The taxonomy should feel natural to Italian legal practitioners — use standard Italian legal terminology, not translated English equivalents
- Court levels use the Italian hierarchy (Giudice di Pace < Tribunale < Corte d'Appello < Cassazione for ordinary jurisdiction; TAR < Consiglio di Stato for administrative)
- Open conventions approach means the LLM metadata extractor in Phase 2 will reference a documented vocabulary file/config, not database constraints

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-schema-and-llm-abstraction*
*Context gathered: 2026-02-22*
