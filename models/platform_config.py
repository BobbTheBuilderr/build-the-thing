from __future__ import annotations
from enum import Enum
from pydantic import BaseModel


class Platform(str, Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TWITTER = "twitter"


class PlatformConfig(BaseModel):
    platform: Platform
    enabled: bool = True
    max_duration_seconds: int = 3600
    max_file_size_mb: int = 512
    supported_formats: list[str] = ["mp4"]
    requires_vertical: bool = False


PLATFORM_DEFAULTS: dict[Platform, PlatformConfig] = {
    Platform.YOUTUBE: PlatformConfig(
        platform=Platform.YOUTUBE,
        max_duration_seconds=43200,
        max_file_size_mb=256000,
    ),
    Platform.TIKTOK: PlatformConfig(
        platform=Platform.TIKTOK,
        max_duration_seconds=600,
        max_file_size_mb=4096,
        requires_vertical=True,
    ),
    Platform.INSTAGRAM: PlatformConfig(
        platform=Platform.INSTAGRAM,
        max_duration_seconds=3600,
        max_file_size_mb=4096,
        requires_vertical=True,
    ),
    Platform.FACEBOOK: PlatformConfig(
        platform=Platform.FACEBOOK,
        max_duration_seconds=14400,
        max_file_size_mb=10240,
    ),
    Platform.TWITTER: PlatformConfig(
        platform=Platform.TWITTER,
        max_duration_seconds=140,
        max_file_size_mb=512,
    ),
}


class PublishResult(BaseModel):
    platform: Platform
    success: bool
    post_id: str | None = None
    post_url: str | None = None
    error: str | None = None
