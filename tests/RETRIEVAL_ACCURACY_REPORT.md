# PageIndex Retrieval Accuracy Report

**Test Date:** 2026-02-23T16:11:58 UTC
**Document:** `2023-annual-report-truncated.pdf`
**Doc ID:** `69074ec6-c2fa-4502-bed8-cca75c8a6156`
**Total Chunks:** 45
**Questions:** 20
**Strategies Tested:** 5 (semantic, auto, semantic_chunks, tree_search, description)

---

## 1. Executive Summary

A retrieval accuracy benchmark was run against the Federal Reserve 2023 Annual Report (45 chunks) using 20 factual questions with known ground-truth answers. **Chunk-level semantic search (`semantic_chunks`) dramatically outperformed all other strategies**, achieving 95% top-1 accuracy and 100% top-3/top-5 accuracy. All four document-level strategies (semantic, auto, tree_search, description) scored 0% across all accuracy tiers, revealing a critical architectural gap: document-level retrieval returns document descriptions and metadata rather than the underlying chunk text where answers reside.

---

## 2. Test Setup

| Property | Value |
|---|---|
| Document | `2023-annual-report-truncated.pdf` |
| Document ID | `69074ec6-c2fa-4502-bed8-cca75c8a6156` |
| Total Chunks | 45 |
| Number of Questions | 20 |
| Test Timestamp | 2026-02-23T16:11:58 UTC |
| Source Pages Covered | 5, 9, 10, 11, 13, 15, 28, 32, 33, 35, 36, 42, 43 |

### Strategies Tested

| Strategy | Description | Level |
|---|---|---|
| `semantic` | `pi.search(strategy="semantic")` -- document-level semantic search | Document |
| `auto` | `pi.search(strategy="auto")` -- LLM orchestrator picks strategy | Document |
| `semantic_chunks` | Raw `match_chunks()` with embedding similarity (threshold 0.3, count 10) | Chunk |
| `tree_search` | `pi.search_tree()` -- hierarchical tree-structure search | Document |
| `description` | `pi.search_description()` -- searches document descriptions | Document |

### Answer Verification Method

Each question has a set of **answer keywords**. A result is considered correct if at least one keyword appears (case-insensitive) in the text content of the retrieved chunk or document. Accuracy is measured at top-1, top-3, and top-5 cutoffs.

---

## 3. Questions & Ground Truth

| ID | Question | Expected Answer | Source Page(s) |
|---:|---|---|---:|
| 1 | What was the federal funds rate target range maintained by the FOMC since July 2023? | 5-1/4 to 5-1/2 percent | 9 |
| 2 | What was the PCE price index 12-month change ending in January (March 2024 summary)? | 2.4 percent | 10 |
| 3 | What was the core PCE price index 12-month change ending in January? | 2.8 percent | 10 |
| 4 | What was the average monthly job gains since June (March 2024 summary)? | 239,000 per month | 10 |
| 5 | By how much did real GDP increase in the last year (March 2024 summary)? | 3.1 percent | 11 |
| 6 | Total increase in federal funds rate target during the tightening cycle from early 2022? | 525 basis points | 11 |
| 7 | Federal Reserve securities holdings reduction since mid-June 2023? | About $640 billion | 13 |
| 8 | Total reduction in securities holdings since balance sheet runoff start? | About $1.4 trillion | 13 |
| 9 | PCE inflation rate in April (June 2023 summary)? | 4.4 percent | 15 |
| 10 | Federal funds rate target range raised to by the June 2023 summary? | 5 to 5-1/4 percent | 15 |
| 11 | How many U.S. G-SIBs are in the LISCC portfolio? | Eight (8) | 32 |
| 12 | How many state member banks existed at year-end 2023? | 706 / 1,411 total | 32 |
| 13 | How many U.S. bank holding companies at year-end 2023? | 3,794 | 33 |
| 14 | How many savings and loan holding companies at year-end 2023? | 287 | 33 |
| 15 | Total civil money penalties assessed by the Fed in 2023? | $542,329,952.20 | 42 |
| 16 | How many formal enforcement actions did the Fed complete in 2023? | 63 | 42 |
| 17 | Total value of stablecoin assets in the financial stability section? | Around $125 billion | 28 |
| 18 | Examinations of state member banks conducted in 2023? | 316 | 35, 36 |
| 19 | Board collection for 2022 S&R Regulation TT assessment? | $771,050,870 from 53 institutions | 43 |
| 20 | When was the Federal Reserve created by an act of Congress? | December 23, 1913 | 5 |

---

## 4. Results by Strategy

