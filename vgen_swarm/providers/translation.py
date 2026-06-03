"""Translation adapters (Module 3 / SA-06).

The spec suggests DeepL *or* the Claude API for translation. This module
provides an LLM-backed translator that works with any
:class:`vgen_swarm.providers.base.LLMProvider` — so the DeepSeek key already
wired for prose also powers real multi-language subtitles, no new account
needed.

``best_available_translation()`` returns an LLM translator when a live LLM is
configured, else the deterministic offline mock.
"""
from __future__ import annotations

# Human-readable names for the prompt, keyed by the spec's required codes.
LANG_NAMES = {
    "en": "English",
    "zh-Hans": "Simplified Chinese (Mandarin)",
    "ms": "Bahasa Malaysia",
    "id": "Bahasa Indonesia",
    "es": "Spanish",
    "ar": "Arabic",
    "pt-BR": "Brazilian Portuguese",
    "pt": "Portuguese",
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
    "ko": "Korean",
}

_TRANSLATE_SYS = ("You are a professional subtitle translator for short-form "
                  "video. Output ONLY the translated line — no quotes, no notes, "
                  "no transliteration, no explanation. Keep it concise enough for "
                  "an on-screen subtitle card.")
_BACK_SYS = ("You are a professional translator. Translate the given line into "
             "natural English. Output ONLY the English translation — nothing else.")


class LLMTranslation:
    """Translate via any live LLM provider (DeepSeek, Claude, …)."""

    live = True

    def __init__(self, llm, name: str = "") -> None:
        self.llm = llm
        self.name = name or f"llm-translate:{type(llm).__name__}"

    @staticmethod
    def lang_name(code: str) -> str:
        return LANG_NAMES.get(code, code)

    def translate(self, text: str, target_lang: str) -> str:
        if target_lang.lower().startswith("en"):
            return text
        out = self.llm.complete(
            _TRANSLATE_SYS,
            f"Translate this subtitle line into {self.lang_name(target_lang)}:\n\n"
            f"{text}",
            max_tokens=256).strip()
        return out or text

    def back_translate(self, text: str, source_lang: str) -> str:
        out = self.llm.complete(
            _BACK_SYS,
            f"Source language: {self.lang_name(source_lang)}. Line:\n\n{text}",
            max_tokens=256).strip()
        return out or text


def best_available_translation():
    """LLM translator if a live LLM is available, else the offline mock."""
    from .llm import best_available_llm
    from .mock import MockTranslation
    llm = best_available_llm()
    if getattr(llm, "live", False):
        return LLMTranslation(llm)
    return MockTranslation()
