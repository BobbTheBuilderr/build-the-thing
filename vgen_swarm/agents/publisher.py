"""SA-08 Publisher — platform upload + scheduling (post-approval only).

Triggered by the human approval signal. Publishes per platform via the social
providers, staggering across platform peak-hour windows rather than firing
simultaneously, threads the YouTube URL into the other platforms' descriptions
after YouTube completes, and writes a publish record per platform.
"""
from __future__ import annotations

import time

from ..models import MetadataPackage, VideoArtifact
from .base import BaseAgent, AgentResult


class Publisher(BaseAgent):
    agent_id = "SA-08"
    name = "Publisher"

    def publish(self, video: VideoArtifact, meta: MetadataPackage,
                *, now: float | None = None) -> list[dict]:
        ref = video.ref
        now = now or time.time()
        records: list[dict] = []

        # Publish YouTube first if present so its URL can be threaded elsewhere.
        order = sorted(meta.platforms, key=lambda p: (p != "youtube",
                       self.config.publish_stagger_sec.get(p, 0)))
        youtube_url = None
        for platform in order:
            pm = meta.platforms[platform]
            offset = self.config.publish_stagger_sec.get(platform, 0)
            scheduled = now + offset
            caption = pm.caption
            if youtube_url and platform != "youtube":
                caption = f"{caption}\n\n▶ {youtube_url}"   # cross-platform threading
            result = self.providers.social[platform].publish(
                video.path,
                {"title": pm.title, "caption": caption, "hashtags": pm.hashtags,
                 "thumbnail": pm.thumbnail_path},
                scheduled_ts=scheduled)
            if platform == "youtube":
                youtube_url = result["url"]
            self.db.log_publish(ref, platform, result["post_id"], result["url"])
            records.append({**result, "scheduled_ts": scheduled})
            self.log("publish", result, episode_ref=ref,
                     detail={"platform": platform, "scheduled_ts": scheduled})

        self.db.set_stage(ref, "published", {"publish_records": records})
        return records

    def run(self, video: VideoArtifact, meta: MetadataPackage) -> AgentResult:
        return AgentResult(self.agent_id, True, output=self.publish(video, meta))
