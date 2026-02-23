# Milestones

## v1.0 Legal Retrieval (Shipped: 2026-02-23)

**Phases completed:** 7 phases, 17 plans
**Stats:** 87 commits, 33 files, 5,675 insertions, ~7,600 LOC (Python+SQL)
**Timeline:** 2 days (Feb 22-23, 2026)
**Git range:** d8dfc25..b7d0c8b
**Audit:** 19/19 requirements satisfied, 3 minor tech debt items accepted

**Delivered:** A Python library that accepts Italian legal queries and returns precise relevant sections from a 1000+ document corpus, combining metadata filtering, semantic search, and LLM-powered tree reasoning — all backed by Supabase/pgvector.

**Key accomplishments:**
1. Supabase schema with Italian legal metadata (10 fields + JSONB), pgvector embeddings, and 3 idempotent SQL migrations
2. 6-stage batch ingestion pipeline: PDF tree indexing → LLM metadata extraction → description generation → tree-aware chunking → embedding → Supabase storage
3. 4 independent retrieval engines with uniform result contract: metadata (LLM-to-JSON filters), semantic (DocScore aggregation), description (embedding similarity), tree search (async concurrent LLM reasoning)
4. Strategy orchestration with Reciprocal Rank Fusion, LLM query intent classification, and automatic strategy routing
5. Clean `PageIndex` class API with pydantic-settings layered configuration (kwargs > env > YAML > defaults)
6. Full config threading from constructor to all subsystems with flat-kwargs support and 7 tech debt items resolved

**Known tech debt (accepted):**
- Batch `ingest()` in pipeline.py doesn't forward `embed_batch_size` or `additional_fields` (only `PageIndex.ingest()` path wires them)
- `RetrievalSettings.default_strategy` has no effect on `PageIndex.search()` method signature
- `utils.py` google-genai SDK initialized at import time (pre-existing from before LiteLLM migration)

---

