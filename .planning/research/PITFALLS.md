# Pitfalls Research

**Domain:** Multi-document legal retrieval system (Italian legal corpus, Supabase/pgvector, LLM-powered search)
**Researched:** 2026-02-22
**Confidence:** HIGH (verified via official docs, peer-reviewed research, production case studies)

## Critical Pitfalls

### Pitfall 1: LLM-to-SQL Injection via Unsanitized Query Translation

**What goes wrong:**
The metadata retrieval path translates natural-language legal queries into SQL via an LLM. The LLM output is treated as trusted code and executed directly against the database. An adversarial or malformed user query can cause the LLM to generate SQL containing DROP, UPDATE, DELETE, or data-exfiltration statements. Research shows injecting only 0.44% of poisoned data into a text-to-SQL training pipeline yields a 79.41% attack success rate. Even without poisoned models, prompt injection alone can cause LLMs to generate destructive SQL via LangChain-style middleware.

**Why it happens:**
Developers treat LLM output as safe because "it came from our system." But LLM-generated SQL is untrusted user input in a different form. The LLM is a text transformer, not a security boundary. Natural-language queries can embed SQL injection payloads that the LLM faithfully translates.

**How to avoid:**
1. **Read-only database role:** The database user for LLM-generated queries MUST have only SELECT privileges. No INSERT, UPDATE, DELETE, DROP, TRUNCATE, or DDL permissions. Create a dedicated `readonly_search` Postgres role.
2. **SQL allowlisting via AST parsing:** Parse every LLM-generated SQL query with a SQL parser (e.g., `sqlglot` or `pg_query` Python bindings) before execution. Verify: only SELECT statements, only allowed tables/columns, no subqueries with side effects, no function calls to dangerous Postgres functions.
3. **Parameterized RPC functions:** Instead of executing raw SQL, have the LLM produce structured filter parameters (JSON) that map to pre-defined Supabase RPC functions with parameterized queries. The LLM chooses WHICH filters, not HOW to query.
4. **SQL compilation gate:** Validate generated SQL against the database schema without executing it (EXPLAIN without ANALYZE) to catch syntax issues and unauthorized table references.

**Warning signs:**
- LLM output is passed directly to `execute()` or `.rpc()` without parsing
- The database connection uses the same credentials as the application admin
- No SQL allowlist or AST validation exists between LLM output and query execution
- Testing only uses benign queries (no adversarial prompt testing)

**Phase to address:**
Phase 1 (Supabase schema/infrastructure) -- create the read-only role. Phase 2 (metadata retrieval) -- implement the AST validation layer and parameterized RPC pattern before any LLM-to-SQL execution.

---

### Pitfall 2: Embedding Model Lock-In and Forced Full Reindex

**What goes wrong:**
You choose an embedding model (e.g., `text-embedding-ada-002` at 1536 dimensions), embed your entire 1000+ document corpus, build HNSW indexes, and ship. Six months later, a better multilingual model arrives, or OpenAI deprecates your model (as they did with first-generation embeddings). Every single embedding must be regenerated, the vector column dimensions must change, and the HNSW index must be fully rebuilt. For 1000+ legal documents chunked into 50K+ chunks, this is a multi-day, high-cost operation that blocks semantic search entirely during migration.

**Why it happens:**
Vector embeddings from different models are incompatible -- you cannot compare vectors from Model A with vectors from Model B. The column type in pgvector is `vector(N)` where N is fixed. Changing N requires dropping and recreating the column and index.

**How to avoid:**
1. **Choose a model with long-term viability:** Use BGE-M3 (open-source, self-hostable, 100+ languages including Italian, 1024 dimensions). Self-hosted models cannot be deprecated by a provider.
2. **Design for migration from day one:** Store the `embedding_model` name and `embedding_version` alongside every vector in the database. This lets you run old and new embeddings in parallel during migration.
3. **Use 768 or 1024 dimensions, not 1536:** Research confirms the accuracy curve flattens between 768-1024 dimensions. Moving from 768 to 1536 improves accuracy by approximately 2% while doubling storage and halving query throughput. For legal document retrieval at 1000-doc scale, 768-1024 dimensions is the sweet spot.
4. **Build a reindexing pipeline early:** The batch ingestion pipeline should support "re-embed only" mode from day one, so reindexing is an operational procedure rather than a crisis.

**Warning signs:**
- No `embedding_model` column in the vectors table
- Using a proprietary-only model (OpenAI, Cohere) without a fallback plan
- Choosing 1536+ dimensions without benchmarking against 768/1024
- No documented procedure for reindexing the corpus

