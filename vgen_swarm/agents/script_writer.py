"""SA-03 Script Writer — scene-by-scene scripts with timestamps.

Builds a mobile-first episode (90-180s) with the mandated beats and weaves the
episode's seeded clue narratives into dialogue, so each clue is *experienced as
story* rather than presented as a puzzle. Emits the hidden clue manifest and the
emotional-beat timestamps SA-05 needs for BGM sync.
"""
from __future__ import annotations

from ..config import EPISODE_MIN_SEC, EPISODE_MAX_SEC
from ..models import Script, Scene
from .base import BaseAgent, AgentResult, QualityCheckError


class ScriptWriter(BaseAgent):
    agent_id = "SA-03"
    name = "Script Writer"

    def write(self, season: int, episode: int) -> Script:
        ref = f"S{season:02d}E{episode:02d}"
        outline = self.db.get_episode_outline(ref)
        if outline is None:
            raise QualityCheckError(f"no outline for {ref}")
        placements = self.db.clue_placements_for_episode(season, episode)
        clue_lines = [p["narrative_form"] for p in placements]
        clue_ids = [p["clue_id"] for p in placements]

        # LLM-enriched hook lines (fall back to templates offline). The clue beat
        # stays literal so the embedded logic survives verbatim.
        sys = ("You are SA-03, scriptwriter for a dark serialized mystery. Write a "
               "single line of taut spoken dialogue — no quotes, no stage "
               "directions, under 80 characters.")
        cold_line = self.prose(
            sys, f"Cold-open hook for '{outline['title']}': {outline['cold_open']}",
            "...he didn't fall. Someone was there.", episode_ref=ref)
        end_line = self.prose(
            sys, f"Ending cliffhanger line for '{outline['title']}': "
                 f"{outline['ending_hook']}",
            "Then you already know who lied.", episode_ref=ref)

        # Beat layout across a ~140s episode (within the 90-180s window).
        scenes = [
            Scene(0, outline["cold_open"], [cold_line],
                  0.0, 10.0, "tension-spike", "match_cut"),
            Scene(1, outline["main_scene"],
                  ["Walk me through it again — where were you?",
                   "Where I always am when the bell rings."],
                  10.0, 70.0, "simmer", "cut"),
            Scene(2, outline["clue_beat"], clue_lines or ["(a glance says enough)"],
                  70.0, 120.0, "reveal", "whip_pan"),
            Scene(3, outline["ending_hook"], [end_line],
                  120.0, 140.0, "cliff", "fade"),
        ]
        script = Script(season=season, episode=episode, title=outline["title"],
                        scenes=scenes, clue_manifest=clue_ids)

        dur = script.duration_sec
        if not (EPISODE_MIN_SEC <= dur <= EPISODE_MAX_SEC):
            raise QualityCheckError(
                f"{ref} duration {dur}s outside [{EPISODE_MIN_SEC},{EPISODE_MAX_SEC}]")

        self.log("write", _script_to_dict(script), episode_ref=ref,
                 detail={"scenes": len(scenes), "duration_sec": dur,
                         "clues": clue_ids})
        return script

    def run(self, season: int, episode: int) -> AgentResult:
        return AgentResult(self.agent_id, True, output=self.write(season, episode))


def _script_to_dict(s: Script) -> dict:
    return {"ref": s.ref, "title": s.title, "clue_manifest": s.clue_manifest,
            "scenes": [vars(sc) for sc in s.scenes]}
