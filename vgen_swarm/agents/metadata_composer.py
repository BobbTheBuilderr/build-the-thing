"""SA-07 Metadata Composer — per-platform metadata packages.

Generates a distinct title/caption/hashtag/thumbnail package per platform,
enforcing each platform's character limits and hashtag counts, leading with a
hook (no lead-in phrases), labelling season/episode, adding a platform CTA, and
avoiding the banned AI-sounding phrases. Thumbnails are generated via the image
provider and must remain legible small.
"""
from __future__ import annotations

import os

from ..config import BANNED_CAPTION_PHRASES, PLATFORM_LIMITS
from ..models import Script, MetadataPackage, PlatformMetadata
from .base import BaseAgent, AgentResult, QualityCheckError

_BASE_TAGS = ["mystery", "logicpuzzle", "whodunit", "shortfilm", "thriller",
              "detective", "storytime", "plottwist", "cliffhanger", "binge",
              "noir", "suspense", "riddle", "clues", "investigation",
              "darkacademia", "seriestowatch", "episode", "fyp", "viral",
              "storyseries", "puzzlebox", "deduction", "crimedrama",
              "mysterytok", "twistending", "watchtillend", "guessthekiller",
              "islandmystery", "ashford"]


class MetadataComposer(BaseAgent):
    agent_id = "SA-07"
    name = "Metadata Composer"

    def _cta(self, platform: str, is_clue_ep: bool) -> str:
        if is_clue_ep:
            return "Drop your answer below 👇"
        return {"youtube": "Subscribe for the next clue.",
                "x": "Replies hold theories. Mind the spoilers."}.get(
                    platform, "Follow so you don't miss the reveal.")

    def _check_clean(self, *texts: str) -> None:
        low = " ".join(texts).lower()
        for phrase in BANNED_CAPTION_PHRASES:
            if phrase in low:
                raise QualityCheckError(f"banned caption phrase: {phrase!r}")

    def _truncate(self, text: str, limit: int) -> str:
        return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"

    def compose(self, script: Script, is_clue_ep: bool = True) -> MetadataPackage:
        ref = script.ref
        s, e = script.season, script.episode
        hook = "Someone in this house is lying about that night."
        series = ("The Ashford Inheritance — a five-guest island mystery you solve "
                  "by tracking the clues across episodes.")
        thumb_prompt = (f"High-contrast close-up, storm light, key object, bold title "
                        f"'S{s} E{e}', legible at thumbnail size")
        thumb_path = os.path.join(self.config.workdir, ref, "thumb.png")
        self.providers.image.generate_image(thumb_prompt, thumb_path)

        pkg = MetadataPackage(ref=ref)
        for platform in self.config.platforms:
            limits = PLATFORM_LIMITS[platform]
            lo, hi = limits["hashtags"]
            tags = _BASE_TAGS[:hi]
            if len(tags) < lo:
                raise QualityCheckError(f"{platform}: too few hashtags")
            cta = self._cta(platform, is_clue_ep)
            title = self._truncate(f"S{s} E{e}: {hook}", limits["title"])
            caption_full = (f"{hook}\nSeason {s}, Episode {e}.\n\n{series}\n\n{cta}")
            if platform == "youtube":
                caption_full += "\n\n— Full series context & timestamps below."
            caption = self._truncate(caption_full, limits["caption"])
            self._check_clean(title, caption)
            pkg.platforms[platform] = PlatformMetadata(
                platform=platform, title=title, caption=caption,
                hashtags=tags, thumbnail_path=thumb_path, cta=cta)

        self.log("compose", {"ref": ref,
                            "platforms": list(pkg.platforms)}, episode_ref=ref)
        return pkg

    def run(self, script: Script, is_clue_ep: bool = True) -> AgentResult:
        return AgentResult(self.agent_id, True,
                           output=self.compose(script, is_clue_ep))
