#!/usr/bin/env python3
"""End-to-end VGEN-SWARM demo: run Season 1 Episode 1 through the full pipeline.

Uses offline mock providers, so it runs with no API keys or network. Prints the
state-machine progression, the QA report, simulates the single human approval
signal, and shows the resulting (mock) publish records.

    python3 run_demo.py            # run S1E1
    python3 run_demo.py --serve    # also start the review dashboard
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from vgen_swarm.config import SwarmConfig
from vgen_swarm.orchestrator import MasterOrchestrator
from vgen_swarm.providers import (best_available_image, best_available_llm,
                                  best_available_translation, default_mock_bundle)
from vgen_swarm.state.db import StateDB


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true",
                    help="start the human review dashboard after producing")
    ap.add_argument("--no-approve", action="store_true",
                    help="leave the episode in the review queue instead of approving")
    ap.add_argument("--budget", action="store_true",
                    help="use the budget pipeline: ffmpeg slideshow video + free "
                         "audio (no per-second video billing)")
    ap.add_argument("--cap", type=float, default=None,
                    help="hard per-episode cost cap in USD (blocks generation above it)")
    args = ap.parse_args()

    workdir = Path("build_output")
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)

    config = SwarmConfig(workdir=str(workdir), db_path=":memory:",
                         audit_path=str(workdir / "audit.log"),
                         max_cost_per_episode=args.cap)
    # Real services where a key is set (DeepSeek prose/translation, DALL-E/FLUX
    # thumbnails); everything else mocked, or the free slideshow under --budget.
    if args.budget:
        from vgen_swarm.providers import budget_bundle, ffmpeg_available
        bundle = budget_bundle()
        llm, image, translation = bundle.llm, bundle.image, bundle.translation
        print(f"Video provider      : slideshow "
              f"({'ffmpeg LIVE' if ffmpeg_available() else 'ffmpeg missing → placeholder'})")
        print("Audio provider      : free music + SFX (synth/library)")
    else:
        llm = best_available_llm()
        image = best_available_image()
        translation = best_available_translation()
        bundle = default_mock_bundle(llm=llm, image=image, translation=translation)
    img_live = type(image).__name__ != "MockImage"
    tr_live = getattr(translation, "live", False)
    print(f"LLM provider        : {type(llm).__name__} "
          f"(prose {'LIVE' if getattr(llm, 'live', False) else 'templated/offline'})")
    print(f"Image provider      : {getattr(image, 'name', type(image).__name__)} "
          f"({'LIVE' if img_live else 'mock placeholder'})")
    print(f"Translation provider: {getattr(translation, 'name', type(translation).__name__)} "
          f"({'LIVE' if tr_live else 'mock'})")
    moa = MasterOrchestrator(bundle, config=config, db=StateDB(":memory:"))

    print("=" * 64)
    print("VGEN-SWARM — Season 1 bootstrap (universe → puzzle → outlines)")
    print("=" * 64)
    moa.bootstrap_season(1, num_episodes=8, seed=7)
    ps = moa.db.get_puzzle_state(1)
    uni = moa.db.get_universe()
    print(f"  Universe : {uni['title']}")
    print(f"  Setting  : {uni['setting']}")
    print(f"  Conflict : {uni['central_conflict']}")
    print(f"  Puzzle   : {ps['grid_size']} grid, {len(ps['clues'])} clues "
          f"(uniquely solvable)")
    print(f"  Solution : culprit = {ps['solution_key']['culprit']} "
          f"(held for a later season per spec)")

    print("\n" + "=" * 64)
    print("Producing S01E01 through the pipeline")
    print("=" * 64)
    from vgen_swarm.cost import BudgetExceeded
    try:
        ep = moa.produce_episode(1, 1)
    except BudgetExceeded as exc:
        print(f"  BLOCKED: {exc}")
        return
    print(f"  Cold open: {ep.script.scenes[0].dialogue[0]}")
    print(f"  Cliffhanger: {ep.script.scenes[-1].dialogue[0]}")
    thumb = next(iter(ep.meta.platforms.values())).thumbnail_path
    print(f"  Thumbnail: {thumb}")
    print(f"  Video: {ep.video.path}")
    for lang in ("zh-Hans", "ar", "es"):
        track = ep.subs.tracks.get(lang)
        if track and track.cues:
            sample = track.cues[0]["text"].replace("\n", " ")
            print(f"  Subtitle [{lang}]: {sample}")

    print("\n" + ep.cost_estimate.format())
    bundle = ep  # downstream review/approve uses the episode bundle

    print(f"\nQA report for {bundle.ref}: "
          f"{'PASS ✅' if bundle.qa.passed else 'FAIL ❌'}")
    for c in bundle.qa.checks:
        mark = "✓" if c.passed else "✗"
        print(f"  [{mark}] {c.category:10s} {c.name}"
              f"{('  — ' + c.detail) if c.detail else ''}")

    print(f"\nReview queue: {moa.review_queue()}")

    if args.no_approve:
        print("Leaving episode in review queue (--no-approve).")
    elif bundle.qa.passed:
        print("\nSimulating human APPROVAL signal → publishing…")
        records = moa.approve(bundle.ref)
        for r in records:
            print(f"  → {r['platform']:10s} {r['url']}  (scheduled +{int(r['scheduled_ts'])%100000}s)")
        print("\nPublish log:")
        for rec in moa.db.publish_records(bundle.ref):
            print(f"  {rec['platform']:10s} post_id={rec['post_id']}")

    print(f"\nAudit entries recorded: {len(moa.audit.entries)} "
          f"(each with timestamp + output hash)")

    if args.serve:
        from vgen_swarm.review import ReviewServer
        # re-produce a second episode so there is something to review live
        moa.produce_episode(1, 2)
        ReviewServer(moa).serve_forever()


if __name__ == "__main__":
    main()
