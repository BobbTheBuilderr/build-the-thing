"""LLM adapters for story/script/metadata prose.

Three implementations of :class:`vgen_swarm.providers.base.LLMProvider`:

* :class:`DeepSeekLLM` — DeepSeek's OpenAI-compatible chat API (``deepseek-chat``
  / ``deepseek-reasoner``). Pure standard library (urllib), no extra packages.
* :class:`ClaudeLLM`   — Anthropic Claude (requires the ``anthropic`` package).
* ``MockLLM``          — deterministic offline stub (see ``mock.py``).

``best_available_llm()`` picks the first usable real provider (DeepSeek, then
Claude) and otherwise falls back to the mock, so the pipeline always runs.

Real providers expose ``live = True``; agents check this before asking the LLM
for prose, falling back to deterministic templates when it is a mock or errors.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional

DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"
CLAUDE_DEFAULT_MODEL = "claude-sonnet-4-6"


class DeepSeekLLM:
    """DeepSeek chat completions via its OpenAI-compatible endpoint."""

    live = True

    def __init__(self, model: str = DEEPSEEK_DEFAULT_MODEL,
                 api_key: Optional[str] = None,
                 base_url: str = "https://api.deepseek.com") -> None:
        self.model = model
        self._api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        self.base_url = base_url.rstrip("/")

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def complete(self, system: str, prompt: str, *, max_tokens: int = 1024) -> str:
        if not self._api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not set")
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "stream": False,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=payload, method="POST",
            headers={"Authorization": f"Bearer {self._api_key}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


class ClaudeLLM:
    """Anthropic Claude. Recommended model per the spec's stack table."""

    live = True

    def __init__(self, model: str = CLAUDE_DEFAULT_MODEL,
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
        resp = self._ensure_client().messages.create(
            model=self.model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in resp.content
                       if getattr(b, "type", None) == "text")


def best_available_llm():
    """Return the first usable real LLM (DeepSeek, then Claude), else the mock."""
    deepseek = DeepSeekLLM()
    if deepseek.available:
        return deepseek
    claude = ClaudeLLM()
    if claude.available:
        return claude
    from .mock import MockLLM
    return MockLLM()
