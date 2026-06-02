"""System configuration and operator-tunable parameters."""
from __future__ import annotations

from dataclasses import dataclass, field

# Minimum required subtitle languages (Module 3.1). Operator may extend.
DEFAULT_LANGUAGES: list[str] = ["en", "zh-Hans", "ms", "es", "ar", "pt-BR"]
RTL_LANGUAGES: set[str] = {"ar", "he", "fa", "ur"}

# Per-platform metadata limits (Module 4.1).
PLATFORM_LIMITS: dict[str, dict] = {
    "tiktok":    {"title": 90,  "caption": 2200, "hashtags": (5, 8)},
    "youtube":   {"title": 100, "caption": 5000, "hashtags": (15, 15)},
    "instagram": {"title": 220, "caption": 2200, "hashtags": (20, 30)},
    "facebook":  {"title": 255, "caption": 5000, "hashtags": (10, 10)},
    "x":         {"title": 280, "caption": 280,  "hashtags": (3, 5)},
}

# Subtitle specs (Module 3.2).
SUBTITLE_MAX_LINES = 2
SUBTITLE_MAX_CHARS_PER_LINE = 42
SUBTITLE_MIN_DURATION_SEC = 1.5
SUBTITLE_TIMING_TOLERANCE_SEC = 0.3

# Video / audio targets (Modules 2 & 6).
EPISODE_MIN_SEC = 90
EPISODE_MAX_SEC = 180
TARGET_LUFS = -14.0
LUFS_TOLERANCE = 2.0
MAX_SILENCE_GAP_SEC = 2.0
TARGET_ASPECT = "9:16"

# Phrases SA-07 must avoid (Module 4.1 caption rules).
BANNED_CAPTION_PHRASES = [
    "dive into", "embark on", "in a world where", "look no further",
    "buckle up", "get ready to", "unleash",
]

VIDEO_MAX_RETRIES = 3


@dataclass
class SwarmConfig:
    languages: list[str] = field(default_factory=lambda: list(DEFAULT_LANGUAGES))
    platforms: list[str] = field(
        default_factory=lambda: ["tiktok", "youtube", "instagram", "facebook", "x"])
    family_appropriate: bool = True
    workdir: str = "build_output"
    db_path: str = "build_output/vgen_state.db"
    audit_path: str = "build_output/audit.log"
    # staggered publish offsets per platform, in seconds (peak-hour windows)
    publish_stagger_sec: dict = field(default_factory=lambda: {
        "tiktok": 0, "youtube": 1800, "instagram": 3600,
        "facebook": 5400, "x": 7200})