**Phase to address:**
Phase 1 (schema design) -- include model metadata columns. Phase 2 (embedding pipeline) -- choose model and dimensions deliberately, build reindex capability.

---

### Pitfall 3: pgvector HNSW Index Memory Exhaustion on Supabase

**What goes wrong:**
HNSW indexes deliver 15.5x better throughput than IVFFlat at high recall (40.5 QPS vs 2.6 QPS), so developers naturally choose HNSW. But HNSW indexes must fit in RAM to perform well. On Supabase's free/Pro plans, RAM is limited (1-8 GB shared). With 50K chunks at 1024 dimensions, the HNSW index alone consumes approximately 200MB. But Postgres also needs shared_buffers for regular queries, connection overhead, and work_mem for sorts. When the HNSW index is evicted from memory, query latency spikes from milliseconds to seconds.

**Why it happens:**
Developers size their Supabase plan for data storage, not for index memory. HNSW's memory requirements are often invisible until production load reveals eviction patterns. Supabase's managed Postgres makes it hard to tune `shared_buffers` and `effective_cache_size` directly.

**How to avoid:**
1. **Calculate index memory requirements before choosing a plan:** Formula: `num_vectors * dimensions * 4 bytes * 1.5 (overhead)`. For 50K vectors at 1024 dims: ~300MB. Ensure your Supabase plan has at least 3x this in available RAM (for buffers + concurrent queries).
2. **Use IVFFlat for initial development, HNSW for production:** IVFFlat builds 32x faster and uses less memory. Use it during development and testing. Switch to HNSW when index performance matters and you have sized the infrastructure.
3. **Monitor with `pg_stat_user_indexes`:** Track index scans and cache hit ratios. If cache hits drop below 95%, the index is being evicted.
4. **Consider quantized vectors:** pgvector 0.7+ supports halfvec (half-precision) which halves index memory with minimal recall loss.

**Warning signs:**
- Semantic search latency is inconsistent (sometimes fast, sometimes slow)
- Supabase dashboard shows high disk I/O during vector queries
- Using Supabase Free tier with more than 10K vectors
- HNSW index created with default parameters (m=16, ef_construction=64) without benchmarking

**Phase to address:**
Phase 1 (infrastructure) -- calculate memory requirements and choose appropriate Supabase plan. Phase 2 (semantic search) -- benchmark IVFFlat vs HNSW with actual corpus size.

---

### Pitfall 4: Naive Retrieval Strategy Combination Produces Worse Results Than Single Strategies

**What goes wrong:**
You implement three retrieval paths (metadata SQL, semantic vector search, tree search) and combine their results with a simple union or naive score averaging. The combined results are worse than any single strategy alone. Metadata search returns precisely relevant documents (Italian Supreme Court decisions on employment law from 2020-2023) but with no relevance score. Semantic search returns vaguely related documents with cosine similarity scores. Combining them without normalization and proper weighting drowns precise metadata matches in a sea of semantically similar but legally irrelevant results.

**Why it happens:**
Scores from different retrieval methods are on incompatible scales. Cosine similarity produces 0-1 scores. Metadata filtering is binary (match/no-match). Tree search relevance is LLM-judged. Simply averaging or summing these produces meaningless composite scores. Reciprocal Rank Fusion (RRF) helps but assumes equal strategy quality, which is rarely true for legal queries where metadata precision dominates.

**How to avoid:**
1. **Keep retrieval paths independent until the reranking stage:** Do NOT merge result sets early. Run each strategy independently and collect separate ranked lists.
2. **Implement weighted Reciprocal Rank Fusion (wRRF):** Assign configurable weights to each strategy. For legal queries with rich metadata, metadata filtering should have higher weight. Expose weights as configuration so they can be tuned without code changes.
3. **Use metadata filtering as a pre-filter, not a parallel path:** For queries with clear metadata signals (date ranges, court names, legal area), filter FIRST, then run semantic search within the filtered set. This is both faster and more accurate than running both independently.
4. **Let the user select the strategy:** The PROJECT.md already specifies "user-selectable retrieval strategy per query" -- implement this from the start rather than trying to auto-detect.

**Warning signs:**
- Combined search returns obviously wrong documents that neither individual strategy would return alone
- Retrieval accuracy drops when you add a second strategy
- No normalization step exists between retrieval and ranking
- All strategies are weighted equally regardless of query type

**Phase to address:**
Phase 3 (retrieval combination) -- but the API design for independent strategy execution should be defined in Phase 1 (schema/architecture).

