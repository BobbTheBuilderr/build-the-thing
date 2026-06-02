"""External-service provider interfaces and implementations.

Every external dependency named in the spec (video gen, BGM, SFX, Whisper,
translation, image gen, the five social platforms, and the LLM) is reached
through a protocol here. :mod:`mock` supplies deterministic offline
implementations so the whole pipeline is runnable and testable without keys or
network. Real adapters (Runway/Kling/Pika, Suno/Udio, ElevenLabs, Whisper,
DeepL, Flux/DALL-E, the platform APIs) implement the same protocols and read
credentials from the secrets vault — never hardcoded.
"""
from .base import (
    LLMProvider, VideoProvider, MusicProvider, SFXProvider,
    TranscriptionProvider, TranslationProvider, ImageProvider, SocialProvider,
    ProviderBundle,
)
from .mock import default_mock_bundle

__all__ = [
    "LLMProvider", "VideoProvider", "MusicProvider", "SFXProvider",
    "TranscriptionProvider", "TranslationProvider", "ImageProvider",
    "SocialProvider", "ProviderBundle", "default_mock_bundle",
]
