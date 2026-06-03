# VGEN-SWARM

An autonomous, multi-agent short-form video production pipeline implementing the
**VGEN-SWARM v1.0** spec: a swarm of nine specialised agents coordinated by a
Master Orchestrator that takes a serialized, puzzle-driven mystery from universe
design all the way to multi-platform publishing — with a human acting only as
the final approve/reject gate.

> **What's real vs. mocked.** The deterministic core is implemented for real and
> tested: the Einstein/Zebra **logic-grid engine** (generator + constraint
> solver + uniqueness validator), the **orchestration state machine** with retry
> and QA-gating, the **QA auditor**, **per-platform metadata/character-limit**
> logic, **subtitle spec** enforcement, continuity tracking, and the full
> **state/persistence** layer. Every external AI / social service (Runway, Kling,
> Pika, Suno, Udio, ElevenLabs, Whisper, DeepL, Flux/DALL-E, and the five social
> platforms) sits behind a **provider interface** with a working **offline mock**,
> so the entire pipeline runs and is testable with **no API keys and no
> network**. Going live means dropping real adapters into
> `vgen_swarm/providers/` — the orchestration, QA, and continuity logic stays
> unchanged.

## Quickstart

No dependencies required (standard library only).

```bash
# Run Season 1 Episode 1 through the full pipeline (offline mocks)
python3 run_demo.py

# Run the test suite (puzzle uniqueness, QA gating, continuity, limits, subs)
python3 -m unittest discover -s tests -v

# Produce two episodes and open the human review dashboard
python3 run_demo.py --serve     # → http://127.0.0.1:8765/
```

## Architecture

```
MasterOrchestrator (MOA)            vgen_swarm/orchestrator.py
├─ SA-01 Story Architect            agents/story_architect.py   universe, seasons, outlines
├─ SA-02 Puzzle Weaver              agents/puzzle_weaver.py     grid design + clue embedding
├─ SA-03 Script Writer              agents/script_writer.py     timestamped scenes + clue manifest
├─ SA-04 Video Director             agents/video_director.py    9:16 prompts, visual bible, retries
├─ SA-05 Audio Composer             agents/audio_composer.py    BGM brief, motif, SFX, -14 LUFS mix
├─ SA-06 Subtitle Engine            agents/subtitle_engine.py   6 languages, RTL, spec + back-translation
├─ SA-07 Metadata Composer          agents/metadata_composer.py per-platform limits, banned phrases
├─ SA-09 QA Auditor                 agents/qa_auditor.py        the full automated checklist
└─ SA-08 Publisher                  agents/publisher.py         staggered publish (post-approval)

Puzzle engine     vgen_swarm/puzzle/{grid,solver,generator}.py
State stores      vgen_swarm/state/db.py        (SQLite-backed, the 6 spec stores)
Providers         vgen_swarm/providers/         (interfaces + offline mocks + Claude adapter)
Review interface  vgen_swarm/review/server.py   (stdlib web dashboard)
Audit log         vgen_swarm/audit_log.py       (timestamp + output hash per action)
```

### Production state machine

```
writing → video → audio → subtitles → metadata → QA ─┬─ pass → review → (human) → published
                                                      └─ fail → routed back to owning agent
```

Each stage retries up to 3× on a self-reported quality failure
(`QualityCheckError`) before the episode is flagged `FAILED`. A QA failure never
reaches the human queue; it is routed back to the responsible agent.

## The logic-grid engine (the heart of the story)

`vgen_swarm/puzzle/` is a real CSP solver, not decoration:

- **`generate_puzzle(categories, seed)`** picks a random solution, derives the
  clues that hold for it, then **minimises to an irreducible clue set** —
  removing *any* remaining clue breaks uniqueness.
- **`is_uniquely_solvable(puzzle)`** is the mandatory validation step: a puzzle
  with more than one solution is rejected (no ambiguous solutions).