---

### Pitfall 5: Provider-Agnostic LLM Abstraction Becomes Provider-Lowest-Common-Denominator

**What goes wrong:**
You abstract away Gemini behind a unified LLM interface (via LiteLLM or a custom wrapper) so any provider works. But different providers have different capabilities: Gemini supports structured JSON output natively, OpenAI has function calling with different semantics, Anthropic has different context window sizes and tool use patterns. Your abstraction reduces to the intersection of all providers' features -- losing the specific capabilities your prompts rely on. One production report found that swapping models blindly dropped task accuracy by 22%.

**Why it happens:**
The existing codebase (visible in `utils.py`) is tightly coupled to Gemini's API: `types.Content`, `types.Part`, `types.GenerateContentConfig`, and Gemini-specific finish reasons. An abstraction layer must map these to different providers, but the mapping is lossy. Temperature=0 means different things to different providers. Token counting varies. Error types differ. The codebase already has `ChatGPT_API = Gemini_API` aliases, suggesting a previous migration where the interface was swapped but not truly abstracted.

**How to avoid:**
1. **Use LiteLLM as the abstraction layer, not a custom wrapper:** LiteLLM supports 100+ providers with OpenAI-compatible interface, handles retries/fallbacks/timeouts natively (see Context7 docs). It is the ecosystem standard.
2. **Define your own thin interface on top:** Create a `LLMClient` protocol/ABC with `complete(prompt, system, temperature, max_tokens) -> str` and `complete_json(prompt, schema) -> dict`. Map provider-specific features inside the implementation.
3. **Test every prompt with every target provider:** Prompt behavior varies significantly between models. The tree search prompts, metadata extraction prompts, and SQL generation prompts must each be tested with each target provider. Budget for prompt tuning per provider.
4. **Do NOT abstract embeddings and chat models behind the same interface:** They have fundamentally different APIs, error modes, and rate limits.
5. **Pin model versions:** `gemini-3.1-pro-preview` is a moving target. Pin to specific model versions (e.g., `gemini-2.0-flash-001`) and test before upgrading.

**Warning signs:**
- Abstraction layer has provider-specific `if/else` branches growing over time
- Prompts that work on Gemini produce garbage on OpenAI or vice versa
- No integration tests exist for non-primary providers
- Error handling catches generic `Exception` rather than provider-specific errors (as the current `utils.py` does)

**Phase to address:**
Phase 1 (infrastructure) -- define the LLM abstraction interface. Phase 2+ -- test each new capability with all target providers.

---

### Pitfall 6: Batch Ingestion Pipeline Fails Silently at Scale

**What goes wrong:**
Ingesting 1000+ legal PDFs involves: PDF parsing, tree index building (multiple LLM calls per document), metadata extraction (LLM call), chunking, embedding generation (API calls with rate limits), and Supabase upserts. At scale, individual failures are invisible. Document 437 fails during tree indexing due to a Gemini rate limit, document 612's embedding call times out, document 891 has a corrupt PDF. Without per-document status tracking, you think ingestion is complete but 15% of documents are missing or partially indexed.

**Why it happens:**
The current codebase uses `try/except` with retry loops (10 retries, 1-second sleep) that eventually return `"Error"` as a string. At single-document scale this is visible. At 1000-document scale, errors are buried in logs. There is no persistent record of which documents succeeded, which failed, and which are partially complete.

**How to avoid:**
1. **Implement a document ingestion status table:** `document_ingestion_status(doc_id, status, stage, error_message, started_at, completed_at)`. Stages: `pdf_parsed`, `tree_indexed`, `metadata_extracted`, `chunks_created`, `embeddings_generated`, `stored`. Status: `pending`, `in_progress`, `completed`, `failed`, `partial`.
2. **Make ingestion idempotent:** Use upserts (ON CONFLICT) for all database writes. A failed-and-retried document should not create duplicates.
3. **Implement exponential backoff with jitter for API calls:** The current 1-second flat sleep between retries will not handle Gemini's rate limits at scale. Use `2^attempt * (0.5 + random(0, 0.5))` with a maximum backoff of 60 seconds.
4. **Process documents in parallel with bounded concurrency:** Use `asyncio.Semaphore` to limit concurrent LLM API calls (e.g., 5-10 concurrent) rather than sequential processing or unbounded parallelism.
5. **Write embeddings in batches:** Direct batch SQL inserts to Supabase are 6-8x faster than individual upserts through the API (reduces from ~3-4 seconds per upsert to ~0.5 seconds per batch). Use batches of 100-500 chunks.

