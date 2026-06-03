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
    def _subs_with_translation(self, translation):
        from vgen_swarm.providers import default_mock_bundle
        cfg = SwarmConfig(workdir="build_output_test", db_path=":memory:",
                          audit_path="build_output_test/a.log")
        moa = MasterOrchestrator(default_mock_bundle(translation=translation),
                                 config=cfg, db=StateDB(":memory:"))
        moa.bootstrap_season(1, num_episodes=8, seed=7)
        script = moa.sa03.write(1, 1)
        audio = moa.sa05.compose(script)
        return moa, moa.sa06.build(script, audio.path)

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

    def test_translation_selected_when_deepseek_key_present(self):
        import os
        from vgen_swarm.providers import best_available_translation, LLMTranslation
        os.environ["DEEPSEEK_API_KEY"] = "sk-test"
        try:
            self.assertIsInstance(best_available_translation(), LLMTranslation)
        finally:
            del os.environ["DEEPSEEK_API_KEY"]

    def test_paraphrasing_backtranslation_does_not_false_fail(self):
        # back-translation that paraphrases (high overlap) must not raise
        class Paraphrase:
            live = True
            name = "paraphrase"
            def translate(self, text, target_lang):
                return f"<{target_lang}>{text}"
            def back_translate(self, text, source_lang):
                return text.split(">", 1)[-1] + " indeed"  # minor drift
        _, subs = self._subs_with_translation(Paraphrase())
        self.assertEqual(set(subs.tracks), set(SwarmConfig().languages))

    def test_broken_translation_is_caught(self):
        from vgen_swarm.agents.base import QualityCheckError
        class Broken:
            live = True
            name = "broken"
            def translate(self, text, target_lang):
                return "xx"
            def back_translate(self, text, source_lang):
                return "zzzzz unrelated garbage qqqq"  # ~0 overlap
        with self.assertRaises(QualityCheckError):
            self._subs_with_translation(Broken())


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

    def test_image_no_keys_falls_back_to_mock(self):
        import os
        from vgen_swarm.providers import best_available_image
        saved = {k: os.environ.pop(k, None)
                 for k in ("OPENAI_API_KEY", "TOGETHER_API_KEY")}
        try:
            self.assertEqual(type(best_available_image()).__name__, "MockImage")
        finally:
            os.environ.update({k: v for k, v in saved.items() if v is not None})

    def test_image_selected_when_key_present(self):
        import os
        from vgen_swarm.providers import best_available_image
        os.environ["OPENAI_API_KEY"] = "sk-test"
        try:
            img = best_available_image()
            self.assertEqual(img.name, "dall-e-3")  # wrapped real provider
        finally:
            del os.environ["OPENAI_API_KEY"]

    def test_image_fallback_on_api_error(self):
        # a real provider that raises must still yield a placeholder file
        import tempfile, os
        from vgen_swarm.providers.image import ImageWithFallback

        class Boom:
            name = "boom"
            def generate_image(self, prompt, out_path):
                raise RuntimeError("network down")
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "t.png")
            meta = ImageWithFallback(Boom()).generate_image("x", out)
            self.assertTrue(os.path.exists(out))
            self.assertIn("network down", meta["fallback_error"])

    def test_mock_llm_keeps_templates_via_prose_helper(self):
        # With a non-live LLM, agents must use deterministic fallback prose.
        moa = fresh_moa()
        moa.bootstrap_season(1, num_episodes=8, seed=7)
        universe = moa.db.get_universe()
        self.assertIn("estate", universe["setting"].lower())


class TestBudgetPipeline(unittest.TestCase):
    def test_budget_bundle_uses_slideshow_and_free_audio(self):
        from vgen_swarm.providers import (budget_bundle, SlideshowVideo,
                                          FreeMusic, FreeSFX)
        b = budget_bundle()
        self.assertIsInstance(b.video, SlideshowVideo)
        self.assertIsInstance(b.music, FreeMusic)
        self.assertIsInstance(b.sfx, FreeSFX)

    def test_full_mock_episode_estimate_is_zero(self):
        from vgen_swarm.cost import estimate_episode
        from vgen_swarm.providers import default_mock_bundle
        est = estimate_episode(default_mock_bundle(), duration_sec=140,
                               num_scenes=4, num_dialogue_lines=5,
                               num_languages=6, num_platforms=5)
        self.assertEqual(est.total, 0.0)

    def test_paid_video_estimate_is_large_and_shows_comparison(self):
        from vgen_swarm.cost import estimate_episode
        from vgen_swarm.providers import default_mock_bundle
        b = default_mock_bundle()
        class Veo: name = "veo3"
        b.video = Veo()
        est = estimate_episode(b, duration_sec=140, num_scenes=4,
                               num_dialogue_lines=5, num_languages=6,
                               num_platforms=5)
        self.assertAlmostEqual(est.total, 56.0, places=1)

    def test_budget_cap_blocks_expensive_episode(self):
        from vgen_swarm.cost import BudgetExceeded
        from vgen_swarm.providers import default_mock_bundle
        cfg = SwarmConfig(workdir="build_output_test", db_path=":memory:",
                          audit_path="build_output_test/a.log",
                          max_cost_per_episode=1.0)
        b = default_mock_bundle()
        class Veo: name = "veo3"
        b.video = Veo()
        moa = MasterOrchestrator(b, config=cfg, db=StateDB(":memory:"))
        moa.bootstrap_season(1, num_episodes=8, seed=7)
        with self.assertRaises(BudgetExceeded):
            moa.produce_episode(1, 1)
        entry = moa.db.get_queue_entry("S01E01")
        self.assertEqual(entry["stage"], Stage.FAILED.value)
        self.assertTrue(entry["data"]["budget_exceeded"])

    def test_budget_cap_allows_cheap_episode(self):
        cfg = SwarmConfig(workdir="build_output_test", db_path=":memory:",
                          audit_path="build_output_test/a.log",
                          max_cost_per_episode=1.0)
        moa = fresh_moa()
        moa.config = cfg
        moa.bootstrap_season(1, num_episodes=8, seed=7)
        ep = moa.produce_episode(1, 1)  # all-mock => $0 => under cap
        self.assertTrue(ep.qa.passed)


if __name__ == "__main__":
    unittest.main()
