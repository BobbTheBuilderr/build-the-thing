"""Backtracking CSP solver with uniqueness detection.

Solves logic-grid puzzles via MRV (minimum-remaining-values) variable ordering
plus forward checking. ``count_solutions(limit=2)`` lets the generator and the
puzzle-validation step assert a puzzle is *uniquely* solvable (the spec forbids
ambiguous solutions).
"""
from __future__ import annotations

from typing import Iterator, Optional

from .grid import Puzzle, Clue, ClueType, Entity, PosMap


def _allowed_positions(clue: Clue, known: Entity, known_pos: int,
                       other: Entity, n: int) -> set[int]:
    """Positions ``other`` may take given ``known`` sits at ``known_pos``."""
    rng = range(n)
    if clue.ctype is ClueType.SAME:
        return {known_pos}
    if clue.ctype is ClueType.DIFFERENT:
        return {p for p in rng if p != known_pos}
    if clue.ctype is ClueType.ADJACENT:
        return {p for p in (known_pos - 1, known_pos + 1) if 0 <= p < n}
    if clue.ctype is ClueType.IMMEDIATELY_LEFT:
        # pos(a) + 1 == pos(b)
        if known == clue.a:
            return {known_pos + 1} & set(rng)
        return {known_pos - 1} & set(rng)
    if clue.ctype is ClueType.LEFT_OF:
        # pos(a) < pos(b)
        if known == clue.a:
            return {p for p in rng if p > known_pos}
        return {p for p in rng if p < known_pos}
    raise ValueError(f"non-binary clue in propagation: {clue.ctype}")


class _Solver:
    def __init__(self, puzzle: Puzzle, limit: int) -> None:
        self.p = puzzle
        self.n = puzzle.n
        self.limit = limit
        # entity -> set of candidate positions
        self.domains: dict[Entity, set[int]] = {
            e: set(range(self.n)) for e in puzzle.entities
        }
        # index binary clues by entity for fast forward-checking
        self.binary_by_entity: dict[Entity, list[Clue]] = {}
        self.solutions: list[PosMap] = []
        self._apply_unary()
        # group entities by category for the all-different rule
        self.siblings: dict[Entity, list[Entity]] = {}
        for cat, vals in puzzle.categories.items():
            ents = [(cat, v) for v in vals]
            for e in ents:
                self.siblings[e] = [o for o in ents if o != e]
        for c in puzzle.clues:
            if c.ctype is ClueType.AT_POSITION:
                continue
            for e in c.entities:
                self.binary_by_entity.setdefault(e, []).append(c)

    def _apply_unary(self) -> None:
        for c in self.p.clues:
            if c.ctype is ClueType.AT_POSITION:
                self.domains[c.a] &= {c.position}

    def solve(self) -> list[PosMap]:
        assignment: PosMap = {}
        self._backtrack(assignment, {e: set(d) for e, d in self.domains.items()})
        return self.solutions

    def _backtrack(self, assignment: PosMap, domains: dict[Entity, set[int]]) -> None:
        if len(self.solutions) >= self.limit:
            return
        unassigned = [e for e in domains if e not in assignment]
        if not unassigned:
            if self.p.verify_solution(assignment):
                self.solutions.append(dict(assignment))
            return
        # MRV: choose the most constrained variable
        entity = min(unassigned, key=lambda e: len(domains[e]))
        if not domains[entity]:
            return
        for pos in sorted(domains[entity]):
            new_dom = {e: set(d) for e, d in domains.items()}
            new_dom[entity] = {pos}
            assignment[entity] = pos
            if self._forward_check(entity, pos, assignment, new_dom):
                self._backtrack(assignment, new_dom)
            del assignment[entity]
            if len(self.solutions) >= self.limit:
                return

    def _forward_check(self, entity: Entity, pos: int,
                       assignment: PosMap, domains: dict[Entity, set[int]]) -> bool:
        # all-different within category
        for sib in self.siblings[entity]:
            if sib in assignment:
                continue
            domains[sib].discard(pos)
            if not domains[sib]:
                return False
        # binary clue propagation
        for clue in self.binary_by_entity.get(entity, ()):
            other = clue.b if clue.a == entity else clue.a
            if other is None or other in assignment:
                continue
            allowed = _allowed_positions(clue, entity, pos, other, self.n)
            domains[other] &= allowed
            if not domains[other]:
                return False
        return True


def solve(puzzle: Puzzle) -> Optional[PosMap]:
    """Return one solution, or ``None`` if unsatisfiable."""
    sols = _Solver(puzzle, limit=1).solve()
    return sols[0] if sols else None


def count_solutions(puzzle: Puzzle, limit: int = 2) -> int:
    """Count solutions up to ``limit`` (cheap uniqueness probe)."""
    return len(_Solver(puzzle, limit=limit).solve())


def is_uniquely_solvable(puzzle: Puzzle) -> bool:
    """True iff the puzzle has exactly one solution."""
    return count_solutions(puzzle, limit=2) == 1