**Warning signs:**
- No way to answer "how many documents are fully indexed?" without querying multiple tables
- Rerunning ingestion creates duplicate entries
- Ingestion of 100+ documents takes longer than expected with no progress visibility
- API rate limit errors in logs with no corresponding retry success

**Phase to address:**
Phase 1 (schema) -- create the ingestion status table. Phase 2 (batch pipeline) -- implement idempotent ingestion with status tracking, batched writes, and bounded concurrency.

---

### Pitfall 7: Italian Legal Metadata Schema That Cannot Evolve

**What goes wrong:**
You design a rigid metadata schema for Italian legal documents (ECLI, court, date, legal_area, parties) and store it in a flat Postgres table. Six months later, you need to add cross-references between documents, distinguish between majority and dissenting opinions, track legislative history chains, or add EU directive transposition metadata. Every schema change requires an ALTER TABLE migration, and existing documents lack the new fields. With 1000+ documents already indexed, backfilling is expensive.

**Why it happens:**
Legal document metadata is inherently evolving. Italian legal taxonomy is deep (constitutional law, civil law, criminal law, administrative law -- each with dozens of sub-areas). Court hierarchies change (new specialized courts are created). Cross-reference types expand. A flat relational schema cannot anticipate all future metadata dimensions.

**How to avoid:**
1. **Use a hybrid schema: fixed columns for stable fields, JSONB for evolving fields:**
   - Fixed columns: `doc_id`, `doc_type`, `date`, `ecli`, `authority` (these are stable and queried frequently with indexes)
   - JSONB column: `metadata_extra` for everything else (legal_area, parties, cross_references, tags). JSONB supports GIN indexing for query performance.
2. **Use the expand-and-contract migration pattern:** When adding new required fields, first add the column as nullable, backfill existing rows, then add the NOT NULL constraint. This avoids locking issues on tables with many rows.
3. **Version your metadata schema:** Store a `schema_version` integer on each document. When the schema evolves, increment the version. Query logic can handle multiple versions.
4. **Design cross-references as a separate join table:** `document_references(source_doc_id, target_doc_id, reference_type, context)`. Do NOT embed references in the document's JSONB -- they need bidirectional querying.

**Warning signs:**
- Every new metadata field requires a database migration
- Existing documents have NULL values for fields that should be populated
- LLM-to-SQL queries break when metadata schema changes
- No way to add "tags" or "categories" without a code change