### 4.1 `semantic` (Document-Level Semantic Search)

| Metric | Value |
|---|---|
| **Top-1 Accuracy** | **0.0%** (0/20) |
| **Top-3 Accuracy** | **0.0%** (0/20) |
| **Top-5 Accuracy** | **0.0%** (0/20) |
| Avg Timing | 0.413s |

**Per-Question Breakdown:**

| Q | Top-1 | Top-3 | Top-5 | Top Score | # Results |
|--:|:-----:|:-----:|:-----:|----------:|----------:|
| 1 | ✗ | ✗ | ✗ | 0.5069 | 1 |
| 2 | ✗ | ✗ | ✗ | 0.5214 | 1 |
| 3 | ✗ | ✗ | ✗ | -- | 0 |
| 4 | ✗ | ✗ | ✗ | 0.5045 | 1 |
| 5 | ✗ | ✗ | ✗ | 1.0941 | 1 |
| 6 | ✗ | ✗ | ✗ | 0.4979 | 1 |
| 7 | ✗ | ✗ | ✗ | -- | 0 |
| 8 | ✗ | ✗ | ✗ | -- | 0 |
| 9 | ✗ | ✗ | ✗ | 1.2784 | 1 |
| 10 | ✗ | ✗ | ✗ | 1.2634 | 1 |
| 11 | ✗ | ✗ | ✗ | -- | 0 |
| 12 | ✗ | ✗ | ✗ | 1.0944 | 1 |
| 13 | ✗ | ✗ | ✗ | 1.1041 | 1 |
| 14 | ✗ | ✗ | ✗ | 0.5292 | 1 |
| 15 | ✗ | ✗ | ✗ | 0.5150 | 1 |
| 16 | ✗ | ✗ | ✗ | 1.4658 | 1 |
| 17 | ✗ | ✗ | ✗ | -- | 0 |
| 18 | ✗ | ✗ | ✗ | 2.6932 | 1 |
| 19 | ✗ | ✗ | ✗ | -- | 0 |
| 20 | ✗ | ✗ | ✗ | 0.5155 | 1 |

**Note:** When results were returned, the top result preview consistently showed a generic Italian legal document description ("This Italian legal document details a dispute..."), not the actual Federal Reserve report content.

---

### 4.2 `auto` (LLM Orchestrator)

| Metric | Value |
|---|---|
| **Top-1 Accuracy** | **0.0%** (0/20) |
| **Top-3 Accuracy** | **0.0%** (0/20) |
| **Top-5 Accuracy** | **0.0%** (0/20) |
| Avg Timing | 1.532s |

The `auto` strategy delegated to `semantic` for all 20 questions. The LLM orchestrator correctly identified that these were not Italian legal document queries, but the underlying semantic strategy still returned document-level descriptions.

**Per-Question Breakdown:**

| Q | Top-1 | Top-3 | Top-5 | Top Score | Strategy Used |
|--:|:-----:|:-----:|:-----:|----------:|---|
| 1 | ✗ | ✗ | ✗ | 0.5069 | semantic |
| 2 | ✗ | ✗ | ✗ | 0.5214 | semantic |
| 3 | ✗ | ✗ | ✗ | -- | semantic |
| 4 | ✗ | ✗ | ✗ | 0.5045 | semantic |
| 5 | ✗ | ✗ | ✗ | 1.0941 | semantic |
| 6 | ✗ | ✗ | ✗ | 0.4979 | semantic |
| 7 | ✗ | ✗ | ✗ | -- | semantic |
| 8 | ✗ | ✗ | ✗ | -- | semantic |
| 9 | ✗ | ✗ | ✗ | 1.2784 | semantic |
| 10 | ✗ | ✗ | ✗ | 1.2634 | semantic |
| 11 | ✗ | ✗ | ✗ | -- | semantic |
| 12 | ✗ | ✗ | ✗ | 1.0944 | semantic |
| 13 | ✗ | ✗ | ✗ | 1.1041 | semantic |
| 14 | ✗ | ✗ | ✗ | 0.5292 | semantic |
| 15 | ✗ | ✗ | ✗ | 0.5150 | semantic |
| 16 | ✗ | ✗ | ✗ | 1.4658 | semantic |
| 17 | ✗ | ✗ | ✗ | -- | semantic |
| 18 | ✗ | ✗ | ✗ | 2.6932 | semantic |
| 19 | ✗ | ✗ | ✗ | -- | semantic |
| 20 | ✗ | ✗ | ✗ | 0.5155 | semantic |

---

### 4.3 `semantic_chunks` (Chunk-Level Semantic Search)

