"""SA-09 QA Auditor — automated checks before human review.

Runs the spec's QA checklist across video, audio, subtitles, metadata, and story
continuity. Any failed check blocks the episode from the human review queue; the
orchestrator routes a failing episode back to the responsible agent.
"""
from __future__ import annotations

from ..config import (EPISODE_MAX_SEC, EPISODE_MIN_SEC, LUFS_TOLERANCE,
                      MAX_SILENCE_GAP_SEC, PLATFORM_LIMITS, TARGET_ASPECT,
                      TARGET_LUFS)
from ..models import (AudioArtifact, MetadataPackage, QACheck, QAReport, Script,
                      SubtitleArtifact, VideoArtifact)
from .base import BaseAgent, AgentResult

_CLIP_THRESHOLD = 0.85


class QAAuditor(BaseAgent):
    agent_id = "SA-09"
    name = "QA Auditor"

    def run_audit(self, *, script: Script, video: VideoArtifact, audio: AudioArtifact,
                  subs: SubtitleArtifact, meta: MetadataPackage) -> QAReport:
        ref = script.ref
        c: list[QACheck] = []

        # --- Video ----------------------------------------------------------
        c.append(QACheck("aspect_ratio", "video",
                         video.aspect_ratio == TARGET_ASPECT, video.aspect_ratio))
        c.append(QACheck("no_watermark_or_artifacts", "video",
                         not video.has_watermark and not video.has_text_artifacts))
        worst = min(video.character_consistency.values(), default=1.0)
        c.append(QACheck("character_consistency", "video",
                         worst >= _CLIP_THRESHOLD, f"min CLIP={worst:.2f}"))
        c.append(QACheck("duration_in_range", "video",
                         EPISODE_MIN_SEC <= video.duration_sec <= EPISODE_MAX_SEC,
                         f"{video.duration_sec}s"))

        # --- Audio ----------------------------------------------------------
        c.append(QACheck("audio_present_synced", "audio",
                         audio.duration_sec > 0
                         and abs(audio.duration_sec - video.duration_sec) <= 0.5))
        c.append(QACheck("lufs_in_spec", "audio",
                         abs(audio.lufs - TARGET_LUFS) <= LUFS_TOLERANCE,
                         f"{audio.lufs} LUFS"))
        c.append(QACheck("no_clipping_or_long_silence", "audio",
                         not audio.clipping
                         and audio.max_silence_gap_sec <= MAX_SILENCE_GAP_SEC))

        # --- Subtitles ------------------------------------------------------
        required = set(self.config.languages)
        present = set(subs.tracks)
        c.append(QACheck("all_languages_present", "subtitles",
                         required.issubset(present),
                         f"missing={sorted(required - present)}"))
        timing_ok = all(cue["end"] > cue["start"]
                        for t in subs.tracks.values() for cue in t.cues)
        c.append(QACheck("subtitle_timing_valid", "subtitles", timing_ok))
        untranslated = self._find_untranslated(subs)
        c.append(QACheck("no_untranslated_lines", "subtitles",
                         not untranslated, f"{len(untranslated)} suspect"))

        # --- Metadata -------------------------------------------------------
        meta_complete = set(self.config.platforms).issubset(set(meta.platforms))
        c.append(QACheck("metadata_complete", "metadata", meta_complete))
        c.append(QACheck("thumbnails_present", "metadata",
                         all(p.thumbnail_path for p in meta.platforms.values())))
        c.append(QACheck("char_limit_compliance", "metadata",
                         self._limits_ok(meta)))

        # --- Story continuity ----------------------------------------------
        season, episode = script.season, script.episode
        placed = {p["clue_id"]
                  for p in self.db.clue_placements_for_episode(season, episode)}
        manifest = set(script.clue_manifest)
        c.append(QACheck("clue_manifest_matches_tracker", "continuity",
                         placed == manifest,
                         f"manifest^tracker diff={placed ^ manifest}"))
        c.append(QACheck("no_continuity_errors", "continuity",
                         self._continuity_ok(season)))

        report = QAReport(ref=ref, checks=c)
        self.db.set_stage(ref, "qa", {"qa_report": report.to_dict()})
        self.log("audit", report.to_dict(), episode_ref=ref,
                 status="ok" if report.passed else "fail",
                 detail={"failures": [f.name for f in report.failures]})
        return report

    def _find_untranslated(self, subs: SubtitleArtifact) -> list[str]:
        bad = []
        en = subs.tracks.get("en")
        en_texts = {cue["text"] for cue in en.cues} if en else set()
        for lang, track in subs.tracks.items():
            if lang.startswith("en"):
                continue
            for cue in track.cues:
                if cue["text"] in en_texts and cue["text"].strip():
                    bad.append(f"{lang}:{cue['text'][:20]}")
        return bad

    def _limits_ok(self, meta: MetadataPackage) -> bool:
        for platform, pm in meta.platforms.items():
            lim = PLATFORM_LIMITS[platform]
            lo, hi = lim["hashtags"]
            if len(pm.title) > lim["title"] or len(pm.caption) > lim["caption"]:
                return False
            if not (lo <= len(pm.hashtags) <= hi):
                return False
        return True

    def _continuity_ok(self, season: int) -> bool:
        """No clue placed in a season later than its own; solution not revealed
        in-season (the spec non-negotiable)."""
        state = self.db.get_puzzle_state(season)
        if not state:
            return True
        for cid, p in state["placement_log"].items():
            if p["season"] != season:
                return False
        return True

    def run(self, **kw) -> AgentResult:
        report = self.run_audit(**kw)
        return AgentResult(self.agent_id, report.passed, output=report)
