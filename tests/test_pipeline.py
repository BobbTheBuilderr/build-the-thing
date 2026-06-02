"""Tests for orchestration, QA gating, continuity, metadata limits, subtitles."""
import unittest

from vgen_swarm.config import (PLATFORM_LIMITS, SUBTITLE_MAX_CHARS_PER_LINE,
                               SwarmConfig)
from vgen_swarm.models import Stage
from vgen_swarm.orchestrator import MasterOrchestrator
from vgen_swarm.providers import default_mock_bundle
from vgen_swarm.state.db import StateDB


def fresh_moa(tmp="build_output_test"):
    cfg = SwarmConfig(workdir=tmp, db_path=":memory:", audit_path=tmp + "/a.log")
    return MasterOrchestrator(default_mock_bundle(), config=cfg, db=StateDB(":memory:"))


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.moa = fresh_moa()
        self.moa.bootstrap_season(1, num_episodes=8, seed=7)

    def test_full_episode_passes_qa_and_reaches_review(self):
        bundle = self.moa.produce_episode(1, 1)
        self.assertTrue(bundle.qa.passed, [f.name for f in bundle.qa.failures])
        self.assertIn("S01E01", self.moa.review_queue())

    def test_approval_publishes_to_all_platforms_and_logs(self):
        self.moa.produce_episode(1, 1)
        records = self.moa.approve("S01E01")
        self.assertEqual({r["platform"] for r in records},
                         set(self.moa.config.platforms))
        logged = self.moa.db.publish_records("S01E01")
        self.assertEqual(len(logged), len(self.moa.config.platforms))
        # youtube publishes first so its URL can thread into the others
        self.assertEqual(records[0]["platform"], "youtube")

    def test_cannot_approve_before_review_stage(self):
        with self.assertRaises(ValueError):
            self.moa.approve("S01E99")

    def test_reject_moves_to_failed(self):
        self.moa.produce_episode(1, 1)
        self.moa.reject("S01E01", "reshoot the cold open")
        entry = self.moa.db.get_queue_entry("S01E01")
        self.assertEqual(entry["stage"], Stage.FAILED.value)
        self.assertEqual(entry["data"]["reviewer_note"], "reshoot the cold open")

    def test_clue_manifest_matches_tracker(self):
        bundle = self.moa.produce_episode(1, 1)
        check = next(c for c in bundle.qa.checks
                     if c.name == "clue_manifest_matches_tracker")
        self.assertTrue(check.passed)

    def test_solution_not_revealed_in_same_season(self):
        # every clue for season 1 stays in season 1; the culprit reveal is deferred
        state = self.moa.db.get_puzzle_state(1)
        self.assertTrue(all(p["season"] == 1 for p in state["placement_log"].values()))
        self.assertIn("culprit", state["solution_key"])


class TestQAGating(unittest.TestCase):
    def test_qa_failure_blocks_review_and_routes_back(self):
        moa = fresh_moa()
        moa.bootstrap_season(1, num_episodes=8, seed=7)
        # corrupt the video so QA must fail on aspect ratio
        orig = moa.sa04.render

        def bad_render(script, cast_names):
            art = orig(script, cast_names)
            art.aspect_ratio = "16:9"
            return art
        moa.sa04.render = bad_render
        bundle = moa.produce_episode(1, 1)
        self.assertFalse(bundle.qa.passed)
        self.assertNotIn("S01E01", moa.review_queue())
        entry = moa.db.get_queue_entry("S01E01")
        self.assertEqual(entry["stage"], Stage.FAILED.value)
        self.assertIn("SA-04", entry["data"]["route_back_to"])


class TestMetadataLimits(unittest.TestCase):
    def test_all_platforms_within_limits(self):
        moa = fresh_moa()
        moa.bootstrap_season(1, num_episodes=8, seed=7)
        script = moa.sa03.write(1, 1)
        pkg = moa.sa07.compose(script)
        for platform, pm in pkg.platforms.items():
            lim = PLATFORM_LIMITS[platform]
            lo, hi = lim["hashtags"]
            self.assertLessEqual(len(pm.title), lim["title"], platform)
            self.assertLessEqual(len(pm.caption), lim["caption"], platform)
            self.assertTrue(lo <= len(pm.hashtags) <= hi, platform)


class TestSubtitles(unittest.TestCase):
    def test_line_length_and_languages(self):
        moa = fresh_moa()
        moa.bootstrap_season(1, num_episodes=8, seed=7)
        script = moa.sa03.write(1, 1)
        audio = moa.sa05.compose(script)
        subs = moa.sa06.build(script, audio.path)
        self.assertEqual(set(subs.tracks), set(moa.config.languages))
        self.assertTrue(subs.tracks["ar"].rtl)
        for track in subs.tracks.values():
            for cue in track.cues:
                for line in cue["text"].split("\n"):
                    self.assertLessEqual(len(line), SUBTITLE_MAX_CHARS_PER_LINE)


class TestLLMSelection(unittest.TestCase):
    def test_no_keys_falls_back_to_mock(self):
        import os
        from vgen_swarm.providers import best_available_llm
        saved = {k: os.environ.pop(k, None)
                 for k in ("DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY")}
        try:
            llm = best_available_llm()
            self.assertEqual(type(llm).__name__, "MockLLM")
            self.assertFalse(getattr(llm, "live", False))
        finally:
            os.environ.update({k: v for k, v in saved.items() if v is not None})

    def test_deepseek_selected_when_key_present(self):
        import os
        from vgen_swarm.providers import best_available_llm, DeepSeekLLM
        os.environ["DEEPSEEK_API_KEY"] = "sk-test"
        try:
            llm = best_available_llm()
            self.assertIsInstance(llm, DeepSeekLLM)
            self.assertTrue(llm.live)
        finally:
            del os.environ["DEEPSEEK_API_KEY"]

    def test_mock_llm_keeps_templates_via_prose_helper(self):
        # With a non-live LLM, agents must use deterministic fallback prose.
        moa = fresh_moa()
        moa.bootstrap_season(1, num_episodes=8, seed=7)
        universe = moa.db.get_universe()
        self.assertIn("estate", universe["setting"].lower())


if __name__ == "__main__":
    unittest.main()
