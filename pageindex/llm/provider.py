"""LiteLLM wrapper providing provider-agnostic LLM completion and embedding.

All LLM and embedding calls in the project go through this module.
Model names use the provider prefix format (e.g. ``gemini/gemini-2.0-flash``
for Google AI Studio routing via ``GEMINI_API_KEY``).
"""

from __future__ import annotations

import litellm

# Prevent errors from unsupported parameters when switching providers.
litellm.drop_params = True


class LLMProvider:
    """Thin wrapper around LiteLLM for completion and embedding calls.

    Parameters
    ----------
    config : dict
        Must contain ``completion_model`` (str) and ``embedding_model`` (str).
        Optional keys: ``embedding_dimensions`` (int, default 768),
        ``temperature`` (float, default 0).
    """

    def __init__(self, config: dict) -> None:
        self.completion_model: str = config["completion_model"]
        self.embedding_model: str = config["embedding_model"]
        self.embedding_dimensions: int = config.get("embedding_dimensions", 768)
        self.temperature: float = config.get("temperature", 0)

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------

    def complete(self, messages: list[dict], **kwargs) -> str:
        """Synchronous completion call.

        Returns the assistant message content as a plain string.
        """
        response = litellm.completion(
            model=self.completion_model,
            messages=messages,
            temperature=kwargs.get("temperature", self.temperature),
        )
        return response.choices[0].message.content

    async def acomplete(self, messages: list[dict], **kwargs) -> str:
        """Asynchronous completion call."""
        response = await litellm.acompletion(
            model=self.completion_model,
            messages=messages,
            temperature=kwargs.get("temperature", self.temperature),
        )
        return response.choices[0].message.content

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Returns a list of float vectors whose dimensionality matches
        ``self.embedding_dimensions``.
        """
        response = litellm.embedding(
            model=self.embedding_model,
            input=texts,
            dimensions=self.embedding_dimensions,
        )
        return [item["embedding"] for item in response.data]

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        """Asynchronous embedding call."""
        response = await litellm.aembedding(
            model=self.embedding_model,
            input=texts,
            dimensions=self.embedding_dimensions,
        )
        return [item["embedding"] for item in response.data]

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    def count_tokens(self, text: str, model: str | None = None) -> int:
        """Count tokens for *text* using the given (or default) model tokenizer."""
        target_model = model or self.completion_model
        return litellm.token_counter(
            model=target_model,
            text=text,
        )


# ------------------------------------------------------------------
# Module-level singleton convenience
# ------------------------------------------------------------------

_provider_instance: LLMProvider | None = None


def get_provider() -> LLMProvider:
    """Return a module-level singleton ``LLMProvider`` built from config.yaml.

    Useful for call sites that do not want to manage configuration
    explicitly (e.g. backward-compat shims in ``utils.py``).
    """
    global _provider_instance
    if _provider_instance is None:
        from .config import load_llm_config

        _provider_instance = LLMProvider(load_llm_config())
    return _provider_instance
