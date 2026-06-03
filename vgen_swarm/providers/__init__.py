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
from .mock import (default_mock_bundle, MockLLM, MockTranscription,
                   MockSocial, MockImage)
from .llm import DeepSeekLLM, ClaudeLLM, best_available_llm
from .image import OpenAIImage, TogetherFlux, best_available_image
from .translation import LLMTranslation, best_available_translation
from .ffmpeg_media import SlideshowVideo, FreeMusic, FreeSFX, ffmpeg_available


def budget_bundle(*, music_library_dir=None):
    """Near-zero-cost provider bundle: DeepSeek text (cheap), real thumbnails if
    a key is set, an ffmpeg slideshow for video (no per-second billing), and free
    synthesised/library audio. Social stays mocked (no live posting)."""
    image = best_available_image()
    return ProviderBundle(
        llm=best_available_llm(),
        video=SlideshowVideo(image),
        music=FreeMusic(library_dir=music_library_dir),
        sfx=FreeSFX(),
        transcription=MockTranscription(),
        translation=best_available_translation(),
        image=image,
        social={p: MockSocial(p) for p in
                ("tiktok", "youtube", "instagram", "facebook", "x")},
    )


__all__ = [
    "LLMProvider", "VideoProvider", "MusicProvider", "SFXProvider",
    "TranscriptionProvider", "TranslationProvider", "ImageProvider",
    "SocialProvider", "ProviderBundle", "default_mock_bundle", "budget_bundle",
    "DeepSeekLLM", "ClaudeLLM", "best_available_llm",
    "OpenAIImage", "TogetherFlux", "best_available_image",
    "LLMTranslation", "best_available_translation",
    "SlideshowVideo", "FreeMusic", "FreeSFX", "ffmpeg_available",
]
