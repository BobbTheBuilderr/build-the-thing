"""Logic-grid constraint model.

A puzzle has ``N`` ordered positions (0..N-1) and ``M`` categories. Each
category has exactly ``N`` distinct values, one per position. An *entity* is a
``(category, value)`` pair; solving means assigning each entity a position such
that within every category the positions form a permutation and all clues hold.

Clues are expressed against entities so the narrative layer (SA-02) can render
``("house", "red") not_same ("pet", "fish")`` as on-screen dialogue while the
solver reasons over the logical form.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

Entity = tuple[str, str]          # (category, value)
PosMap = dict[Entity, int]        # entity -> position


class ClueType(str, Enum):
    SAME = "same_entity"          # A and B occupy the same position
    DIFFERENT = "different_entity"
    AT_POSITION = "at_position"   # A is at a fixed position
    IMMEDIATELY_LEFT = "immediately_left"   # pos(A) + 1 == pos(B)
    ADJACENT = "adjacent"         # |pos(A) - pos(B)| == 1
    LEFT_OF = "left_of"           # pos(A) < pos(B)


@dataclass
class Clue:
    ctype: ClueType
    a: Entity
    b: Optional[Entity] = None
    position: Optional[int] = None
    # filled in by the narrative layer; not used by the solver
    narrative: str = ""

    @property
    def entities(self) -> tuple[Entity, ...]:
        return (self.a,) if self.b is None else (self.a, self.b)

    def holds(self, pos: PosMap) -> bool:
        """Evaluate the clue given a *complete-enough* position map.

        Caller guarantees every entity referenced by the clue is present.
        """
        pa = pos[self.a]
        if self.ctype is ClueType.AT_POSITION:
            return pa == self.position
        pb = pos[self.b]            # type: ignore[index]
        if self.ctype is ClueType.SAME:
            return pa == pb
        if self.ctype is ClueType.DIFFERENT:
            return pa != pb
        if self.ctype is ClueType.IMMEDIATELY_LEFT:
            return pa + 1 == pb
        if self.ctype is ClueType.ADJACENT:
            return abs(pa - pb) == 1
        if self.ctype is ClueType.LEFT_OF:
            return pa < pb
        raise ValueError(f"unknown clue type {self.ctype}")

    def logical_form(self) -> str:
        a = f"{self.a[0]}={self.a[1]}"
        if self.ctype is ClueType.AT_POSITION:
            return f"{self.ctype.value}({a}, pos={self.position})"
        b = f"{self.b[0]}={self.b[1]}"     # type: ignore[index]
        return f"{self.ctype.value}({a}, {b})"


# --- ergonomic constructors --------------------------------------------------
def same_entity(a: Entity, b: Entity, narrative: str = "") -> Clue:
    return Clue(ClueType.SAME, a, b, narrative=narrative)


def different_entity(a: Entity, b: Entity, narrative: str = "") -> Clue:
    return Clue(ClueType.DIFFERENT, a, b, narrative=narrative)


def at_position(a: Entity, position: int, narrative: str = "") -> Clue:
    return Clue(ClueType.AT_POSITION, a, position=position, narrative=narrative)


def immediately_left(a: Entity, b: Entity, narrative: str = "") -> Clue:
    return Clue(ClueType.IMMEDIATELY_LEFT, a, b, narrative=narrative)


def adjacent(a: Entity, b: Entity, narrative: str = "") -> Clue:
    return Clue(ClueType.ADJACENT, a, b, narrative=narrative)


def left_of(a: Entity, b: Entity, narrative: str = "") -> Clue:
    return Clue(ClueType.LEFT_OF, a, b, narrative=narrative)


@dataclass
class Puzzle:
    """A logic-grid puzzle definition (categories + clues), independent of any
    particular solution."""
    n: int                                   # positions per category
    categories: dict[str, list[str]]         # category -> N distinct values
    clues: list[Clue] = field(default_factory=list)

    def __post_init__(self) -> None:
        for cat, values in self.categories.items():
            if len(values) != self.n:
                raise ValueError(
                    f"category {cat!r} has {len(values)} values, expected {self.n}")
            if len(set(values)) != self.n:
                raise ValueError(f"category {cat!r} has duplicate values")

    @property
    def entities(self) -> list[Entity]:
        return [(c, v) for c, vs in self.categories.items() for v in vs]

    def grid_size(self) -> str:
        return f"{self.n}x{len(self.categories)}"

    def verify_solution(self, pos: PosMap) -> bool:
        """True iff ``pos`` is a valid full solution satisfying every clue and
        the all-different-within-category rule."""
        for cat, values in self.categories.items():
            seen = {pos[(cat, v)] for v in values}
            if seen != set(range(self.n)):
                return False
        return all(c.holds(pos) for c in self.clues)
