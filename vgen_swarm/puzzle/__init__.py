"""Einstein-riddle / Zebra-puzzle engine.

The puzzle is the structural story engine for VGEN-SWARM (SA-02). This package
provides:

* :mod:`grid`      — the constraint model (entities, categories, clue types).
* :mod:`solver`    — a backtracking CSP solver with **uniqueness detection**.
* :mod:`generator` — generates a randomly chosen solution, derives a clue set,
  and minimises it to a *uniquely solvable* puzzle (no ambiguous solutions).
"""
from .grid import (
    Puzzle, Clue, ClueType,
    same_entity, different_entity, at_position,
    immediately_left, adjacent, left_of,
)
from .solver import solve, count_solutions, is_uniquely_solvable
from .generator import generate_puzzle

__all__ = [
    "Puzzle", "Clue", "ClueType",
    "same_entity", "different_entity", "at_position",
    "immediately_left", "adjacent", "left_of",
    "solve", "count_solutions", "is_uniquely_solvable",
    "generate_puzzle",
]
