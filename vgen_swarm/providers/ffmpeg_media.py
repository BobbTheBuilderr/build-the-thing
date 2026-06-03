"""Budget media providers — real video/audio for near-zero marginal cost.

The expensive line item in this whole system is AI text-to-video (priced per
second). This module avoids it entirely:

* :class:`SlideshowVideo` — turns one generated still per scene into a 9:16
  motion clip (Ken Burns pan/zoom) and concatenates them with ffmpeg. Cost = the
  still images only (cents); **no per-second video billing.**
* :class:`FreeMusic`      — synthesises a soft ambient bed with ffmpeg (free).
* :class:`FreeSFX`        — synthesises short punctuation effects with ffmpeg
  (free). Drop royalty-free files into a library dir to use those instead.

Every provider degrades gracefully: if ffmpeg is unavailable the call writes the
same placeholder the mocks do, so the pipeline always completes. Real
royalty-free music belongs in ``FreeMusic(library_dir=...)``; the spec allows
Freesound / AI-generated originals only.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _run(cmd: list[str], timeout: int = 120) -> bool:
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return proc.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _placeholder(out_path: str, meta: dict) -> dict:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"VGEN-MOCK-MEDIA\x00" + json.dumps(meta).encode("utf-8"))
    Path(out_path + ".meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def _parse_duration(text: str, default: float = 60.0) -> float:
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*s\b", text)
    return float(matches[-1]) if matches else default


class SlideshowVideo:
    """ffmpeg Ken Burns slideshow. Generates a still per scene via the injected
    image provider, then animates and concatenates into a 9:16 MP4."""

    name = "slideshow"
    cost_model = ("free", 0.0)   # only the still images cost anything

    def __init__(self, image_provider, width: int = 1080, height: int = 1920,
                 fps: int = 30) -> None:
        self.image = image_provider
        self.width, self.height, self.fps = width, height, fps
        self._ffmpeg = ffmpeg_available()

    def _prompt_text(self, prompt: dict) -> str:
        return (f"{prompt.get('subject','')}, {prompt.get('action','')}; "
                f"{prompt.get('lighting','')}, {prompt.get('palette','')}; "
                f"{prompt.get('environment','')}; vertical 9:16 cinematic frame")

    def render_scene(self, prompt: dict, out_path: str) -> dict:
        idx = prompt.get("scene_index", 0)
        dur = max(float(prompt.get("duration_sec", 4.0)), 1.0)
        base = Path(out_path)
        still = str(base.with_suffix(f".s{idx}.png"))
        clip = str(base.with_suffix(f".s{idx}.mp4"))
        meta = {"kind": "video", "engine": "slideshow", "scene_index": idx,
                "aspect_ratio": "9:16", "width": self.width, "height": self.height,
                "fps": self.fps, "duration_sec": dur, "has_watermark": False,
                "has_text_artifacts": False, "clip_path": clip, "cost_usd": 0.0}

        # 1) still (cheap) — via the image provider (real or mock)
        try:
            self.image.generate_image(self._prompt_text(prompt), still)
        except Exception:  # noqa: BLE001
            pass

        # 2) animate the still into a clip (free) — or fall back to placeholder
        if self._ffmpeg and os.path.exists(still) and os.path.getsize(still) > 64:
            frames = int(dur * self.fps)
            vf = (f"scale={self.width*3//2}:{self.height*3//2},"
                  f"zoompan=z='min(zoom+0.0004,1.4)':d={frames}:"
                  f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                  f"s={self.width}x{self.height}:fps={self.fps},"
                  f"format=yuv420p")
            ok = _run(["ffmpeg", "-y", "-loop", "1", "-i", still, "-t", str(dur),
                       "-vf", vf, "-c:v", "libx264", "-r", str(self.fps), clip])
            if ok:
                return meta
        meta["engine"] = "fallback-placeholder"
        _placeholder(clip, meta)
        return meta

    def assemble(self, clip_paths: list[str], out_path: str) -> dict:
        clip_paths = [c for c in clip_paths if c]
        meta = {"kind": "video", "engine": "slideshow", "aspect_ratio": "9:16",
                "width": self.width, "height": self.height, "fps": self.fps,
                "clips": len(clip_paths), "path": out_path, "cost_usd": 0.0}
        real = [c for c in clip_paths
                if os.path.exists(c) and not _is_placeholder(c)]
        if self._ffmpeg and len(real) == len(clip_paths) and clip_paths:
            listfile = out_path + ".concat.txt"
            Path(listfile).write_text(
                "".join(f"file '{os.path.abspath(c)}'\n" for c in clip_paths))
            if _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
                     "-c", "copy", out_path]):
                meta["engine"] = "slideshow-concat"
                Path(out_path + ".meta.json").write_text(json.dumps(meta, indent=2))
                return meta
        meta["engine"] = "fallback-placeholder"
        return _placeholder(out_path, meta)


def _is_placeholder(path: str) -> bool:
    try:
        with open(path, "rb") as fh:
            return fh.read(15) == b"VGEN-MOCK-MEDIA"
    except OSError:
        return True


class FreeMusic:
    """Free BGM: a royalty-free library track if provided, else a synthesised
    ambient bed via ffmpeg. Zero marginal cost."""

    name = "free-music"
    cost_model = ("free", 0.0)

    def __init__(self, library_dir: Optional[str] = None) -> None:
        self.library_dir = library_dir
        self._ffmpeg = ffmpeg_available()

    def compose(self, brief: str, out_path: str, *, motif_ref: str = "") -> dict:
        dur = _parse_duration(brief)
        meta = {"kind": "bgm", "brief": brief, "motif_ref": motif_ref,
                "royalty_free": True, "source": "library_or_synth",
                "duration_sec": dur, "cost_usd": 0.0}
        # prefer a user-supplied royalty-free track
        if self.library_dir and os.path.isdir(self.library_dir):
            tracks = [f for f in os.listdir(self.library_dir)
                      if f.lower().endswith((".mp3", ".wav", ".m4a"))]
            if tracks:
                src = os.path.join(self.library_dir, sorted(tracks)[0])
                Path(out_path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, out_path)
                meta["source"] = f"library:{tracks[0]}"
                Path(out_path + ".meta.json").write_text(json.dumps(meta, indent=2))
                return meta
        # else synthesise a soft two-note pad
        if self._ffmpeg:
            ac = "pcm_s16le" if out_path.endswith(".wav") else "aac"
            ok = _run(["ffmpeg", "-y",
                       "-f", "lavfi", "-i", f"sine=frequency=220:duration={dur}",
                       "-f", "lavfi", "-i", f"sine=frequency=277:duration={dur}",
                       "-filter_complex", "[0][1]amix=inputs=2,volume=0.18",
                       "-c:a", ac, out_path])
            if ok:
                meta["source"] = "synth-pad"
                Path(out_path + ".meta.json").write_text(json.dumps(meta, indent=2))
                return meta
        return _placeholder(out_path, meta)


class FreeSFX:
    """Free SFX: short synthesised punctuation effects via ffmpeg."""

    name = "free-sfx"
    cost_model = ("free", 0.0)

    def __init__(self) -> None:
        self._ffmpeg = ffmpeg_available()

    def fetch_sfx(self, description: str, out_path: str) -> dict:
        meta = {"kind": "sfx", "description": description, "royalty_free": True,
                "source": "synth", "cost_usd": 0.0}
        if self._ffmpeg:
            ac = "pcm_s16le" if out_path.endswith(".wav") else "aac"
            ok = _run(["ffmpeg", "-y", "-f", "lavfi",
                       "-i", "anoisesrc=d=0.4:c=pink:a=0.3",
                       "-c:a", ac, out_path])
            if ok:
                Path(out_path + ".meta.json").write_text(json.dumps(meta, indent=2))
                return meta
        return _placeholder(out_path, meta)