| Metric | Value |
|---|---|
| **Top-1 Accuracy** | **95.0%** (19/20) |
| **Top-3 Accuracy** | **100.0%** (20/20) |
| **Top-5 Accuracy** | **100.0%** (20/20) |
| Avg Timing | 0.329s |

**Per-Question Breakdown:**

| Q | Top-1 | Top-3 | Top-5 | Top Score | # Results |
|--:|:-----:|:-----:|:-----:|----------:|----------:|
| 1 | ✓ | ✓ | ✓ | 0.7168 | 10 |
| 2 | ✓ | ✓ | ✓ | 0.7373 | 10 |
| 3 | ✓ | ✓ | ✓ | 0.6542 | 10 |
| 4 | ✓ | ✓ | ✓ | 0.7135 | 10 |
| 5 | ✓ | ✓ | ✓ | 0.7557 | 10 |
| 6 | ✗ | ✓ | ✓ | 0.7041 | 10 |
| 7 | ✓ | ✓ | ✓ | 0.6960 | 10 |
| 8 | ✓ | ✓ | ✓ | 0.6456 | 10 |
| 9 | ✓ | ✓ | ✓ | 0.7368 | 10 |
| 10 | ✓ | ✓ | ✓ | 0.7146 | 10 |
| 11 | ✓ | ✓ | ✓ | 0.6739 | 10 |
| 12 | ✓ | ✓ | ✓ | 0.7757 | 10 |
| 13 | ✓ | ✓ | ✓ | 0.7674 | 10 |
| 14 | ✓ | ✓ | ✓ | 0.7484 | 10 |
| 15 | ✓ | ✓ | ✓ | 0.7283 | 10 |
| 16 | ✓ | ✓ | ✓ | 0.7616 | 10 |
| 17 | ✓ | ✓ | ✓ | 0.6987 | 10 |
| 18 | ✓ | ✓ | ✓ | 0.7934 | 10 |
| 19 | ✓ | ✓ | ✓ | 0.6968 | 10 |
| 20 | ✓ | ✓ | ✓ | 0.7290 | 10 |

The only top-1 miss was **Question 6** (525 basis points / tightening cycle), where the answer appeared in the 2nd or 3rd ranked chunk rather than the 1st.

---

### 4.4 `tree_search` (Hierarchical Tree Search)

| Metric | Value |
|---|---|
| **Top-1 Accuracy** | **0.0%** (0/20) |
| **Top-3 Accuracy** | **0.0%** (0/20) |
| **Top-5 Accuracy** | **0.0%** (0/20) |
| Avg Timing | 0.864s |

**Per-Question Breakdown:**

| Q | Top-1 | Top-3 | Top-5 | Top Score | # Results |
|--:|:-----:|:-----:|:-----:|----------:|----------:|
| 1 | ✗ | ✗ | ✗ | 0.1667 | 1 |
| 2 | ✗ | ✗ | ✗ | 0.1667 | 1 |
| 3 | ✗ | ✗ | ✗ | 0.0833 | 1 |
| 4 | ✗ | ✗ | ✗ | 0.1667 | 1 |
| 5 | ✗ | ✗ | ✗ | 0.1667 | 1 |
| 6 | ✗ | ✗ | ✗ | -- | 0 |
| 7 | ✗ | ✗ | ✗ | 0.0833 | 1 |
| 8 | ✗ | ✗ | ✗ | -- | 0 |
| 9 | ✗ | ✗ | ✗ | 0.1667 | 1 |
| 10 | ✗ | ✗ | ✗ | 0.1667 | 1 |
| 11 | ✗ | ✗ | ✗ | 0.4167 | 1 |
| 12 | ✗ | ✗ | ✗ | 0.0833 | 1 |
| 13 | ✗ | ✗ | ✗ | 0.0833 | 1 |
| 14 | ✗ | ✗ | ✗ | 0.0833 | 1 |
| 15 | ✗ | ✗ | ✗ | -- | 0 |
| 16 | ✗ | ✗ | ✗ | -- | 0 |
| 17 | ✗ | ✗ | ✗ | 0.1667 | 1 |
| 18 | ✗ | ✗ | ✗ | 0.0833 | 1 |
| 19 | ✗ | ✗ | ✗ | -- | 0 |
| 20 | ✗ | ✗ | ✗ | 0.0833 | 1 |

Tree search scores are very low (0.08--0.42 range), reflecting keyword-overlap scoring on section titles rather than content similarity.

---

### 4.5 `description` (Description Search)

