"""Claude API LLM adapter.

Implements :class:`vgen_swarm.providers.base.LLMProvider`. Uses the Anthropic SDK
when ``ANTHROPIC_API_KEY`` is set and the package is installed; otherwise the
caller should fall back to the deterministic ``MockLLM`` so the pipeline still
runs offline. Recommended model: ``claude-sonnet-4`` (per the spec's stack
table) for story/script/metadata generation.
"""
from __future__ import annotations

import os
from typing import Optional

DEFAULT_MODEL = "claude-sonnet-4-6"


class ClaudeLLM:
    def __init__(self, model: str = DEFAULT_MODEL,
                 api_key: Optional[str] = None) -> None:
        self.model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = None

    @property
    def available(self) -> bool:
        if not self._api_key:
            return False
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            return False

    def _ensure_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def complete(self, system: str, prompt: str, *, max_tokens: int = 1024) -> str:
        client = self._ensure_client()
        resp = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in resp.content
                       if getattr(block, "type", None) == "text")


def best_available_llm():
    """Return a Claude adapter if usable, else the deterministic mock."""
    claude = ClaudeLLM()
    if claude.available:
        return claude
    from .mock import MockLLM
    return MockLLM()