**Phase to address:**
Phase 1 (schema design) -- define the hybrid fixed+JSONB schema and the cross-references table. This is foundational and extremely expensive to change later.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcoding Gemini API calls (current state) | Works now, no abstraction overhead | Every new provider requires touching every call site; migration is already painful (OpenAI->Gemini aliases in utils.py prove this) | Never -- abstract now before adding more call sites |
| Storing embeddings and metadata in separate tables without foreign keys | Faster initial development | Orphaned embeddings after document deletion; inconsistent state during partial ingestion failures | Never -- use foreign keys with ON DELETE CASCADE |
| Using Supabase client library for all database operations | Simpler code, single dependency | PostgREST does not support pgvector operators natively, forcing RPC wrappers; batch inserts are slow through the API | Only for non-vector operations; use direct Postgres connection (psycopg2/asyncpg) for batch vector operations |
| Flat retry logic (current 10x retries with 1s sleep) | Simple to implement | Thundering herd on rate limits; wastes quota on permanent failures; no distinction between transient and permanent errors | Only for prototyping single-document flows |
| Skipping RLS on development Supabase instance | Faster iteration | Forgetting to enable RLS before production; queries that work in dev fail in production due to missing policies | Only if RLS is on the "must-do before deploy" checklist |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Supabase PostgREST + pgvector | Trying to use `.select()` with vector similarity operators -- PostgREST does not support them | Create Postgres functions (e.g., `match_documents`) and call them via `.rpc()` |
| Supabase Python client (supabase-py) | Assuming the Python client supports all PostgREST features -- it often lags behind the JS client | Verify feature support in supabase-py docs; use direct asyncpg/psycopg2 for unsupported operations |
| Gemini API rate limits during batch ingestion | Sending all 1000+ documents' LLM calls as fast as possible, hitting 429 errors | Implement bounded concurrency (asyncio.Semaphore), exponential backoff with jitter, and per-minute request tracking |
| Embedding API (Gemini or external) | Sending one chunk at a time for embedding | Batch embedding calls (most APIs support batch inputs of 50-100 texts per request), dramatically reducing latency and cost |
| pgvector index creation | Creating HNSW index on empty table then bulk-inserting vectors | For IVFFlat: insert data first, then create index (needs representative data for clustering). For HNSW: order doesn't matter, but building on large existing data takes 32x longer than IVFFlat |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Unindexed metadata columns used in LLM-generated WHERE clauses | Metadata SQL queries take 500ms+ instead of <10ms | Create B-tree indexes on all columns that appear in metadata filter queries (date, doc_type, authority, legal_area) | >500 documents with complex multi-column filters |
| Sequential document processing during batch ingestion | Ingesting 1000 documents takes 50+ hours (3 min/doc for tree indexing) | Use asyncio with bounded concurrency; process tree indexing, metadata extraction, and embedding in parallel per document | >50 documents |
| Embedding all chunks before any are queryable | Users cannot search until the entire corpus is embedded (hours/days) | Process and store documents incrementally; each completed document becomes immediately searchable | >200 documents with user-facing deadlines |
| Full document text stored in vector chunks table | Table bloat; vector similarity queries read unnecessary text columns off disk, polluting the buffer cache | Store chunk text in a separate table; the vectors table should contain only: id, doc_id, embedding, chunk_index. Join to text only when needed | >20K chunks (table exceeds shared_buffers) |
| Running EXPLAIN ANALYZE on LLM-generated SQL | EXPLAIN ANALYZE actually executes the query, including any destructive operations | Use EXPLAIN (without ANALYZE) for validation; only use EXPLAIN ANALYZE on confirmed-safe SELECT queries | Any LLM-generated SQL in production |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Using the Supabase `service_role` key in client-side or application code for LLM queries | Service role bypasses RLS entirely; LLM-generated SQL has unrestricted access to all data | Create a dedicated Postgres role with SELECT-only on specific tables; use a connection pooler (Supabase's Supavisor) with this role |
| Not enabling RLS on the documents and embeddings tables | Any client with the anon key can read/modify all legal documents | Enable RLS on every table; create policies for read access via authenticated users only |
| Logging full LLM-generated SQL queries with user context | SQL logs may contain sensitive legal query patterns; combined with document metadata, this reveals client legal strategies | Log query patterns and performance metrics, not full query text; implement log redaction |
| Storing API keys (Gemini, OpenAI, embedding provider) in config files or environment variables committed to git | Credential exposure via repository access | Use Supabase Vault for secrets in Edge Functions; use OS keychain or secret managers for application keys; add `.env` to `.gitignore` (already using `python-dotenv`) |

## "Looks Done But Isn't" Checklist

- [ ] **Semantic search:** Returns results but no relevance threshold is set -- verify that a `match_threshold` (e.g., 0.75) filters out low-quality matches rather than returning the top-K regardless of similarity
- [ ] **Metadata search:** LLM generates valid SQL but no guardrails exist -- verify AST parsing, read-only role, and table allowlisting are all in place
- [ ] **Batch ingestion:** All documents "processed" but no verification -- verify each document has: tree index, metadata record, AND at least one embedding chunk in the vectors table
- [ ] **Provider abstraction:** "Works with OpenAI too" but only tested with simple prompts -- verify that tree search prompts, metadata extraction prompts, and SQL generation prompts produce correct results with each provider
- [ ] **Combined retrieval:** Returns merged results but no evaluation -- verify that combined results are better than (or at least no worse than) the best single strategy on a test query set
- [ ] **HNSW index:** Created and queries work but performance not validated -- verify that the index fits in memory by checking `pg_stat_user_indexes` cache hit ratio >95%
- [ ] **Cross-references:** Documents reference each other by ECLI but references are not queryable -- verify that a `document_references` table exists with indexes, not just inline text mentions

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| LLM-to-SQL injection in production | HIGH | Revoke all write permissions immediately; audit query logs for destructive operations; restore from backup if data was modified; implement AST validation before re-enabling |
| Wrong embedding model choice (need to re-embed) | MEDIUM | Run new embeddings in parallel column/table; validate search quality against test set; atomic swap (rename tables) once validated; drop old embeddings |
| HNSW index won't fit in memory | LOW | Drop HNSW, create IVFFlat as stopgap; upgrade Supabase plan; recreate HNSW once memory is sufficient |
| Metadata schema too rigid | HIGH | Add JSONB `metadata_extra` column; migrate existing metadata into it; update all query generation prompts to use new schema; retest all LLM-to-SQL paths |
| Batch ingestion left partially complete | MEDIUM | Query ingestion status table for failed/partial documents; rerun ingestion for those documents only (requires idempotent pipeline); if no status table exists, compare document IDs in source vs database |
| Provider abstraction is leaky | MEDIUM | Audit all prompt templates for provider-specific assumptions; create integration test suite that runs every prompt against every provider; fix prompts one by one |
| Combined retrieval produces worse results | LOW | Disable combination, fall back to single-strategy mode; add per-strategy evaluation metrics; tune weights based on a labeled test set before re-enabling |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| LLM-to-SQL injection | Phase 1 (schema) + Phase 2 (metadata retrieval) | Run adversarial prompt test suite; verify database role has only SELECT; AST validation catches DROP/UPDATE/DELETE |
| Embedding model lock-in | Phase 1 (schema) + Phase 2 (embeddings) | `embedding_model` and `embedding_version` columns exist; reindex pipeline runs successfully on 10-doc test set |
| HNSW memory exhaustion | Phase 1 (infrastructure) + Phase 2 (semantic search) | `pg_stat_user_indexes` shows >95% cache hit ratio under load; query latency p99 < 500ms |
| Naive strategy combination | Phase 3 (retrieval combination) | Combined results evaluated against labeled test queries; no accuracy regression vs best single strategy |
| Provider abstraction pitfalls | Phase 1 (LLM abstraction) | Integration tests pass for at least 2 providers; each prompt template has provider-specific test cases |
| Silent batch ingestion failures | Phase 1 (schema) + Phase 2 (batch pipeline) | Ingestion status table accounts for all source documents; zero documents in `failed` status after full run; rerun produces no duplicates |
| Rigid metadata schema | Phase 1 (schema design) | JSONB `metadata_extra` column exists; adding a new metadata field requires zero database migrations |

## Sources

- [ToxicSQL: LLM Text-to-SQL Backdoor Attacks (ACM SIGMOD 2025)](https://arxiv.org/abs/2503.05445) - 0.44% poisoned data yields 79.41% attack success rate
- [Prompt-to-SQL Injection Attacks (ICSE 2025)](https://dl.acm.org/doi/10.1109/ICSE55347.2025.00007) - LangChain middleware vulnerability analysis
- [Text-to-SQL: A Privacy Nightmare (Feb 2026)](https://lotuslabs.medium.com/text-to-sql-a-privacy-nightmare-how-to-architect-secure-enterprise-grade-text-to-sql-256615d1b59f) - Multi-layer defense architecture
- [Supabase pgvector docs](https://supabase.com/docs/guides/database/extensions/pgvector) - PostgREST limitations, RPC function pattern
- [Supabase: Fewer dimensions are better](https://supabase.com/blog/fewer-dimensions-are-better-pgvector) - Dimension reduction evidence
- [Comprehensive Evaluation of Embeddings for English and Italian (BDCC 2025)](https://www.mdpi.com/2504-2289/9/5/141) - Italian-language embedding benchmarks
- [BGE-M3: Multi-Lingual Multi-Functionality Multi-Granularity Embeddings](https://arxiv.org/abs/2402.03216) - Top multilingual open-source model
- [Optimizing RAG with Hybrid Search & Reranking (Superlinked)](https://superlinked.com/vectorhub/articles/optimizing-rag-with-hybrid-search-reranking) - Strategy combination best practices
- [LiteLLM Official Docs](https://docs.litellm.ai/docs/) - Provider fallback and retry patterns (verified via Context7)
- [To Scale our RAG Agent (5,000 Files/hr)](https://www.theaiautomators.com/scale-rag-agent/) - Batch insert optimization benchmarks
- [pgvector HNSW vs IVFFlat Study](https://medium.com/@bavalpreetsinghh/pgvector-hnsw-vs-ivfflat-a-comprehensive-study-21ce0aaab931) - 15.5x throughput difference, 32x build time difference
- [Postgres Schema Changes Are Still a PITA (Xata)](https://xata.io/blog/postgres-schema-changes-pita) - ALTER TABLE locking and migration patterns
- [Supabase RLS with pgvector](https://supabase.com/docs/guides/ai/rag-with-permissions) - Row-level security for vector search
- [LiteLLM Context7 Docs](https://docs.litellm.ai/docs/proxy/reliability) - Fallback, retry, cooldown configuration

---
*Pitfalls research for: Italian legal multi-document retrieval (PageIndex Legal Retrieval)*
*Researched: 2026-02-22*
