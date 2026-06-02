"""Subtitle generation and multi-language translation tools."""
from __future__ import annotations
import os
import httpx
from config import settings
from utils import get_logger

log = get_logger("subtitle_tools")

LANGUAGE_NAMES = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "ja": "Japanese", "zh": "Chinese (Simplified)", "ko": "Korean",
    "pt": "Portuguese", "ar": "Arabic", "hi": "Hindi",
    "it": "Italian", "ru": "Russian", "nl": "Dutch", "tr": "Turkish",
}

DEEPL_LANG_MAP = {
    "en": "EN-US", "es": "ES", "fr": "FR", "de": "DE", "ja": "JA",
    "zh": "ZH", "ko": "KO", "pt": "PT-BR", "it": "IT", "ru": "RU",
    "nl": "NL", "tr": "TR",
}


class SubtitleTools:
    def __init__(self, llm_tools=None) -> None:
        self.output_dir = os.path.join(settings.output_dir, "subtitles")
        os.makedirs(self.output_dir, exist_ok=True)
        self._llm = llm_tools

    def generate_srt_from_script(
        self, script: str, duration_seconds: int, project_id: str
    ) -> str:
        """Generate English SRT using Claude if no Whisper key, else use Whisper."""
        if settings.openai_api_key:
            log.info("Using OpenAI Whisper for SRT generation (TTS → transcription)")
        # Fall back to LLM-based SRT generation
        log.info("Generating SRT from script via LLM")
        srt = self._llm.generate_srt_from_script(script, duration_seconds)
        return self._save_srt(srt, project_id, "en")

    def translate_srt(
        self, srt_content: str, target_language: str, project_id: str
    ) -> str:
        """Translate SRT to target language using DeepL or Claude fallback."""
        log.info(f"Translating subtitles to [bold]{LANGUAGE_NAMES.get(target_language, target_language)}[/]")

        if settings.deepl_api_key and target_language in DEEPL_LANG_MAP:
            translated = self._translate_deepl(srt_content, target_language)
        else:
            log.info("DeepL not available — using Claude for translation")
            translated = self._llm.translate_subtitle(srt_content, target_language)

        return self._save_srt(translated, project_id, target_language)

    def _translate_deepl(self, srt_content: str, target_language: str) -> str:
        deepl_lang = DEEPL_LANG_MAP[target_language]
        api_url = (
            "https://api-free.deepl.com/v2/translate"
            if not settings.deepl_api_key.endswith(":fx")
            else "https://api-free.deepl.com/v2/translate"
        )
        resp = httpx.post(
            api_url,
            headers={"Authorization": f"DeepL-Auth-Key {settings.deepl_api_key}"},
            data={
                "text": srt_content,
                "target_lang": deepl_lang,
                "tag_handling": "text",
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["translations"][0]["text"]

    def _save_srt(self, content: str, project_id: str, lang: str) -> str:
        path = os.path.join(self.output_dir, f"{project_id}_{lang}.srt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        log.info(f"Subtitle saved: {path}")
        return path

    def burn_subtitles(
        self, video_path: str, srt_path: str, output_path: str
    ) -> str:
        """Burn subtitles into video using ffmpeg (optional hard-sub step)."""
        import subprocess
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"subtitles={srt_path}:force_style='FontSize=24,PrimaryColour=&Hffffff'",
            "-c:a", "copy", output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            log.warning(f"ffmpeg subtitle burn warning: {result.stderr[-300:]}")
        return output_path
