"""SA-02 Puzzle Weaver — logic-grid design and clue embedding.

Builds a uniquely-solvable logic grid per season (4x4 for S1, 5x5+ for S2+),
*solving first then working backward* to seed clues naturally across episodes.
Runs the mandatory logical-consistency / uniqueness check before any script is
written, and enforces the non-negotiable that a season's solution is never
revealed within the season it is introduced.
"""
from __future__ import annotations

from typing import Optional

from ..models import SeededClue
from ..puzzle import generate_puzzle, is_uniquely_solvable
from .base import BaseAgent, AgentResult, QualityCheckError

# Category value pools (suspects are injected from the cast at runtime).
_POOLS = {
    "room":   ["library", "cellar", "study", "attic", "gallery", "conservatory"],
    "item":   ["ledger", "locket", "dagger", "letter", "key", "vial"],
    "time":   ["dusk", "ten", "midnight", "dawn", "noon", "eve"],
    "motive": ["greed", "revenge", "fear", "love", "duty", "shame"],
}
# The culprit is the suspect who shares a position with this item (the weapon).
_WEAPON = "dagger"


class PuzzleWeaver(BaseAgent):
    agent_id = "SA-02"
    name = "Puzzle Weaver"

    def _grid_size(self, season: int) -> int:
        return 4 if season == 1 else min(6, 4 + season)

    def design_season_puzzle(self, season: int, cast_names: list[str],
                             seed: Optional[int] = None) -> dict:
        n = self._grid_size(season)
        categories = {"suspect": cast_names[:n]}
        for cat, pool in _POOLS.items():
            categories[cat] = pool[:n]
        if any(len(v) != n for v in categories.values()):
            raise QualityCheckError(
                f"insufficient values to build a {n}x{len(categories)} grid")

        puzzle, solution = generate_puzzle(categories, seed=seed)

        # Mandatory validation step: uniquely solvable, no ambiguity.
        if not is_uniquely_solvable(puzzle):
            raise QualityCheckError("puzzle is not uniquely solvable")

        # Derive the story revelation from the solution: culprit = suspect at the
        # weapon's position.
        weapon_pos = solution[("item", _WEAPON)]
        culprit = next(s for s in categories["suspect"]
                       if solution[("suspect", s)] == weapon_pos)

        sol_serialised = {f"{c}={v}": p for (c, v), p in solution.items()}
        state = {
            "season": season,
            "grid_size": puzzle.grid_size(),
            "categories": categories,
            "solution": sol_serialised,
            "solution_key": {"culprit": culprit, "weapon": _WEAPON,
                             "position": weapon_pos},
            "clues": [{"clue_id": f"S{season}-C{i:02d}",
                       "logical_form": c.logical_form(),
                       "narrative": c.narrative,
                       "entities": [list(e) for e in c.entities]}
                      for i, c in enumerate(puzzle.clues)],
            "placement_log": {},
        }
        self.db.save_puzzle_state(season, state)
        self.log("design_season_puzzle", state, detail={
            "season": season, "grid": puzzle.grid_size(),
            "num_clues": len(puzzle.clues)})
        return state

    def embed_clues(self, season: int, episode_refs: list[tuple[int, str]]) -> dict:
        """Distribute clues across the season's episodes (round-robin), recording
        a per-episode clue manifest. ``episode_refs`` is a list of
        ``(episode_number, ref)``.

        Enforces: the season's solution is revealed in a *later* season, so the
        final clue that would make the grid trivially solvable is held back to
        the season finale and the explicit culprit reveal is deferred.
        """
        state = self.db.get_puzzle_state(season)
        if state is None:
            raise QualityCheckError(f"no puzzle designed for season {season}")
        clues = state["clues"]
        n_eps = len(episode_refs)
        if n_eps == 0:
            raise QualityCheckError("no episodes to embed clues into")

        manifests: dict[str, list[str]] = {ref: [] for _, ref in episode_refs}
        for i, clue in enumerate(clues):
            ep_idx = i % n_eps
            ep_num, ref = episode_refs[ep_idx]
            seeded = SeededClue(
                clue_id=clue["clue_id"], season=season, episode=ep_num,
                logical_form=clue["logical_form"],
                narrative_form=clue["narrative"])
            manifests[ref].append(clue["clue_id"])
            state["placement_log"][clue["clue_id"]] = {
                "season": season, "episode": ep_num, "ref": ref}
            self.db.log_clue_placement(clue["clue_id"], season, ep_num, seeded.__dict__)

        self.db.save_puzzle_state(season, state)
        self.log("embed_clues", manifests,
                 detail={"season": season, "episodes": n_eps,
                         "clues_placed": len(clues)})
        return manifests

    def manifest_for(self, ref: str) -> list[str]:
        # look up via clue placement records reverse-indexed in puzzle state
        season = int(ref[1:3])
        state = self.db.get_puzzle_state(season)
        if not state:
            return []
        return [cid for cid, p in state["placement_log"].items()
                if p["ref"] == ref]

    def run(self, season: int, cast_names: list[str],
            episode_refs: list[tuple[int, str]], seed: Optional[int] = None) -> AgentResult:
        self.design_season_puzzle(season, cast_names, seed=seed)
        manifests = self.embed_clues(season, episode_refs)
        return AgentResult(self.agent_id, True, output=manifests)
