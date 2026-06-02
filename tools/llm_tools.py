"""Claude API integration for storyline writing and agent reasoning."""
from __future__ import annotations
import json
import anthropic
from config import settings
from utils import get_logger

log = get_logger("llm_tools")

LANGUAGE_NAMES = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "ja": "Japanese", "zh": "Chinese", "ko": "Korean", "pt": "Portuguese",
    "ar": "Arabic", "hi": "Hindi", "it": "Italian", "ru": "Russian",
}


class LLMTools:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.anthropic_model

    def _chat(self, system: str, user: str, max_tokens: int = 4096) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text.strip()

    # ── Storyline ────────────────────────────────────────────────────────────

    def write_storyline(
        self,
        topic: str,
        genre: str,
        target_audience: str,
        duration_seconds: int,
    ) -> dict:
        system = (
            "You are an award-winning screenwriter and creative director specialising in "
            "short-form video content. Respond ONLY with valid JSON."
        )
        user = f"""Create a complete video storyline for:
Topic: {topic}
Genre: {genre}
Target audience: {target_audience}
Total duration: {duration_seconds} seconds

Return JSON with this exact structure:
{{
  "title": "...",
  "logline": "One-sentence hook",
  "full_script": "Complete narration script",
  "scenes": [
    {{
      "scene_number": 1,
      "title": "...",
      "narration": "...",
      "visual_description": "Detailed visual prompt for AI video generation",
      "duration_seconds": 10,
      "mood": "energetic | calm | dramatic | inspiring | mysterious"
    }}
  ],
  "caption": "Social media caption (max 150 chars)",
  "description": "Longer platform description (200-300 words)",
  "hashtags": ["tag1", "tag2"]
}}"""
        raw = self._chat(system, user, max_tokens=4096)
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            return json.loads(raw[start:end])
        except json.JSONDecodeError as exc:
            log.error(f"Failed to parse storyline JSON: {exc}\nRaw: {raw[:500]}")
            raise

    def generate_caption_and_description(
        self, title: str, logline: str, platform: str
    ) -> dict:
        system = "You are a viral social media content strategist. Respond ONLY with valid JSON."
        user = f"""Write optimised copy for {platform}:
Title: {title}
Logline: {logline}

Return JSON:
{{
  "caption": "...",
  "description": "...",
  "hashtags": ["..."]
}}"""
        raw = self._chat(system, user, max_tokens=1024)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        return json.loads(raw[start:end])

    def translate_subtitle(self, srt_content: str, target_language_code: str) -> str:
        lang_name = LANGUAGE_NAMES.get(target_language_code, target_language_code)
        system = (
            f"You are a professional subtitle translator. Translate the following SRT subtitle "
            f"content to {lang_name}. Preserve all SRT formatting, numbering, and timestamps exactly. "
            "Return ONLY the translated SRT content, nothing else."
        )
        return self._chat(system, srt_content, max_tokens=4096)

    def generate_srt_from_script(self, full_script: str, duration_seconds: int) -> str:
        system = (
            "You are a subtitle editor. Convert the provided script into SRT format. "
            "Split text into natural phrases of 5-10 words. "
            "Distribute evenly across the total duration. "
            "Return ONLY valid SRT content."
        )
        user = f"Script (total {duration_seconds}s):\n{full_script}"
        return self._chat(system, user, max_tokens=2048)
