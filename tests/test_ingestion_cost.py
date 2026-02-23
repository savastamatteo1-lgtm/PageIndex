#!/usr/bin/env python3
"""Ingest a test PDF and measure approximate LLM cost.

Tracks two separate LLM pathways:
  - Stage 1 (Tree Indexing): Google GenAI SDK direct calls
  - Stages 2-5: LiteLLM completion + embedding calls

Usage:
    python tests/test_ingestion_cost.py
"""

import os
import sys
import time
import threading
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

# ── Fallback pricing ($ per 1M tokens) ──────────────────────────────────

PRICING = {
    "gemini-3.1-pro-preview": {"input": 1.25, "output": 5.00},
    "gemini/gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini/gemini-embedding-001": {"input": 0.006, "output": 0.0},
}


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate cost from token counts using the fallback pricing table."""
    prices = PRICING.get(model, PRICING.get("gemini/gemini-2.0-flash"))
    input_cost = prompt_tokens * prices["input"] / 1_000_000
    output_cost = completion_tokens * prices["output"] / 1_000_000
    return input_cost + output_cost


# ═══════════════════════════════════════════════════════════════════════════
# 1. LiteLLM Callback Tracker (Stages 2-5)
# ═══════════════════════════════════════════════════════════════════════════

import litellm
from litellm.integrations.custom_logger import CustomLogger


class CostTracker(CustomLogger):
    """LiteLLM callback that records token usage for every call."""

    def __init__(self):
        super().__init__()
        self.calls: list[dict] = []
        self._lock = threading.Lock()

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        call_type = kwargs.get("call_type", "unknown")
        model = kwargs.get("model", "unknown")

        prompt_tok = 0
        completion_tok = 0

        if call_type == "embedding":
            usage = getattr(response_obj, "usage", None)
            if usage:
                prompt_tok = getattr(usage, "prompt_tokens", 0) or 0
                completion_tok = 0
        else:
            usage = getattr(response_obj, "usage", None)
            if usage:
                prompt_tok = getattr(usage, "prompt_tokens", 0) or 0
                completion_tok = getattr(usage, "completion_tokens", 0) or 0

        # Try litellm.completion_cost first, fall back to manual
        try:
            cost = litellm.completion_cost(completion_response=response_obj)
        except Exception:
            cost = _estimate_cost(model, prompt_tok, completion_tok)

        with self._lock:
            self.calls.append(
                {
                    "call_type": call_type,
                    "model": model,
                    "prompt_tokens": prompt_tok,
                    "completion_tokens": completion_tok,
                    "cost": cost,
                }
            )

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        self.log_success_event(kwargs, response_obj, start_time, end_time)


cost_tracker = CostTracker()
litellm.callbacks = [cost_tracker]


# ═══════════════════════════════════════════════════════════════════════════
# 2. GenAI Client Proxy (Stage 1 — Tree Indexing)
# ═══════════════════════════════════════════════════════════════════════════

stage1_calls: list[dict] = []
_stage1_lock = threading.Lock()


def _record_stage1(response):
    """Extract usage_metadata from a GenAI response and record it."""
    usage = getattr(response, "usage_metadata", None)
    if usage:
        prompt_tok = getattr(usage, "prompt_token_count", 0) or 0
        completion_tok = getattr(usage, "candidates_token_count", 0) or 0
    else:
        prompt_tok = 0
        completion_tok = 0
    with _stage1_lock:
        stage1_calls.append(
            {
                "prompt_tokens": prompt_tok,
                "completion_tokens": completion_tok,
            }
        )


class _TrackingModels:
    """Proxy for client.models — intercepts generate_content."""

    def __init__(self, real_models):
        self._real = real_models

    def generate_content(self, *args, **kwargs):
        response = self._real.generate_content(*args, **kwargs)
        _record_stage1(response)
        return response

    def __getattr__(self, name):
        return getattr(self._real, name)


class _TrackingAsyncModels:
    """Proxy for client.aio.models — intercepts async generate_content."""

    def __init__(self, real_models):
        self._real = real_models

    async def generate_content(self, *args, **kwargs):
        response = await self._real.generate_content(*args, **kwargs)
        _record_stage1(response)
        return response

    def __getattr__(self, name):
        return getattr(self._real, name)


class _TrackingAio:
    """Proxy for client.aio — wraps aio.models."""

    def __init__(self, real_aio):
        self._real = real_aio
        self.models = _TrackingAsyncModels(real_aio.models)

    def __getattr__(self, name):
        if name == "models":
            return self.models
        return getattr(self._real, name)


class _TrackingClient:
    """Proxy for genai.Client — wraps models and aio.models."""

    def __init__(self, real_client):
        self._real = real_client
        self.models = _TrackingModels(real_client.models)
        self.aio = _TrackingAio(real_client.aio)

    def __getattr__(self, name):
        if name == "models":
            return self.models
        if name == "aio":
            return self.aio
        return getattr(self._real, name)


def _install_genai_proxy():
    """Monkey-patch _get_gemini_client to return a tracking proxy."""
    import pageindex.utils as utils_mod

    original_getter = utils_mod._get_gemini_client

    def _patched_getter():
        real_client = original_getter()
        # Avoid double-wrapping
        if isinstance(real_client, _TrackingClient):
            return real_client
        proxy = _TrackingClient(real_client)
        # Replace the module-level cache so subsequent calls get the proxy
        utils_mod._gemini_client = proxy
        return proxy

    utils_mod._get_gemini_client = _patched_getter


# ═══════════════════════════════════════════════════════════════════════════
# 3. Main
# ═══════════════════════════════════════════════════════════════════════════


def main():
    pdf_path = str(PROJECT_ROOT / "tests" / "pdfs" / "2023-annual-report-truncated.pdf")

    if not os.path.isfile(pdf_path):
        print(f"ERROR: PDF not found at {pdf_path}")
        sys.exit(1)

    # Install proxies
    _install_genai_proxy()

    # Import PageIndex (after proxy installation)
    from pageindex.api import PageIndex

    print("=" * 60)
    print("  PageIndex Ingestion Cost Test")
    print("=" * 60)
    print(f"\n  PDF: {os.path.basename(pdf_path)}")
    print(f"  Supabase: {os.environ.get('SUPABASE_URL', 'NOT SET')}")
    print()

    pi = PageIndex()

    t0 = time.perf_counter()
    result = pi.ingest(path=pdf_path)
    elapsed = time.perf_counter() - t0

    # ── Ingestion Result ─────────────────────────────────────────────

    print("INGESTION RESULT")
    print(f"  Document ID:    {result.document_id}")
    print(f"  Document Name:  {result.document_name}")
    print(f"  Chunks Created: {result.chunks_created}")
    print(f"  Status:         {result.status}")
    print(f"  Elapsed:        {elapsed:.1f}s")

    # ── Stage 1 — Tree Indexing ──────────────────────────────────────

    s1_total_prompt = sum(c["prompt_tokens"] for c in stage1_calls)
    s1_total_completion = sum(c["completion_tokens"] for c in stage1_calls)
    s1_cost = _estimate_cost("gemini-3.1-pro-preview", s1_total_prompt, s1_total_completion)

    print(f"\nSTAGE 1 — Tree Indexing (Google GenAI direct)")
    print(
        f"  Calls: {len(stage1_calls)} | "
        f"Prompt: {s1_total_prompt:,} tok | "
        f"Completion: {s1_total_completion:,} tok | "
        f"Est. Cost: ${s1_cost:.4f}"
    )

    # ── Stages 2-5 — LiteLLM ────────────────────────────────────────

    print(f"\nSTAGES 2-5 — LiteLLM tracked")
    litellm_total_cost = 0.0
    litellm_total_tokens = 0
    for i, call in enumerate(cost_tracker.calls, 1):
        ct = call["call_type"]
        model = call["model"]
        ptok = call["prompt_tokens"]
        ctok = call["completion_tokens"]
        cost = call["cost"]
        litellm_total_cost += cost
        litellm_total_tokens += ptok + ctok

        if ct == "embedding":
            print(f"  #{i:<3} {ct:<12} {model:<35} {ptok:>8,} tok           ${cost:.6f}")
        else:
            print(
                f"  #{i:<3} {ct:<12} {model:<35} {ptok:>6,} + {ctok:>5,} tok  ${cost:.6f}"
            )

    print(
        f"  Subtotal: {len(cost_tracker.calls)} calls, "
        f"{litellm_total_tokens:,} tok, ${litellm_total_cost:.4f}"
    )

    # ── Grand Total ──────────────────────────────────────────────────

    grand_total = s1_cost + litellm_total_cost
    print(f"\nTOTAL ESTIMATED COST: ${grand_total:.4f}")
    print()


if __name__ == "__main__":
    main()
