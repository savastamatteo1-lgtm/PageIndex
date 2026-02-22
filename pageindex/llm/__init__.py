"""Provider-agnostic LLM abstraction layer using LiteLLM.

This module wraps all LLM completion and embedding calls behind a unified
interface. Consuming code imports from here and never touches litellm directly.

Usage:
    from pageindex.llm import LLMProvider, load_llm_config

    config = load_llm_config()
    provider = LLMProvider(config)
    result = provider.complete([{"role": "user", "content": "Hello"}])
"""

from .provider import LLMProvider, get_provider
from .config import load_llm_config

__all__ = ["LLMProvider", "get_provider", "load_llm_config"]
