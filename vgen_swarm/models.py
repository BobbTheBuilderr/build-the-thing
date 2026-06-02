"""Domain models for the VGEN-SWARM story universe and production artifacts.

These are plain dataclasses (JSON-serialisable) so they round-trip cleanly
through the SQLite state stores in ``vgen_swarm.state``.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# Production pipeline stages (Production Queue store)
# --------------------------------------------------------------------------- #
class Stage(str, Enum):
    PLANNING = "planning"
    WRITING = "writing"
    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLES = "subtitles"
    METADATA = "metadata"
    QA = "qa"
    REVIEW = "review"
    PUBLISHED = "published"
    FAILED = "failed"

    @classmethod
    def production_order(cls) -> list["Stage"]:
        return [cls.WRITING, cls.VIDEO, cls.AUDIO, cls.SUBTITLES,
                cls.METADATA, cls.QA, cls.REVIEW]


# --------------------------------------------------------------------------- #
# Story universe
# --------------------------------------------------------------------------- #
@dataclass
class Character:
    name: str
    role: str
    traits: list[str] = field(default_factory=list)
    motivation: str = ""
    # SA-04 visual bible anchor (appearance prompt template, kept stable across eps)
    appearance_anchor: str = ""


@dataclass
class Universe:
    title: str
    genre: str
    setting: str
    central_conflict: str
    tone: str
    cast: list[Character] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class SeasonArc:
    season: int
    summary: str
    revelation: str          # the thing the puzzle solution reveals this season
    cliffhanger: str
    num_episodes: int


@dataclass
class EpisodeOutline:
    season: int
    episode: int
    title: str
    logline: str
    cold_open: str
    main_scene: str
    clue_beat: str
    ending_hook: str

    @property
    def ref(self) -> str:
        return f"S{self.season:02d}E{self.episode:02d}"


# --------------------------------------------------------------------------- #
# Puzzle artifacts (Puzzle State store) — see vgen_swarm.puzzle
# --------------------------------------------------------------------------- #
@dataclass
class SeededClue:
    """A puzzle clue placed into a specific episode."""
    clue_id: str
    season: int
    episode: int
    logical_form: str        # machine form, e.g. "left_of(A, B)"
    narrative_form: str      # how it is spoken/shown on screen


# --------------------------------------------------------------------------- #
# Script artifacts
# --------------------------------------------------------------------------- #
@dataclass
class Scene:
    index: int
    description: str         # what happens (for SA-04 prompt crafting)
    dialogue: list[str] = field(default_factory=list)
    start_sec: float = 0.0
    end_sec: float = 0.0
    emotional_beat: str = "" # for SA-05 BGM sync
    transition: str = "cut"  # cut | fade | whip_pan | match_cut


@dataclass
class Script:
    season: int
    episode: int
    title: str
    scenes: list[Scene] = field(default_factory=list)
    # hidden internal metadata: which clue_ids are seeded this episode
    clue_manifest: list[str] = field(default_factory=list)

    @property
    def ref(self) -> str:
        return f"S{self.season:02d}E{self.episode:02d}"

    @property
    def duration_sec(self) -> float:
        return max((s.end_sec for s in self.scenes), default=0.0)

    @property
    def all_dialogue(self) -> list[str]:
        out: list[str] = []
        for s in self.scenes:
            out.extend(s.dialogue)
        return out


# --------------------------------------------------------------------------- #
# Media artifacts produced by SA-04/05/06
# --------------------------------------------------------------------------- #
@dataclass
class VideoArtifact:
    ref: str
    path: str
    aspect_ratio: str = "9:16"
    width: int = 1080
    height: int = 1920
    fps: int = 30
    duration_sec: float = 0.0
    has_watermark: bool = False
    has_text_artifacts: bool = False
    # CLIP-similarity to character visual bible, per character (0..1)
    character_consistency: dict[str, float] = field(default_factory=dict)
    scene_prompts: list[dict] = field(default_factory=list)


@dataclass
class AudioArtifact:
    ref: str
    path: str
    lufs: float = -14.0
    sample_rate: int = 48000
    codec: str = "aac"
    duration_sec: float = 0.0
    max_silence_gap_sec: float = 0.0
    clipping: bool = False
    bgm_brief: str = ""
    motif_ref: str = ""      # recurring season sonic identity


@dataclass
class SubtitleTrack:
    lang: str
    rtl: bool
    cues: list[dict] = field(default_factory=list)   # {start, end, text}
    srt_path: str = ""
    ass_path: str = ""


@dataclass
class SubtitleArtifact:
    ref: str
    tracks: dict[str, SubtitleTrack] = field(default_factory=dict)
    burned_in_path: str = ""


@dataclass
class PlatformMetadata:
    platform: str
    title: str
    caption: str
    hashtags: list[str]
    thumbnail_path: str
    cta: str = ""


@dataclass
class MetadataPackage:
    ref: str
    platforms: dict[str, PlatformMetadata] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# QA + review
# --------------------------------------------------------------------------- #
@dataclass
class QACheck:
    name: str
    category: str
    passed: bool
    detail: str = ""


@dataclass
class QAReport:
    ref: str
    checks: list[QACheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failures(self) -> list[QACheck]:
        return [c for c in self.checks if not c.passed]

    def to_dict(self) -> dict:
        return {"ref": self.ref, "passed": self.passed,
                "checks": [asdict(c) for c in self.checks]}
