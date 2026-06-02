"""Agent 4 — Social Media Content Optimiser
Generates platform-optimised captions, descriptions, and hashtags per platform.
"""
from __future__ import annotations
from models.video_project import VideoProject, ProjectStatus
from models.platform_config import Platform
from tools.llm_tools import LLMTools
from utils import get_logger

log = get_logger("SocialMediaAgent")


class SocialMediaAgent:
    """Crafts tailored copy for each social platform using Claude."""

    name = "SocialMediaAgent"

    PLATFORM_NOTES = {
        Platform.YOUTUBE: "YouTube: SEO-rich title, detailed description, chapter timestamps encouraged",
        Platform.TIKTOK: "TikTok: punchy hook first, trending slang, 3-5 hashtags max",
        Platform.INSTAGRAM: "Instagram: emoji-rich, lifestyle-feel, 15-20 hashtags",
        Platform.FACEBOOK: "Facebook: conversational, community-focused, encourage comments",
        Platform.TWITTER: "Twitter/X: under 280 chars, punchy, 1-2 hashtags only",
    }

    def __init__(self) -> None:
        self.llm = LLMTools()

    def run(self, project: VideoProject, platforms: list[Platform]) -> VideoProject:
        log.info(
            f"[bold green]{self.name}[/] ▶ Crafting copy for {len(platforms)} platform(s)"
        )
        project.status = ProjectStatus.UPLOADING
        project.mark_updated()

        # Generate per-platform copy and store as enriched publish metadata
        platform_copy: dict[str, dict] = {}
        for platform in platforms:
            note = self.PLATFORM_NOTES.get(platform, "")
            try:
                copy = self.llm.generate_caption_and_description(
                    title=project.title or project.topic,
                    logline=f"{project.logline or ''} [{note}]",
                    platform=platform.value,
                )
                platform_copy[platform.value] = copy
                log.info(f"  ✓ {platform.value} copy ready")
            except Exception as exc:
                log.warning(f"  ⚠ {platform.value} copy failed, using defaults: {exc}")
                platform_copy[platform.value] = {
                    "caption": project.caption,
                    "description": project.description,
                    "hashtags": project.hashtags,
                }

        # Attach to project for publishing agent to consume
        project._platform_copy = platform_copy  # type: ignore[attr-defined]
        log.info(f"[bold green]{self.name}[/] ✓ Platform copy generated")
        project.mark_updated()
        return project
