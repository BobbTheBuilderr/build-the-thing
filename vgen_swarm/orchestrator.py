"""Master Orchestrator Agent (MOA).

Coordinates the sub-agents, advances each episode through the production state
machine (writing → video → audio → subtitles → metadata → QA → review →
published), tracks season/episode state, applies retry logic on quality-check
failures, gates publishing behind the single human approval signal, and routes
QA failures back to the responsible agent.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .agents import (AudioComposer, MetadataComposer, Publisher, PuzzleWeaver,
                     QAAuditor, ScriptWriter, StoryArchitect, SubtitleEngine,
                     VideoDirector, QualityCheckError)
from .audit_log import AuditLog
from .config import SwarmConfig
from .cost import BudgetExceeded, estimate_episode
from .models import Stage
from .providers.base import ProviderBundle
from .state.db import StateDB

MAX_STAGE_RETRIES = 3


@dataclass
class EpisodeBundle:
    ref: str
    script: object = None
    video: object = None
    audio: object = None
    subs: object = None
    meta: object = None
    qa: object = None
    cost_estimate: object = None


class MasterOrchestrator:
    def __init__(self, providers: ProviderBundle,
                 config: Optional[SwarmConfig] = None,
                 db: Optional[StateDB] = None,
                 audit: Optional[AuditLog] = None) -> None:
        self.config = config or SwarmConfig()
        self.db = db or StateDB(self.config.db_path)
        self.audit = audit or AuditLog(self.config.audit_path)
        self.providers = providers
        a = (self.db, self.providers, self.audit, self.config)
        self.sa01 = StoryArchitect(*a)
        self.sa02 = PuzzleWeaver(*a)
        self.sa03 = ScriptWriter(*a)
        self.sa04 = VideoDirector(*a)
        self.sa05 = AudioComposer(*a)
        self.sa06 = SubtitleEngine(*a)
        self.sa07 = MetadataComposer(*a)
        self.sa09 = QAAuditor(*a)
        self.sa08 = Publisher(*a)
        self._bundles: dict[str, EpisodeBundle] = {}

    def _log(self, action: str, output, **kw):
        return self.audit.record("MOA:Orchestrator", action, output, **kw)

    # -- season planning -----------------------------------------------------
    def bootstrap_season(self, season: int, *, num_episodes: int = 8,
                         seed: Optional[int] = None) -> None:
        """Build universe (once), plan seasons, design + validate this season's
        puzzle, outline episodes, and embed clues. Runs before any script."""
        if self.db.get_universe() is None:
            self.sa01.run(seasons=max(3, season + 2))
        universe = self.db.get_universe()
        cast_names = [c["name"] for c in universe["cast"]]

        outlines = self.sa01.outline_episodes(season, num_episodes)
        episode_refs = [(o.episode, o.ref) for o in outlines]

        # SA-02 designs + validates the grid, then embeds clues across episodes.
        self.sa02.run(season, cast_names, episode_refs, seed=seed)
        self._log("bootstrap_season", {"season": season,
                  "episodes": len(outlines)}, detail={"season": season})

    # -- per-episode pipeline -----------------------------------------------
    def _retry(self, stage: str, ref: str, fn: Callable):
        for attempt in range(1, MAX_STAGE_RETRIES + 1):
            try:
                return fn()
            except QualityCheckError as exc:
                self._log("stage_retry", {"stage": stage, "attempt": attempt,
                          "error": str(exc)}, episode_ref=ref, status="retry")
                if attempt == MAX_STAGE_RETRIES:
                    self.db.set_stage(ref, Stage.FAILED.value,
                                      {"failed_stage": stage, "error": str(exc)})
                    self._log("stage_failed", {"stage": stage, "error": str(exc)},
                              episode_ref=ref, status="fail")
                    raise

    def produce_episode(self, season: int, episode: int) -> EpisodeBundle:
        ref = f"S{season:02d}E{episode:02d}"
        universe = self.db.get_universe()
        cast = universe["cast"]
        bundle = EpisodeBundle(ref=ref)
        self._bundles[ref] = bundle
        self.db.set_stage(ref, Stage.WRITING.value)

        bundle.script = self._retry(Stage.WRITING.value, ref,
                                    lambda: self.sa03.write(season, episode))

        # Estimate cost before any (potentially paid) media generation runs, and
        # enforce the operator's per-episode cap if one is set.
        est = estimate_episode(
            self.providers, duration_sec=bundle.script.duration_sec,
            num_scenes=len(bundle.script.scenes),
            num_dialogue_lines=len(bundle.script.all_dialogue),
            num_languages=len(self.config.languages),
            num_platforms=len(self.config.platforms))
        bundle.cost_estimate = est
        self._log("cost_estimate", est.as_dict(), episode_ref=ref)
        cap = self.config.max_cost_per_episode
        if cap is not None and est.total > cap:
            self.db.set_stage(ref, Stage.FAILED.value,
                              {"budget_exceeded": True, "estimate_usd": est.total,
                               "cap_usd": cap})
            self._log("budget_exceeded",
                      {"estimate_usd": est.total, "cap_usd": cap},
                      episode_ref=ref, status="fail")
            raise BudgetExceeded(
                f"{ref}: estimated ${est.total} exceeds cap ${cap}")

        self.db.set_stage(ref, Stage.VIDEO.value)
        bundle.video = self._retry(
            Stage.VIDEO.value, ref,
            lambda: self.sa04.run(bundle.script, cast).output)
        self.db.set_stage(ref, Stage.AUDIO.value)
        bundle.audio = self._retry(Stage.AUDIO.value, ref,
                                   lambda: self.sa05.compose(bundle.script))
        self.db.set_stage(ref, Stage.SUBTITLES.value)
        bundle.subs = self._retry(
            Stage.SUBTITLES.value, ref,
            lambda: self.sa06.build(bundle.script, bundle.audio.path))
        self.db.set_stage(ref, Stage.METADATA.value)
        bundle.meta = self._retry(Stage.METADATA.value, ref,
                                  lambda: self.sa07.compose(bundle.script))

        # QA gate
        self.db.set_stage(ref, Stage.QA.value)
        bundle.qa = self.sa09.run_audit(
            script=bundle.script, video=bundle.video, audio=bundle.audio,
            subs=bundle.subs, meta=bundle.meta)
        if bundle.qa.passed:
            self.db.set_stage(ref, Stage.REVIEW.value)
            self._log("flagged_for_review", {"ref": ref}, episode_ref=ref)
        else:
            # route back: record which agents own the failed checks
            owners = sorted({self._owner(f.category) for f in bundle.qa.failures})
            self.db.set_stage(ref, Stage.FAILED.value,
                              {"qa_failures": [f.name for f in bundle.qa.failures],
                               "route_back_to": owners})
            self._log("qa_failed_routed_back",
                      {"ref": ref, "owners": owners}, episode_ref=ref, status="fail")
        return bundle

    @staticmethod
    def _owner(category: str) -> str:
        return {"video": "SA-04", "audio": "SA-05", "subtitles": "SA-06",
                "metadata": "SA-07", "continuity": "SA-01/SA-02"}.get(category, "MOA")

    # -- human review gate ---------------------------------------------------
    def review_queue(self) -> list[str]:
        return self.db.episodes_in_stage(Stage.REVIEW.value)

    def approve(self, ref: str) -> list[dict]:
        """Human approval signal → trigger publishing."""
        entry = self.db.get_queue_entry(ref)
        if not entry or entry["stage"] != Stage.REVIEW.value:
            raise ValueError(f"{ref} is not awaiting review (stage="
                             f"{entry['stage'] if entry else 'none'})")
        bundle = self._bundles[ref]
        self._log("human_approved", {"ref": ref}, episode_ref=ref)
        return self.sa08.publish(bundle.video, bundle.meta)

    def reject(self, ref: str, note: str = "") -> None:
        self.db.set_stage(ref, Stage.FAILED.value,
                          {"rejected": True, "reviewer_note": note})
        self._log("human_rejected", {"ref": ref, "note": note}, episode_ref=ref,
                  status="fail")

    def episode_summary(self, ref: str) -> dict:
        entry = self.db.get_queue_entry(ref) or {}
        b = self._bundles.get(ref)
        return {
            "ref": ref,
            "stage": entry.get("stage"),
            "title": getattr(b.script, "title", None) if b else None,
            "qa": entry.get("data", {}).get("qa_report"),
            "platforms": list(b.meta.platforms) if b and b.meta else [],
            "publish_records": entry.get("data", {}).get("publish_records", []),
        }
