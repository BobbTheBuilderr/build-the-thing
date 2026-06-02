"""SA-01 Story Architect — universe building, season arcs, episode outlines.

Generates a self-contained mystery universe with a named cast, plans at least
three seasons before Season 1 is written (continuity guarantee), and emits
episode outlines with the mandated beat structure (cold open / main scene /
clue beat / ending hook). When a real LLM is configured it is used to enrich
prose; offline it falls back to deterministic, structurally-valid content.
"""
from __future__ import annotations

from ..models import Universe, Character, SeasonArc, EpisodeOutline
from .base import BaseAgent, AgentResult

MIN_SEASONS_PLANNED = 3
MIN_EPISODES, MAX_EPISODES = 8, 12

# Cast doubles as the puzzle's "suspect" category, so solving the grid names a
# real character. Roles/traits give the writer and video director material.
_CAST = [
    ("Vega", "investigator", ["relentless", "guarded"], "find her vanished sister"),
    ("Cohen", "archivist", ["meticulous", "evasive"], "protect the estate's secrets"),
    ("Mara", "heir", ["charming", "indebted"], "secure the inheritance"),
    ("Okafor", "groundskeeper", ["loyal", "observant"], "keep an old promise"),
    ("Reyes", "physician", ["calm", "calculating"], "bury a past mistake"),
]


class StoryArchitect(BaseAgent):
    agent_id = "SA-01"
    name = "Story Architect"

    def build_universe(self, cast_size: int = 5) -> Universe:
        cast_size = max(4, min(8, cast_size))
        cast = [Character(name=n, role=r, traits=t, motivation=m,
                          appearance_anchor=f"{n}: see visual bible")
                for (n, r, t, m) in _CAST[:cast_size]]
        universe = Universe(
            title="The Ashford Inheritance",
            genre="mystery",
            setting="A storm-cut island estate where five guests are trapped the "
                    "night the patriarch dies.",
            central_conflict="One guest is responsible for the death; the truth is "
                             "hidden in where everyone was, what they held, and why.",
            tone="Dark, intelligent, emotionally charged — built for replay and debate.",
            cast=cast,
        )
        self.db.save_universe(universe.to_dict())
        self.log("build_universe", universe.to_dict())
        return universe

    def plan_seasons(self, total: int = MIN_SEASONS_PLANNED) -> list[SeasonArc]:
        total = max(MIN_SEASONS_PLANNED, total)
        arcs: list[SeasonArc] = []
        for s in range(1, total + 1):
            if s == 1:
                summary = "Introduce the island, the guests, and the night of the death."
                revelation = "Who was where, and what each guest was holding."
            else:
                summary = f"Escalation layer {s - 1}: motives surface and alibis crack."
                revelation = f"Season {s} exposes the deeper conspiracy behind the death."
            arcs.append(SeasonArc(
                season=s, summary=summary, revelation=revelation,
                cliffhanger=f"A new contradiction reframes everything as Season {s} closes.",
                num_episodes=MIN_EPISODES))
            self.db.save_season_arc(s, arcs[-1].__dict__)
        self.log("plan_seasons", [a.__dict__ for a in arcs])
        return arcs

    def outline_episodes(self, season: int, num_episodes: int) -> list[EpisodeOutline]:
        num_episodes = max(MIN_EPISODES, min(MAX_EPISODES, num_episodes))
        outlines: list[EpisodeOutline] = []
        for ep in range(1, num_episodes + 1):
            o = EpisodeOutline(
                season=season, episode=ep,
                title=f"S{season} E{ep}: The {ep}th Hour",
                logline=f"A fragment of the night surfaces; one more contradiction lands.",
                cold_open="A flash of the storm and a half-heard accusation (0-10s).",
                main_scene="Two guests revisit the hour before the death, stories diverging.",
                clue_beat="An overheard line or seen object encodes a logical fact.",
                ending_hook="A held look implies someone just lied.",
            )
            self.db.save_episode_outline(o.ref, season, ep, o.__dict__)
            outlines.append(o)
        self.log("outline_episodes", [o.__dict__ for o in outlines],
                 detail={"season": season, "count": len(outlines)})
        return outlines

    def run(self, seasons: int = MIN_SEASONS_PLANNED) -> AgentResult:
        universe = self.build_universe()
        arcs = self.plan_seasons(seasons)
        return AgentResult(self.agent_id, True,
                           output={"universe": universe.to_dict(),
                                   "seasons": [a.__dict__ for a in arcs]})