- The solver uses MRV variable ordering + forward checking and handles 4×4
  (Season 1) through 5×5+ (Season 2+) in well under a second.
- The solution maps to a story revelation (the culprit = the suspect at the
  weapon's position), and — per the non-negotiable — the reveal is **deferred to
  a later season** than the one that introduces it.

```python
from vgen_swarm.puzzle import generate_puzzle, is_uniquely_solvable
puzzle, solution = generate_puzzle({
    "suspect": ["Vega","Cohen","Mara","Okafor"],
    "room":    ["library","cellar","study","attic"],
    "item":    ["ledger","locket","dagger","letter"],
    "time":    ["dusk","midnight","dawn","noon"],
}, seed=7)
assert is_uniquely_solvable(puzzle)
```

## Spec coverage

| Spec module | Where | Status |
|---|---|---|
| MOA orchestration, queue, retry, review gate | `orchestrator.py` | ✅ real |
| Module 1 — Story creation (SA-01) | `agents/story_architect.py` | ✅ structure real; prose via LLM adapter |
| Module 1.2 — Logic-grid puzzle (SA-02) | `puzzle/`, `agents/puzzle_weaver.py` | ✅ real (solver + uniqueness) |
| Module 2.1 — Video prompts + render (SA-04) | `agents/video_director.py` | ✅ logic real; render via provider (mock) |
| Module 2.2 — BGM + SFX (SA-05) | `agents/audio_composer.py` | ✅ logic real; gen via provider (mock) |
| Module 3 — Subtitles, 6 langs, RTL (SA-06) | `agents/subtitle_engine.py` | ✅ spec real; timing/translate via provider |
| Module 4 — Per-platform metadata (SA-07) | `agents/metadata_composer.py` | ✅ real (limits, banned phrases, tags) |
| Module 5 — Publishing, staggered (SA-08) | `agents/publisher.py` | ✅ logic real; upload via provider (mock) |
| Module 6 — QA auditor checklist (SA-09) | `agents/qa_auditor.py` | ✅ real |
| Module 7 — Human review interface | `review/server.py` | ✅ real (stdlib web app) |
| Data & state — the 6 stores | `state/db.py` | ✅ real (SQLite) |
| Auditability (timestamp + output hash) | `audit_log.py` | ✅ real |

## Going live

### Step B (start here) — real story/script prose via DeepSeek or Claude

The LLM is the cheapest, lowest-risk service to make real. **DeepSeek is
supported out of the box** (its API is OpenAI-compatible) with no extra packages:

```bash
export DEEPSEEK_API_KEY=sk-...      # uses the deepseek-chat model
python3 run_demo.py                 # prints "LLM provider: DeepSeekLLM (prose is LIVE)"
```

`best_available_llm()` selects DeepSeek when `DEEPSEEK_API_KEY` is set, else
Claude when `ANTHROPIC_API_KEY` is set (requires `pip install anthropic`), else
the offline mock. SA-01 (universe prose) and SA-03 (script hook lines) call the
LLM and fall back to deterministic templates if no key is set or the call fails,
so the pipeline never breaks. To pick the reasoning model:

```python
from vgen_swarm.providers import DeepSeekLLM, default_mock_bundle
bundle = default_mock_bundle(llm=DeepSeekLLM(model="deepseek-reasoner"))
```

### Step B continued — real thumbnails via DALL·E 3 or FLUX

Thumbnail image generation is another single, self-contained API (stdlib only):

```bash
export OPENAI_API_KEY=sk-...      # DALL·E 3 (portrait 1024x1792), or
export TOGETHER_API_KEY=...       # FLUX via Together AI
python3 run_demo.py               # prints "Image provider: dall-e-3 (LIVE)"
```

`best_available_image()` picks DALL·E 3 when `OPENAI_API_KEY` is set, else FLUX
when `TOGETHER_API_KEY` is set, else the offline mock. Real calls are wrapped so
an API/network error falls back to the placeholder rather than breaking the run.
The generated PNG path is printed by the demo. Mix and match providers freely:

```python
from vgen_swarm.providers import default_mock_bundle, best_available_llm, TogetherFlux
bundle = default_mock_bundle(llm=best_available_llm(), image=TogetherFlux())
```

### Step B continued — real subtitle translation (reuses your DeepSeek key)

The 6-language subtitles can be translated by the same LLM you already use for
prose — no new account needed:

```bash
export DEEPSEEK_API_KEY=sk-...     # also powers translation
python3 run_demo.py                # "Translation provider: ... (LIVE)" + sample lines
```

`best_available_translation()` uses an LLM translator when a live LLM is wired
(DeepSeek, then Claude), else the offline mock. The back-translation QA spot
check (~20% of lines) is similarity-based: it tolerates normal paraphrasing and
only fails the episode on systemic breakdown. DeepL can be added later as an
alternative `TranslationProvider`.

### Budget video + audio (no per-second video billing)

AI text-to-video is the one line item that can cost a fortune (priced per second
of output). The **budget pipeline** avoids it entirely — it builds episodes from
still images animated with ffmpeg, plus free synthesised/library audio:

```bash
# install ffmpeg first (e.g. brew install ffmpeg / apt-get install ffmpeg)
python3 run_demo.py --budget            # ffmpeg slideshow video + free audio
python3 run_demo.py --budget --cap 0.50 # also enforce a $0.50/episode hard cap
```

Every run prints a cost estimate before/after generation. Typical figures:

```
  $ 0.0031  text/LLM     (DeepSeek)
  $ 0.2000  images       (5 x DALL-E 3 thumbnails+stills; use FLUX/mock for ~$0)
  $ 0.0000  video        (ffmpeg slideshow — free)
  $ 0.0000  audio        (synth/library — free)
  -------
  $ 0.2031  TOTAL        vs ~$56 for a full Veo text-to-video episode
```

- **`SlideshowVideo`** (`providers/ffmpeg_media.py`) generates one still per
  scene (via your image provider), Ken-Burns-animates each to 9:16, and
  concatenates them. Falls back to a placeholder if ffmpeg is missing.
- **`FreeMusic` / `FreeSFX`** synthesise audio with ffmpeg, or use royalty-free
  tracks from `FreeMusic(library_dir=...)`.
- **Cost guard:** `SwarmConfig.max_cost_per_episode` (or `--cap`) blocks any
  episode whose estimate exceeds the limit *before* a paid API is called. See
  `vgen_swarm/cost.py`.

Recommended workflow: validate hooks/format cheaply on the budget pipeline
first; only graduate specific proven episodes to paid AI video.

### Full production — the remaining services

1. `pip install -r requirements-optional.txt` for whichever adapters you wire.
2. Set credentials in your secrets vault / environment (video/audio/social keys).
   **Never hardcode keys** — providers read the environment.
3. Implement the real adapters against the protocols in
   `vgen_swarm/providers/base.py` (the mocks in `mock.py` show the exact shape
   each must return), and build a `ProviderBundle` with them instead of
   `default_mock_bundle()`.
4. The orchestrator, QA, continuity, and review layers need no changes.

## Notes & honest limitations

- This environment has no API keys and shouldn't auto-post to live social
  accounts, so social publishing, video/audio/image generation, Whisper, and
  translation run as **mocks** that produce placeholder files + metadata
  sidecars. QA and the pipeline operate on the declared artifact properties, so
  the orchestration/QA/continuity logic is genuinely exercised.
- Story/script prose is templated but structurally valid offline; wire the
  Claude adapter (`providers/llm.py`, `best_available_llm()`) for real prose.
- The review dashboard is intentionally minimal (stdlib `http.server`); the spec
  suggests a Next.js front end, which can target the same JSON endpoints.
