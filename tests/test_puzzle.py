"""Tests for the logic-grid engine: solver correctness, uniqueness, generation."""
import unittest

from vgen_swarm.puzzle import (Puzzle, generate_puzzle, solve, count_solutions,
                               is_uniquely_solvable, same_entity, at_position,
                               immediately_left, different_entity)
from vgen_swarm.puzzle.grid import ClueType


CATS4 = {
    "suspect": ["Vega", "Cohen", "Mara", "Okafor"],
    "room": ["library", "cellar", "study", "attic"],
    "item": ["ledger", "locket", "dagger", "letter"],
    "time": ["dusk", "midnight", "dawn", "noon"],
}
CATS5 = {
    "suspect": ["Vega", "Cohen", "Mara", "Okafor", "Reyes"],
    "room": ["library", "cellar", "study", "attic", "gallery"],
    "item": ["ledger", "locket", "dagger", "letter", "key"],
    "time": ["dusk", "midnight", "dawn", "noon", "eve"],
    "motive": ["greed", "revenge", "fear", "love", "duty"],
}


class TestSolver(unittest.TestCase):
    def test_classic_underdetermined_has_many_solutions(self):
        # only one weak clue -> definitely not unique
        p = Puzzle(4, CATS4, [different_entity(("suspect", "Vega"), ("room", "attic"))])
        self.assertGreater(count_solutions(p, limit=2), 1)

    def test_unsatisfiable_returns_none(self):
        p = Puzzle(4, CATS4, [
            at_position(("suspect", "Vega"), 0),
            at_position(("suspect", "Vega"), 1),  # contradiction
        ])
        self.assertIsNone(solve(p))
        self.assertEqual(count_solutions(p), 0)

    def test_solution_satisfies_all_constraints(self):
        p, sol = generate_puzzle(CATS4, seed=3)
        self.assertTrue(p.verify_solution(sol))
        found = solve(p)
        self.assertIsNotNone(found)
        self.assertTrue(p.verify_solution(found))

    def test_immediately_left_semantics(self):
        p = Puzzle(4, CATS4, [
            at_position(("suspect", "Vega"), 0),
            immediately_left(("suspect", "Vega"), ("suspect", "Cohen")),
        ])
        sol = solve(p)
        self.assertEqual(sol[("suspect", "Cohen")], 1)


class TestGeneratorUniqueness(unittest.TestCase):
    def test_generated_puzzles_are_unique_4x4(self):
        for seed in range(12):
            p, sol = generate_puzzle(CATS4, seed=seed)
            self.assertTrue(is_uniquely_solvable(p), f"seed {seed} not unique")
            self.assertEqual(count_solutions(p, limit=3), 1)

    def test_generated_puzzles_are_unique_5x5(self):
        for seed in range(4):
            p, sol = generate_puzzle(CATS5, seed=seed)
            self.assertTrue(is_uniquely_solvable(p), f"seed {seed} not unique")

    def test_clue_set_is_irreducible(self):
        # removing any clue must break uniqueness
        p, _ = generate_puzzle(CATS4, seed=5)
        for i in range(len(p.clues)):
            reduced = Puzzle(p.n, p.categories, p.clues[:i] + p.clues[i + 1:])
            self.assertFalse(is_uniquely_solvable(reduced),
                             f"clue {i} was redundant; set not minimal")

    def test_every_clue_has_narrative(self):
        p, _ = generate_puzzle(CATS4, seed=1)
        for c in p.clues:
            self.assertTrue(c.narrative, c.logical_form())


if __name__ == "__main__":
    unittest.main()
