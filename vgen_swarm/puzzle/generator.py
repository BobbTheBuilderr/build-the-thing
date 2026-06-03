"""Generate uniquely-solvable logic-grid puzzles.

Strategy (matches SA-02's spec: *solve first, embed clues backward*):

1. Choose a random full solution over the supplied categories.
2. Enumerate clues that are **true** for that solution.
3. Start from a clue set that fully determines the grid, then greedily drop
   clues while the puzzle stays uniquely solvable — yielding an *irreducible*
   minimal clue set with no ambiguous solutions.
"""
from __future__ import annotations

import random
from typing import Optional

from .grid import (
    Puzzle, Clue, ClueType, Entity,
    same_entity, different_entity, at_position, immediately_left, adjacent, left_of,
)
from .solver import is_uniquely_solvable


def _ordinal(i: int) -> str:
    return {0: "first", 1: "second", 2: "third", 3: "fourth",
            4: "fifth", 5: "sixth"}.get(i, f"{i + 1}th")


def _narrate(clue: Clue, pos: dict[Entity, int]) -> str:
    (ca, va) = clue.a
    if clue.ctype is ClueType.AT_POSITION:
        return f"The one who is {va} stands in the {_ordinal(clue.position)} place."
    (cb, vb) = clue.b  # type: ignore[misc]
    if clue.ctype is ClueType.SAME:
        return f"Whoever is {va} is also {vb}."
    if clue.ctype is ClueType.DIFFERENT:
        return f"The {va} one is never the {vb} one."
    if clue.ctype is ClueType.IMMEDIATELY_LEFT:
        return f"The {va} one stands directly before the {vb} one."
    if clue.ctype is ClueType.ADJACENT:
        return f"The {va} one and the {vb} one stand side by side."
    if clue.ctype is ClueType.LEFT_OF:
        return f"The {va} one comes somewhere before the {vb} one."
    return clue.logical_form()


def _candidate_clues(categories: dict[str, list[str]], pos: dict[Entity, int],
                     rng: random.Random) -> list[Clue]:
    """All (or sampled) clues that hold for the chosen solution."""
    cats = list(categories)
    entities = [(c, v) for c in cats for v in categories[c]]
    clues: list[Clue] = []

    # cross-category pairwise relations
    for i, a in enumerate(entities):
        for b in entities[i + 1:]:
            if a[0] == b[0]:
                continue  # same category -> always DIFFERENT, uninformative
            pa, pb = pos[a], pos[b]
            if pa == pb:
                clues.append(same_entity(a, b))
            else:
                # keep a sampling of the (many) DIFFERENT/LEFT_OF facts
                if rng.random() < 0.30:
                    clues.append(different_entity(a, b))
                if abs(pa - pb) == 1:
                    lo, hi = (a, b) if pa < pb else (b, a)
                    clues.append(immediately_left(lo, hi))
                    clues.append(adjacent(a, b))
                if rng.random() < 0.25:
                    lo, hi = (a, b) if pa < pb else (b, a)
                    clues.append(left_of(lo, hi))

    # a couple of positional anchors
    for a in rng.sample(entities, k=min(2, len(entities))):
        clues.append(at_position(a, pos[a]))

    for c in clues:
        c.narrative = _narrate(c, pos)
    rng.shuffle(clues)
    return clues


def generate_puzzle(
    categories: dict[str, list[str]],
    *,
    seed: Optional[int] = None,
) -> tuple[Puzzle, dict[Entity, int]]:
    """Return ``(puzzle, solution)`` where ``puzzle`` is uniquely solvable and
    its clue set is irreducible (removing any clue breaks uniqueness)."""
    rng = random.Random(seed)
    n = len(next(iter(categories.values())))
    for cat, vals in categories.items():
        if len(vals) != n:
            raise ValueError("all categories must have the same number of values")

    # 1. random solution
    pos: dict[Entity, int] = {}
    for cat, vals in categories.items():
        perm = list(range(n))
        rng.shuffle(perm)
        for v, p in zip(vals, perm):
            pos[(cat, v)] = p

    # 2. candidate true clues, guaranteed to over-determine via SAME links
    candidates = _candidate_clues(categories, pos, rng)
    # ensure full determination: add the complete SAME chain to position 0 anchor
    anchor_cat = next(iter(categories))
    for cat in list(categories)[1:]:
        for v_anchor in categories[anchor_cat]:
            p = pos[(anchor_cat, v_anchor)]
            partner = next(v for v in categories[cat] if pos[(cat, v)] == p)
            link = same_entity((anchor_cat, v_anchor), (cat, partner))
            link.narrative = _narrate(link, pos)
            candidates.append(link)

    full = Puzzle(n=n, categories=categories, clues=list(candidates))
    if not is_uniquely_solvable(full):
        raise RuntimeError("generation invariant violated: full clue set not unique")

    # 3. minimise: drop clues while the puzzle stays uniquely solvable
    kept: list[Clue] = list(candidates)
    rng.shuffle(kept)
    i = 0
    while i < len(kept):
        trial = kept[:i] + kept[i + 1:]
        if is_uniquely_solvable(Puzzle(n=n, categories=categories, clues=trial)):
            kept = trial            # clue is redundant
        else:
            i += 1                  # clue is load-bearing, keep it
    rng.shuffle(kept)
    return Puzzle(n=n, categories=categories, clues=kept), pos
