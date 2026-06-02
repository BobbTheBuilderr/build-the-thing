from __future__ import annotations
from enum import Enum
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
    PENDING = "pending"
    WRITING_STORYLINE = "writing_storyline"
    GENERATING_VIDEO = "generating_video"
    ADDING_SUBTITLES = "adding_subtitles"
    UPLOADING = "uploading"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    FAILED = "failed"


class SceneScript(BaseModel):
    scene_number: int
    title: str
    narration: str
    visual_description: str
    duration_seconds: int = 5
    mood: str = "neutral"


class SubtitleTrack(BaseModel):
    language_code: str
    language_name: str
    srt_content: str
    file_path: str | None = None


class VideoProject(BaseModel):
    project_id: str
    topic: str
    genre: str = "general"
    target_audience: str = "general"
    duration_seconds: int = 60
    status: ProjectStatus = ProjectStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Storyline
    title: str | None = None
    logline: str | None = None
    full_script: str | None = None
    scenes: list[SceneScript] = []

    # Video
    video_url: str | None = None
    video_local_path: str | None = None
    thumbnail_path: str | None = None

    # Subtitles
    subtitle_tracks: list[SubtitleTrack] = []

    # Social
    caption: str | None = None
    description: str | None = None
    hashtags: list[str] = []
    publish_results: list[dict[str, Any]] = []

    def mark_updated(self) -> None:
        self.updated_at = datetime.utcnow()
