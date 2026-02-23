"""Retrieval accuracy test for PageIndex.

Runs 15+ specific factual questions against all retrieval strategies
(semantic, auto, tree_search, description) using the Federal Reserve
2023 Annual Report document and evaluates whether the returned chunks
contain the expected answers.

Usage:
    python3 tests/test_retrieval_accuracy.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from pageindex.api import PageIndex

DOC_ID = "69074ec6-c2fa-4502-bed8-cca75c8a6156"
TOTAL_CHUNKS = 45
PDF_NAME = "2023-annual-report-truncated.pdf"

# ---------------------------------------------------------------------------
# Questions with ground-truth answers
# ---------------------------------------------------------------------------

QUESTIONS: list[dict] = [
    {
        "id": 1,
        "question": "What was the federal funds rate target range maintained by the FOMC since its July 2023 meeting?",
        "expected_answer": "5-1/4 to 5-1/2 percent",
        "source_pages": [9],
        "answer_keywords": ["5", "5-1/4", "5-1/2", "5.25", "5.5"],
    },
    {
        "id": 2,
        "question": "What was the PCE price index 12-month change ending in January, as reported in the March 2024 summary?",
        "expected_answer": "2.4 percent",
        "source_pages": [10],
        "answer_keywords": ["2.4", "percent", "PCE"],
    },
    {
        "id": 3,
        "question": "What was the core PCE price index 12-month change ending in January?",
        "expected_answer": "2.8 percent",
        "source_pages": [10],
        "answer_keywords": ["2.8", "percent", "core PCE"],
    },
    {
        "id": 4,
        "question": "What was the average monthly job gains since June according to the March 2024 summary?",
        "expected_answer": "239,000 per month",
        "source_pages": [10],
        "answer_keywords": ["239,000", "239000"],
    },
    {
        "id": 5,
        "question": "By how much did real GDP increase in the last year according to the March 2024 summary?",
        "expected_answer": "3.1 percent",
        "source_pages": [11],
        "answer_keywords": ["3.1", "percent", "GDP"],
    },
    {
        "id": 6,
        "question": "What was the total increase in the target range for the federal funds rate during the entire tightening cycle that began in early 2022?",
        "expected_answer": "525 basis points",
        "source_pages": [11],
        "answer_keywords": ["525", "basis points"],
    },
    {
        "id": 7,
        "question": "By how much did the Federal Reserve reduce its securities holdings since mid-June 2023?",
        "expected_answer": "About $640 billion",
        "source_pages": [13],
        "answer_keywords": ["640", "billion"],
    },
    {
        "id": 8,
        "question": "What was the total reduction in securities holdings since the start of balance sheet runoff?",
        "expected_answer": "About $1.4 trillion",
        "source_pages": [13],
        "answer_keywords": ["1.4", "trillion"],
    },
    {
        "id": 9,
        "question": "What was the PCE inflation rate in April as reported in the June 2023 summary?",
        "expected_answer": "4.4 percent",
        "source_pages": [15],
        "answer_keywords": ["4.4", "percent"],
    },
    {
        "id": 10,
        "question": "What was the federal funds rate target range raised to by the June 2023 summary?",
        "expected_answer": "5 to 5-1/4 percent",
        "source_pages": [15],
        "answer_keywords": ["5 to 5", "5-1/4"],
    },
    {
        "id": 11,
        "question": "How many U.S. global systemically important banks (G-SIBs) are in the LISCC portfolio?",
        "expected_answer": "Eight (8)",
        "source_pages": [32],
        "answer_keywords": ["8", "eight", "G-SIB"],
    },
    {
        "id": 12,
        "question": "How many state member banks existed at year-end 2023?",
        "expected_answer": "706 state chartered banks (1,411 total member banks)",
        "source_pages": [32],
        "answer_keywords": ["706", "1,411"],
    },
    {
        "id": 13,
        "question": "How many U.S. bank holding companies were in operation at year-end 2023?",
        "expected_answer": "3,794 bank holding companies",
        "source_pages": [33],
        "answer_keywords": ["3,794", "3794"],
    },
    {
        "id": 14,
        "question": "How many savings and loan holding companies were in operation at year-end 2023?",
        "expected_answer": "287 savings and loan holding companies",
        "source_pages": [33],
        "answer_keywords": ["287"],
    },
    {
        "id": 15,
        "question": "What was the total amount of civil money penalties assessed by the Federal Reserve in 2023?",
        "expected_answer": "$542,329,952.20",
        "source_pages": [42],
        "answer_keywords": ["542,329,952", "542329952"],
    },
    {
        "id": 16,
        "question": "How many formal enforcement actions did the Federal Reserve complete in 2023?",
        "expected_answer": "63 formal enforcement actions",
        "source_pages": [42],
        "answer_keywords": ["63"],
    },
    {
        "id": 17,
        "question": "What was the total value of stablecoin assets mentioned in the financial stability section?",
        "expected_answer": "Around $125 billion",
        "source_pages": [28],
        "answer_keywords": ["125", "billion", "stablecoin"],
    },
    {
        "id": 18,
        "question": "How many examinations of state member banks did the Federal Reserve conduct in 2023?",
        "expected_answer": "316 examinations",
        "source_pages": [35, 36],
        "answer_keywords": ["316"],
    },
    {
        "id": 19,
        "question": "How much did the Board collect and transfer to the U.S. Treasury for the 2022 S&R Regulation TT assessment in 2023?",
        "expected_answer": "$771,050,870 from 53 institutions",
        "source_pages": [43],
        "answer_keywords": ["771,050,870", "771050870", "53 institutions"],
    },
    {
        "id": 20,
        "question": "When was the Federal Reserve created by an act of Congress?",
        "expected_answer": "December 23, 1913",
        "source_pages": [5],
        "answer_keywords": ["December 23, 1913", "1913"],
    },
]


# ---------------------------------------------------------------------------
# Answer-checking logic
# ---------------------------------------------------------------------------


def check_answer_in_text(text: str, keywords: list[str]) -> bool:
    """Return True if at least one keyword is found in text (case-insensitive)."""
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            return True
    return False


def check_answer_in_results(results: list, keywords: list[str], top_n: int) -> bool:
    """Check if any of the top-N results contain answer keywords."""
    for result in results[:top_n]:
        content = extract_content(result)
        if check_answer_in_text(content, keywords):
            return True
    return False


def extract_content(result) -> str:
    """Extract text content from a result object (works for all result types)."""
    # Direct content field (chunk-level results from match_chunks)
    if isinstance(result, dict):
        return result.get("content", "") or str(result)

    # FusedResult or RetrievalResult subclasses
    if hasattr(result, "content"):
        return result.content or ""
    if hasattr(result, "metadata") and isinstance(result.metadata, dict):
        # Try description from metadata
        return result.metadata.get("doc_description", "") or str(result.metadata)
    if hasattr(result, "doc_description"):
        return result.doc_description or ""
    if hasattr(result, "sections"):
        # TreeSearchResult
        return " ".join(s.get("title", "") for s in (result.sections or []))

    return str(result)


def extract_score(result) -> float:
    """Extract a score from a result object."""
    if isinstance(result, dict):
        return float(result.get("similarity", result.get("score", 0)))
    if hasattr(result, "fused_score"):
        return float(result.fused_score)
    if hasattr(result, "score"):
        return float(result.score)
    return 0.0


# ---------------------------------------------------------------------------
# Main test runner
# ---------------------------------------------------------------------------


def run_tests() -> dict:
    """Execute all retrieval accuracy tests and return structured results."""
    print("=" * 70)
    print("PageIndex Retrieval Accuracy Test")
    print("=" * 70)
    print(f"Document: {PDF_NAME}")
    print(f"Doc ID:   {DOC_ID}")
    print(f"Chunks:   {TOTAL_CHUNKS}")
    print(f"Questions: {len(QUESTIONS)}")
    print()

    # Initialize PageIndex
    print("Initializing PageIndex...")
    pi = PageIndex()
    print("PageIndex initialized successfully.\n")

    # We also get raw chunks for chunk-level evaluation
    from pageindex.db.chunks import match_chunks
    from pageindex.retrieval.semantic import embed_query

    all_results = {
        "test_metadata": {
            "document": PDF_NAME,
            "doc_id": DOC_ID,
            "total_chunks": TOTAL_CHUNKS,
            "num_questions": len(QUESTIONS),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "questions": [],
        "summary": {},
    }

    # Accumulators for summary stats
    strategy_stats: dict[str, dict] = {
        "semantic": {"top1": 0, "top3": 0, "top5": 0, "timings": []},
        "auto": {"top1": 0, "top3": 0, "top5": 0, "timings": []},
        "semantic_chunks": {"top1": 0, "top3": 0, "top5": 0, "timings": []},
        "tree_search": {"top1": 0, "top3": 0, "top5": 0, "timings": []},
        "description": {"top1": 0, "top3": 0, "top5": 0, "timings": []},
    }

    for q in QUESTIONS:
        qid = q["id"]
        question = q["question"]
        keywords = q["answer_keywords"]

        print(f"--- Question {qid}/{len(QUESTIONS)} ---")
        print(f"Q: {question}")
        print(f"Expected: {q['expected_answer']}")
        print(f"Keywords: {keywords}")

        q_results: dict = {
            "id": qid,
            "question": question,
            "expected_answer": q["expected_answer"],
            "source_pages": q["source_pages"],
            "answer_keywords": keywords,
            "results": {},
        }

        # ---------------------------------------------------------------
        # Strategy 1: pi.search(strategy="semantic") -- document-level
        # ---------------------------------------------------------------
        try:
            t0 = time.perf_counter()
            resp = pi.search(question, strategy="semantic")
            elapsed = round(time.perf_counter() - t0, 3)
            results_list = resp.results or []
            scores = [extract_score(r) for r in results_list[:5]]
            top1 = check_answer_in_results(results_list, keywords, 1)
            top3 = check_answer_in_results(results_list, keywords, 3)
            top5 = check_answer_in_results(results_list, keywords, 5)
            q_results["results"]["semantic"] = {
                "num_results": len(results_list),
                "top_scores": scores,
                "answer_in_top1": top1,
                "answer_in_top3": top3,
                "answer_in_top5": top5,
                "top_result_preview": extract_content(results_list[0])[:300] if results_list else "",
                "strategy_used": resp.strategy_used,
                "timing": elapsed,
            }
            strategy_stats["semantic"]["top1"] += int(top1)
            strategy_stats["semantic"]["top3"] += int(top3)
            strategy_stats["semantic"]["top5"] += int(top5)
            strategy_stats["semantic"]["timings"].append(elapsed)
            print(f"  semantic: {len(results_list)} results, top1={top1}, top3={top3}, top5={top5} ({elapsed}s)")
        except Exception as e:
            q_results["results"]["semantic"] = {"error": str(e)}
            print(f"  semantic: ERROR - {e}")

        # ---------------------------------------------------------------
        # Strategy 2: pi.search(strategy="auto") -- orchestrator
        # ---------------------------------------------------------------
        try:
            t0 = time.perf_counter()
            resp = pi.search(question, strategy="auto")
            elapsed = round(time.perf_counter() - t0, 3)
            results_list = resp.results or []
            scores = [extract_score(r) for r in results_list[:5]]
            top1 = check_answer_in_results(results_list, keywords, 1)
            top3 = check_answer_in_results(results_list, keywords, 3)
            top5 = check_answer_in_results(results_list, keywords, 5)
            q_results["results"]["auto"] = {
                "num_results": len(results_list),
                "top_scores": scores,
                "answer_in_top1": top1,
                "answer_in_top3": top3,
                "answer_in_top5": top5,
                "top_result_preview": extract_content(results_list[0])[:300] if results_list else "",
                "strategy_used": resp.strategy_used,
                "reasoning": resp.reasoning,
                "timing": elapsed,
            }
            strategy_stats["auto"]["top1"] += int(top1)
            strategy_stats["auto"]["top3"] += int(top3)
            strategy_stats["auto"]["top5"] += int(top5)
            strategy_stats["auto"]["timings"].append(elapsed)
            print(f"  auto:     {len(results_list)} results (strategy={resp.strategy_used}), top1={top1}, top3={top3}, top5={top5} ({elapsed}s)")
        except Exception as e:
            q_results["results"]["auto"] = {"error": str(e)}
            print(f"  auto:     ERROR - {e}")

        # ---------------------------------------------------------------
        # Strategy 3: Raw chunk-level semantic search (match_chunks)
        # This is the most meaningful test since we have one document
        # and want to check if the right *chunks* are retrieved.
        # ---------------------------------------------------------------
        try:
            t0 = time.perf_counter()
            qvec = embed_query(question)
            chunks = match_chunks(
                query_embedding=qvec,
                match_threshold=0.3,  # lower threshold to get more results
                match_count=10,
            )
            elapsed = round(time.perf_counter() - t0, 3)
            # Filter to our doc
            doc_chunks = [c for c in chunks if c.get("doc_id") == DOC_ID]
            scores = [round(c.get("similarity", 0), 4) for c in doc_chunks[:5]]
            top1 = check_answer_in_results(doc_chunks, keywords, 1)
            top3 = check_answer_in_results(doc_chunks, keywords, 3)
            top5 = check_answer_in_results(doc_chunks, keywords, 5)
            q_results["results"]["semantic_chunks"] = {
                "num_results": len(doc_chunks),
                "top_scores": scores,
                "answer_in_top1": top1,
                "answer_in_top3": top3,
                "answer_in_top5": top5,
                "top_result_preview": (doc_chunks[0].get("content", "")[:300]) if doc_chunks else "",
                "strategy_used": "semantic_chunks",
                "timing": elapsed,
            }
            strategy_stats["semantic_chunks"]["top1"] += int(top1)
            strategy_stats["semantic_chunks"]["top3"] += int(top3)
            strategy_stats["semantic_chunks"]["top5"] += int(top5)
            strategy_stats["semantic_chunks"]["timings"].append(elapsed)
            print(f"  chunks:   {len(doc_chunks)} chunks, top1={top1}, top3={top3}, top5={top5} ({elapsed}s)")
        except Exception as e:
            q_results["results"]["semantic_chunks"] = {"error": str(e)}
            print(f"  chunks:   ERROR - {e}")

        # ---------------------------------------------------------------
        # Strategy 4: pi.search_tree() -- tree-structure search
        # ---------------------------------------------------------------
        try:
            t0 = time.perf_counter()
            tree_results = pi.search_tree(question, doc_ids=[DOC_ID])
            elapsed = round(time.perf_counter() - t0, 3)
            scores = [extract_score(r) for r in tree_results[:5]]
            # For tree results, check section titles and metadata
            top1 = check_answer_in_results(tree_results, keywords, 1)
            top3 = check_answer_in_results(tree_results, keywords, 3)
            top5 = check_answer_in_results(tree_results, keywords, 5)
            q_results["results"]["tree_search"] = {
                "num_results": len(tree_results),
                "top_scores": scores,
                "answer_in_top1": top1,
                "answer_in_top3": top3,
                "answer_in_top5": top5,
                "top_result_preview": extract_content(tree_results[0])[:300] if tree_results else "",
                "strategy_used": "tree_search",
                "timing": elapsed,
            }
            strategy_stats["tree_search"]["top1"] += int(top1)
            strategy_stats["tree_search"]["top3"] += int(top3)
            strategy_stats["tree_search"]["top5"] += int(top5)
            strategy_stats["tree_search"]["timings"].append(elapsed)
            print(f"  tree:     {len(tree_results)} results, top1={top1}, top3={top3}, top5={top5} ({elapsed}s)")
        except Exception as e:
            q_results["results"]["tree_search"] = {"error": str(e)}
            print(f"  tree:     ERROR - {e}")

        # ---------------------------------------------------------------
        # Strategy 5: pi.search_description() -- description search
        # ---------------------------------------------------------------
        try:
            t0 = time.perf_counter()
            desc_results = pi.search_description(question)
            elapsed = round(time.perf_counter() - t0, 3)
            scores = [extract_score(r) for r in desc_results[:5]]
            top1 = check_answer_in_results(desc_results, keywords, 1)
            top3 = check_answer_in_results(desc_results, keywords, 3)
            top5 = check_answer_in_results(desc_results, keywords, 5)
            q_results["results"]["description"] = {
                "num_results": len(desc_results),
                "top_scores": scores,
                "answer_in_top1": top1,
                "answer_in_top3": top3,
                "answer_in_top5": top5,
                "top_result_preview": extract_content(desc_results[0])[:300] if desc_results else "",
                "strategy_used": "description",
                "timing": elapsed,
            }
            strategy_stats["description"]["top1"] += int(top1)
            strategy_stats["description"]["top3"] += int(top3)
            strategy_stats["description"]["top5"] += int(top5)
            strategy_stats["description"]["timings"].append(elapsed)
            print(f"  desc:     {len(desc_results)} results, top1={top1}, top3={top3}, top5={top5} ({elapsed}s)")
        except Exception as e:
            q_results["results"]["description"] = {"error": str(e)}
            print(f"  desc:     ERROR - {e}")

        print()
        all_results["questions"].append(q_results)

    # ---------------------------------------------------------------------------
    # Compute summary
    # ---------------------------------------------------------------------------
    n = len(QUESTIONS)
    summary = {}
    for strategy_name, stats in strategy_stats.items():
        timings = stats["timings"]
        summary[strategy_name] = {
            "top1_accuracy": round(stats["top1"] / n, 4) if n else 0,
            "top3_accuracy": round(stats["top3"] / n, 4) if n else 0,
            "top5_accuracy": round(stats["top5"] / n, 4) if n else 0,
            "top1_count": stats["top1"],
            "top3_count": stats["top3"],
            "top5_count": stats["top5"],
            "total_questions": n,
            "avg_timing": round(sum(timings) / len(timings), 3) if timings else 0,
            "questions_tested": len(timings),
        }

    all_results["summary"] = summary

    # Print summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for strategy_name, s in summary.items():
        print(
            f"  {strategy_name:20s}  top1={s['top1_accuracy']:.0%}  "
            f"top3={s['top3_accuracy']:.0%}  top5={s['top5_accuracy']:.0%}  "
            f"avg_time={s['avg_timing']:.3f}s  "
            f"tested={s['questions_tested']}/{n}"
        )
    print()

    return all_results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    results = run_tests()

    output_path = PROJECT_ROOT / "tests" / "retrieval_accuracy_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"Results saved to {output_path}")
