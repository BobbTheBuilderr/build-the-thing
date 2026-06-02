"""Agent 5 — Multi-Platform Publisher
Publishes the final video to all enabled platforms concurrently (swarm pattern).
"""
from __future__ import annotations
import asyncio
from models.video_project import VideoProject, ProjectStatus
from models.platform_config import Platform, PublishResult
from tools.social_media_tools import SocialMediaTools
from utils import get_logger

log = get_logger("PublishingAgent")


class PublishingAgent:
    """Fans out publish calls to all platforms simultaneously."""

    name = "PublishingAgent"

    def __init__(self) -> None:
        self.sm = SocialMediaTools()

    async def run(
        self,
        project: VideoProject,
        platforms: list[Platform],
    ) -> VideoProject:
        log.info(
            f"[bold green]{self.name}[/] ▶ Publishing to "
            f"{len(platforms)} platform(s): {[p.value for p in platforms]}"
        )
        project.status = ProjectStatus.PUBLISHING
        project.mark_updated()

        platform_copy: dict = getattr(project, "_platform_copy", {})
        video_path = project.video_local_path or ""

        # Publish to all platforms concurrently (true swarm)
        tasks = [
            self._publish_one(platform, project, video_path, platform_copy)
            for platform in platforms
        ]
        results: list[PublishResult] = await asyncio.gather(*tasks)

        project.publish_results = [r.model_dump() for r in results]
        success_count = sum(1 for r in results if r.success)
        log.info(
            f"[bold green]{self.name}[/] ✓ Published {success_count}/{len(results)} platforms"
        )
        project.status = ProjectStatus.COMPLETED
        project.mark_updated()
        return project

    async def _publish_one(
        self,
        platform: Platform,
        project: VideoProject,
        video_path: str,
        platform_copy: dict,
    ) -> PublishResult:
        copy = platform_copy.get(platform.value, {})
        caption = copy.get("caption", project.caption or "")
        description = copy.get("description", project.description or "")
        hashtags = copy.get("hashtags", project.hashtags or [])
        title = project.title or project.topic

        try:
            if platform == Platform.YOUTUBE:
                return await self.sm.upload_youtube(
                    video_path=video_path,
                    title=title,
                    description=description,
                    tags=hashtags,
                    caption=caption,
                )
            elif platform == Platform.TIKTOK:
                return await self.sm.upload_tiktok(
                    video_path=video_path,
                    caption=caption,
                    hashtags=hashtags,
                )
            elif platform == Platform.INSTAGRAM:
                return await self.sm.upload_instagram(
                    video_path=video_path,
                    caption=caption,
                    hashtags=hashtags,
                    video_url=project.video_url,
                )
            elif platform == Platform.FACEBOOK:
                return await self.sm.upload_facebook(
                    video_path=video_path,
                    title=title,
                    description=description,
                    video_url=project.video_url,
                )
            elif platform == Platform.TWITTER:
                tweet = f"{caption} " + " ".join(f"#{h.lstrip('#')}" for h in hashtags[:2])
                return await self.sm.upload_twitter(
                    video_path=video_path,
                    tweet_text=tweet,
                )
            else:
                return PublishResult(
                    platform=platform, success=False, error="Unsupported platform"
                )
        except Exception as exc:
            log.error(f"  ✗ {platform.value}: {exc}")
            return PublishResult(platform=platform, success=False, error=str(exc))