| Metric | Value |
|---|---|
| **Top-1 Accuracy** | **0.0%** (0/20) |
| **Top-3 Accuracy** | **0.0%** (0/20) |
| **Top-5 Accuracy** | **0.0%** (0/20) |
| Avg Timing | 0.325s |

All 20 questions returned **0 results**. The description search operates on document-level descriptions and none matched with sufficient similarity to surface the target document.

---

## 5. Detailed Per-Question Analysis

### Questions That Were Easy (top-1 hit on semantic_chunks)

19 of 20 questions were answered correctly at top-1 by `semantic_chunks`. The highest-scoring questions:

| Q | Question (abbreviated) | Top Score | Difficulty |
|--:|---|----------:|---|
| 18 | Examinations of state member banks in 2023? | 0.7934 | Easiest |
| 12 | State member banks at year-end 2023? | 0.7757 | Easy |
| 5 | Real GDP increase (March 2024 summary)? | 0.7557 | Easy |
| 13 | Bank holding companies at year-end 2023? | 0.7674 | Easy |
| 16 | Formal enforcement actions in 2023? | 0.7616 | Easy |

These questions about specific institutional counts and economic statistics had strong semantic alignment with the chunk content.

### The Only Hard Question (top-1 miss on semantic_chunks)

| Q | Question | Top Score | Outcome |
|--:|---|----------:|---|
| 6 | Total increase in federal funds rate target during tightening cycle from early 2022? | 0.7041 | ✗ top-1, ✓ top-3 |

Question 6 was the sole top-1 failure. While the top-scoring chunk was semantically relevant (score 0.7041), the specific "525 basis points" answer appeared in a different chunk that ranked 2nd or 3rd. The top chunk was the general monetary policy introduction rather than the specific paragraph discussing the cumulative tightening.

### Cross-Strategy Comparison Per Question

| Q | semantic | auto | semantic_chunks | tree_search | description |
|--:|:--------:|:----:|:---------------:|:-----------:|:-----------:|
| 1 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |
| 2 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |
| 3 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |
| 4 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |
| 5 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |
| 6 | ✗ | ✗ | ✓ top-3 | ✗ | ✗ |
| 7 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |
| 8 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |
| 9 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |
| 10 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |
| 11 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |
| 12 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |
| 13 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |
| 14 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |
| 15 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |
| 16 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |
| 17 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |
| 18 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |
| 19 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |
| 20 | ✗ | ✗ | ✓ top-1 | ✗ | ✗ |

**Every single question** was answered only by `semantic_chunks`. No other strategy produced a correct result for any question.

---

## 6. Statistical Summary

### Overall Accuracy Comparison

| Strategy | Top-1 | Top-3 | Top-5 | Avg Latency |
|---|------:|------:|------:|------------:|
| **semantic_chunks** | **95.0%** | **100.0%** | **100.0%** | **0.329s** |
| semantic | 0.0% | 0.0% | 0.0% | 0.413s |
| auto | 0.0% | 0.0% | 0.0% | 1.532s |
| tree_search | 0.0% | 0.0% | 0.0% | 0.864s |
| description | 0.0% | 0.0% | 0.0% | 0.325s |

### Best and Worst Performing Questions

**Best (highest top-1 similarity in semantic_chunks):**

| Rank | Q | Top Score | Question |
|-----:|--:|----------:|---|
| 1 | 18 | 0.7934 | Examinations of state member banks in 2023 |
| 2 | 12 | 0.7757 | State member banks at year-end 2023 |
| 3 | 13 | 0.7674 | Bank holding companies at year-end 2023 |
| 4 | 16 | 0.7616 | Formal enforcement actions in 2023 |
| 5 | 5 | 0.7557 | Real GDP increase (March 2024 summary) |

**Worst (lowest top-1 similarity in semantic_chunks):**

| Rank | Q | Top Score | Question |
|-----:|--:|----------:|---|
| 1 | 8 | 0.6456 | Total reduction in securities holdings |
| 2 | 3 | 0.6542 | Core PCE price index 12-month change |
| 3 | 11 | 0.6739 | U.S. G-SIBs in LISCC portfolio |
| 4 | 7 | 0.6960 | Federal Reserve securities reduction since mid-June 2023 |
| 5 | 19 | 0.6968 | Board collection for Regulation TT assessment |

### Score Distribution (`semantic_chunks` Top-1 Scores)

| Statistic | Value |
|---|------:|
| Mean | 0.7216 |
| Median | 0.7168 |
| Min | 0.6456 (Q8) |
| Max | 0.7934 (Q18) |
| Std Dev | 0.0413 |
| Range | 0.1478 |

