"""SA-04 Video Director — prompt crafting + render coordination.

Translates each scene into a generation-ready 9:16 prompt (subject, action,
camera, lighting, palette, environment, transition), maintains a per-character
visual bible for cross-episode consistency, calls the video provider, and
applies up to 3 quality-check retries before escalating to the orchestrator.
"""
from __future__ import annotations

import os

from ..config import VIDEO_MAX_RETRIES, TARGET_ASPECT
from ..models import Script, VideoArtifact
from .base import BaseAgent, AgentResult, QualityCheckError

_PALETTE = "desaturated teal and amber, deep shadow"
_LIGHTING = "low-key, single practical source, volumetric haze"


class VideoDirector(BaseAgent):
    agent_id = "SA-04"
    name = "Video Director"

    def ensure_visual_bible(self, cast: list[dict]) -> None:
        """Persist a stable appearance anchor per character (the visual bible)."""
        for ch in cast:
            if self.db.get_visual_anchor(ch["name"]) is None:
                anchor = {
                    "character": ch["name"],
                    "prompt_anchor": (
                        f"{ch['name']}, {ch['role']}, consistent face and wardrobe; "
                        f"{', '.join(ch.get('traits', []))}"),
                }
                self.db.save_visual_anchor(ch["name"], anchor)
        self.log("ensure_visual_bible", {"cast": [c["name"] for c in cast]})

    def craft_prompt(self, ref: str, scene: dict) -> dict:
        return {
            "ref": ref, "scene_index": scene["index"],
            "subject": "two figures in tense conversation",
            "action": scene["description"],
            "camera": "slow push-in, eye level",
            "lighting": _LIGHTING,
            "palette": _PALETTE,
            "environment": "storm-lit island estate interior",
            "aspect_ratio": TARGET_ASPECT,
            "transition": scene.get("transition", "cut"),
            "duration_sec": scene["end_sec"] - scene["start_sec"],
            "negatives": "no human hands artifacts, no watermark, no on-screen text",
        }

    def _quality_ok(self, meta: dict) -> bool:
        return (meta.get("aspect_ratio") == TARGET_ASPECT
                and not meta.get("has_watermark", True)
                and not meta.get("has_text_artifacts", True))

    def render(self, script: Script, cast_names: list[str]) -> VideoArtifact:
        ref = script.ref
        out_path = os.path.join(self.config.workdir, ref, "video.mp4")
        prompts = [self.craft_prompt(ref, vars(s)) for s in script.scenes]

        last_meta = {}
        for attempt in range(1, VIDEO_MAX_RETRIES + 1):
            metas = [self.providers.video.render_scene(p, out_path) for p in prompts]
            last_meta = metas[-1] if metas else {}
            if all(self._quality_ok(m) for m in metas):
                break
            self.log("render_retry", {"attempt": attempt}, episode_ref=ref,
                     status="retry")
        else:
            raise QualityCheckError(
                f"{ref}: video failed quality check after {VIDEO_MAX_RETRIES} retries")

        # character consistency vs visual bible (CLIP similarity, mocked high)
        consistency = {name: 0.93 for name in cast_names}
        artifact = VideoArtifact(
            ref=ref, path=out_path, aspect_ratio=TARGET_ASPECT,
            duration_sec=script.duration_sec, has_watermark=False,
            has_text_artifacts=False, character_consistency=consistency,
            scene_prompts=prompts)
        self.log("render", {"path": out_path, "scenes": len(prompts),
                            "consistency": consistency}, episode_ref=ref)
        return artifact

    def run(self, script: Script, cast: list[dict]) -> AgentResult:
        self.ensure_visual_bible(cast)
        artifact = self.render(script, [c["name"] for c in cast])
        return AgentResult(self.agent_id, True, output=artifact)
