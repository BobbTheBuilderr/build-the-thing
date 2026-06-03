"""Provider protocols — the seams where real APIs plug in."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Text generation (Claude API recommended). Used by SA-01/03/07 and the
    translation fallback."""
    def complete(self, system: str, prompt: str, *, max_tokens: int = 1024) -> str: ...


@runtime_checkable
class VideoProvider(Protocol):
    """Runway / Kling / Pika. Renders a scene prompt to a clip on disk."""
    name: str
    def render_scene(self, prompt: dict, out_path: str) -> dict: ...


@runtime_checkable
class MusicProvider(Protocol):
    """Suno / Udio. Generates original BGM from a brief."""
    def compose(self, brief: str, out_path: str, *, motif_ref: str = "") -> dict: ...


@runtime_checkable
class SFXProvider(Protocol):
    """ElevenLabs SFX / Freesound (royalty-free only)."""
    def fetch_sfx(self, description: str, out_path: str) -> dict: ...


@runtime_checkable
class TranscriptionProvider(Protocol):
    """Whisper. Returns word/segment timings aligned to the audio."""
    def transcribe(self, audio_path: str, reference_lines: list[str]) -> list[dict]: ...


@runtime_checkable
class TranslationProvider(Protocol):
    """DeepL / Claude. Translates and back-translates for QA spot checks."""
    def translate(self, text: str, target_lang: str) -> str: ...
    def back_translate(self, text: str, source_lang: str) -> str: ...


@runtime_checkable
class ImageProvider(Protocol):
    """Flux / DALL-E. Thumbnails."""
    def generate_image(self, prompt: str, out_path: str) -> dict: ...


@runtime_checkable
class SocialProvider(Protocol):
    """One social platform's posting API."""
    platform: str
    def publish(self, video_path: str, metadata: dict, *,
                scheduled_ts: Optional[float] = None) -> dict: ...


@dataclass
class ProviderBundle:
    llm: LLMProvider
    video: VideoProvider
    music: MusicProvider
    sfx: SFXProvider
    transcription: TranscriptionProvider
    translation: TranslationProvider
    image: ImageProvider
    social: dict[str, SocialProvider]   # platform name -> provider
