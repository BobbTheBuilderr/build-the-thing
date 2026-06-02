"""Deterministic, offline mock providers.

These let the entire pipeline run and be tested without API keys or network.
Media files are written as small placeholder files accompanied by a JSON sidecar
describing the artifact's *declared* properties (aspect ratio, LUFS, timings,
…). The QA auditor and the rest of the pipeline operate on those declared
properties, so the orchestration / QA / continuity logic is exercised for real
even though no pixels are rendered.

To go live, drop in real providers implementing the same protocols in
:mod:`vgen_swarm.providers.base`.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Optional


def _write_placeholder(out_path: str, meta: dict) -> None:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"VGEN-MOCK-MEDIA\x00" + json.dumps(meta).encode("utf-8"))
    Path(out_path + ".meta.json").write_text(json.dumps(meta, indent=2))


def _stable(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


class MockLLM:
    """Deterministic templated 'LLM'. Marked ``live = False`` so agents use their
    built-in templates instead of this placeholder. Real builds swap in the
    DeepSeek or Claude adapter (see ``llm.py``)."""
    live = False

    def complete(self, system: str, prompt: str, *, max_tokens: int = 1024) -> str:
        return f"[mock-llm:{_stable(system, prompt)}] {prompt[:80]}"


class MockVideo:
    name = "mock-video"

    def render_scene(self, prompt: dict, out_path: str) -> dict:
        meta = {
            "kind": "video", "prompt": prompt,
            "aspect_ratio": "9:16", "width": 1080, "height": 1920, "fps": 30,
            "duration_sec": float(prompt.get("duration_sec", 0.0)),
            "has_watermark": False, "has_text_artifacts": False,
        }
        _write_placeholder(out_path, meta)
        return meta


class MockMusic:
    def compose(self, brief: str, out_path: str, *, motif_ref: str = "") -> dict:
        meta = {"kind": "bgm", "brief": brief, "motif_ref": motif_ref,
                "royalty_free": True, "ai_generated": True}
        _write_placeholder(out_path, meta)
        return meta


class MockSFX:
    def fetch_sfx(self, description: str, out_path: str) -> dict:
        meta = {"kind": "sfx", "description": description, "royalty_free": True}
        _write_placeholder(out_path, meta)
        return meta


class MockTranscription:
    """Distributes reference lines evenly across a nominal duration, mimicking
    Whisper word-timing alignment closely enough to drive subtitle timing."""
    def transcribe(self, audio_path: str, reference_lines: list[str]) -> list[dict]:
        meta_path = audio_path + ".meta.json"
        duration = 120.0
        if os.path.exists(meta_path):
            duration = float(json.loads(Path(meta_path).read_text())
                             .get("duration_sec", 120.0))
        n = max(len(reference_lines), 1)
        slot = duration / n
        out = []
        for i, line in enumerate(reference_lines):
            out.append({"start": round(i * slot, 2),
                        "end": round((i + 1) * slot - 0.05, 2),
                        "text": line})
        return out


class MockTranslation:
    """Deterministic pseudo-translation. Tags text with the target language so
    QA can confirm 'no untranslated lines', and round-trips back-translation."""
    def translate(self, text: str, target_lang: str) -> str:
        if target_lang.lower().startswith("en"):
            return text
        return f"[{target_lang}] {text}"

    def back_translate(self, text: str, source_lang: str) -> str:
        # strip our language tag to recover the original (round-trip ~ lossless)
        if text.startswith("["):
            return text.split("] ", 1)[-1]
        return text


class MockImage:
    def generate_image(self, prompt: str, out_path: str) -> dict:
        meta = {"kind": "thumbnail", "prompt": prompt, "width": 1080, "height": 1920}
        _write_placeholder(out_path, meta)
        return meta


class MockSocial:
    def __init__(self, platform: str) -> None:
        self.platform = platform

    def publish(self, video_path: str, metadata: dict, *,
                scheduled_ts: Optional[float] = None) -> dict:
        post_id = _stable(self.platform, video_path, metadata.get("title", ""))
        url = f"https://{self.platform}.example/p/{post_id}"
        return {"platform": self.platform, "post_id": post_id, "url": url,
                "scheduled_ts": scheduled_ts}


def default_mock_bundle(llm=None):
    """All-mock provider bundle. Pass ``llm`` to use a real LLM (e.g. DeepSeek)
    for story/script prose while every other service stays mocked."""
    from .base import ProviderBundle
    platforms = ["tiktok", "youtube", "instagram", "facebook", "x"]
    return ProviderBundle(
        llm=llm or MockLLM(),
        video=MockVideo(),
        music=MockMusic(),
        sfx=MockSFX(),
        transcription=MockTranscription(),
        translation=MockTranslation(),
        image=MockImage(),
        social={p: MockSocial(p) for p in platforms},
    )