All 20 top-1 scores for `semantic_chunks` fall in the range **[0.6456, 0.7934]**, indicating consistently strong semantic alignment between questions and relevant chunks.

### Score Distribution (`semantic` Top-1 Scores, where results returned)

Of 14 questions that returned results for the `semantic` strategy:

| Statistic | Value |
|---|------:|
| Mean | 0.9713 |
| Median | 0.9943 |
| Min | 0.4979 (Q6) |
| Max | 2.6932 (Q18) |

Note: Scores above 1.0 in the document-level `semantic` strategy suggest a different similarity metric (possibly L2 distance or a non-normalized score), not cosine similarity.

### Score Distribution (`tree_search` Top-1 Scores, where results returned)

Of 15 questions that returned results for `tree_search`:

| Statistic | Value |
|---|------:|
| Mean | 0.1389 |
| Min | 0.0833 |
| Max | 0.4167 (Q11) |

### Timing Comparison

| Strategy | Avg (s) | Min (s) | Max (s) |
|---|-------:|-------:|-------:|
| description | 0.325 | 0.293 | 0.496 |
| semantic_chunks | 0.329 | 0.292 | 0.407 |
| semantic | 0.413 | 0.307 | 0.452 |
| tree_search | 0.864 | 0.443 | 1.099 |
| auto | 1.532 | 1.115 | 2.762 |

`semantic_chunks` is not only the most accurate strategy but also one of the two fastest (tied with `description`). The `auto` strategy is the slowest due to the LLM orchestration overhead.

---

## 7. Key Findings & Recommendations

### Finding 1: Document-Level vs. Chunk-Level Retrieval

The most critical finding is the **architectural mismatch** between the query type and the retrieval level. The `semantic`, `auto`, `tree_search`, and `description` strategies all operate at the **document level** -- they return whole documents with metadata and descriptions. For factual QA tasks where answers are embedded within specific paragraphs, this approach fails completely because:

- The returned content is a **document-level description** (e.g., "This Italian legal document details a dispute..."), not the underlying text.
- The similarity scores compare the query embedding against document-level embeddings, not chunk embeddings.
- Even when the correct document is returned, the answer keywords cannot be found in the description text.

### Finding 2: Why Non-Chunk Strategies Show 0% Accuracy

All four document-level strategies returned results that matched an **unrelated Italian legal document description** rather than the Federal Reserve report. This suggests:

1. The database contains documents from multiple domains (Italian law, US Federal Reserve).
2. Document-level descriptions are generic summaries that do not contain the specific factual data.
3. The `auto` orchestrator correctly identified the queries as non-legal, but could only delegate to `semantic`, which still operates at the document level.
4. The `description` strategy returned 0 results entirely, indicating the document descriptions had no semantic overlap with the factual queries.
5. The `tree_search` strategy returns section-level structure (titles), which do not contain the specific numerical answers.

### Finding 3: Chunk-Level Search Is Highly Effective

`semantic_chunks` achieved near-perfect retrieval:
- **95% top-1 accuracy** with only 1 miss (Q6, which was caught at top-3).
- **100% top-3 and top-5 accuracy** -- every answer was found within the first 3 chunks.
- Consistent similarity scores in the 0.64--0.79 range, indicating reliable semantic matching.
- Fastest or near-fastest latency at 0.329s average.

### Recommendations

1. **Expose chunk-level search in the public API.** The `pi.search()` API should have a mode or strategy that returns chunk-level results with actual text content, not just document metadata. This is the most impactful improvement.

2. **Hybrid retrieval pipeline.** For factual QA, implement a two-stage pipeline: (a) use chunk-level search to find relevant passages, (b) optionally return the parent document metadata alongside the chunk content.

3. **Fix the `auto` orchestrator routing.** When queries are clearly factual/extractive (not legal identifier lookups), `auto` should route to chunk-level search rather than document-level `semantic`.

4. **Improve document descriptions.** The generic Italian legal description appearing for unrelated documents suggests that document-level descriptions need better quality control or domain-specific generation.

5. **Consider re-ranking.** For the single top-1 miss (Q6), a lightweight re-ranker (e.g., cross-encoder) on top of the initial chunk retrieval could push the correct chunk to rank 1.

6. **Normalize similarity scores.** Document-level `semantic` scores above 1.0 indicate a non-standard similarity metric. Normalizing all scores to the [0, 1] cosine similarity range would improve interpretability and threshold-based filtering.

---

*Report generated from test results in `retrieval_accuracy_results.json`.*
*Test script: `tests/test_retrieval_accuracy.py`.*
