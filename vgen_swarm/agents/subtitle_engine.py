"""SA-06 Subtitle Engine — multi-language subtitles synced to audio.

Aligns timing from the audio (Whisper), translates every required language
(RTL-aware for Arabic), enforces the mobile subtitle spec (<=2 lines, <=42
chars/line, >=1.5s display), runs a back-translation spot check on ~20% of lines,
and writes SRT tracks plus a burned-in marker.
"""
from __future__ import annotations

import difflib
import os

from ..config import (RTL_LANGUAGES, SUBTITLE_MAX_CHARS_PER_LINE,
                      SUBTITLE_MAX_LINES, SUBTITLE_MIN_DURATION_SEC)
from ..models import Script, SubtitleArtifact, SubtitleTrack
from .base import BaseAgent, AgentResult, QualityCheckError

# back-translation tolerances: a single paraphrased line is fine, but if most of
# the sample diverges badly the translation pipeline is broken.
_BACKTRANS_MIN_RATIO = 0.25
_BACKTRANS_FAIL_FRACTION = 0.6


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def _wrap(text: str) -> list[str]:
    """Greedy wrap to <=2 lines of <=42 chars."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= SUBTITLE_MAX_CHARS_PER_LINE:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:SUBTITLE_MAX_LINES]


def _srt(cues: list[dict]) -> str:
    def ts(t: float) -> str:
        h, rem = divmod(t, 3600)
        m, s = divmod(rem, 60)
        ms = int((s - int(s)) * 1000)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{ms:03d}"
    out = []
    for i, c in enumerate(cues, 1):
        out.append(f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['text']}\n")
    return "\n".join(out)


class SubtitleEngine(BaseAgent):
    agent_id = "SA-06"
    name = "Subtitle Engine"

    def build(self, script: Script, audio_path: str) -> SubtitleArtifact:
        ref = script.ref
        lines = script.all_dialogue
        timed = self.providers.transcription.transcribe(audio_path, lines)

        # enforce minimum display duration
        for cue in timed:
            if cue["end"] - cue["start"] < SUBTITLE_MIN_DURATION_SEC:
                cue["end"] = cue["start"] + SUBTITLE_MIN_DURATION_SEC

        artifact = SubtitleArtifact(ref=ref)
        raw_by_lang: dict[str, list[str]] = {}
        for lang in self.config.languages:
            cues, raws = [], []
            for cue in timed:
                translated = self.providers.translation.translate(cue["text"], lang)
                raws.append(translated)
                wrapped = "\n".join(_wrap(translated))
                cues.append({"start": cue["start"], "end": cue["end"],
                             "text": wrapped})
            raw_by_lang[lang] = raws
            track = SubtitleTrack(lang=lang, rtl=lang in RTL_LANGUAGES, cues=cues)
            track.srt_path = os.path.join(self.config.workdir, ref, f"sub_{lang}.srt")
            track.ass_path = os.path.join(self.config.workdir, ref, f"sub_{lang}.ass")
            os.makedirs(os.path.dirname(track.srt_path), exist_ok=True)
            with open(track.srt_path, "w", encoding="utf-8") as fh:
                fh.write(_srt(cues))
            artifact.tracks[lang] = track

        # back-translation spot check on ~20% of lines (reuses translations above)
        self._spot_check(ref, timed, raw_by_lang)

        artifact.burned_in_path = os.path.join(self.config.workdir, ref,
                                                "video_burned.mp4")
        self.log("build", {"ref": ref, "langs": list(artifact.tracks),
                          "lines": len(timed)}, episode_ref=ref)
        return artifact

    def _spot_check(self, ref: str, timed: list[dict],
                    raw_by_lang: dict[str, list[str]]) -> None:
        """Back-translate ~20% of lines and compare to the original by similarity.
        Tolerates paraphrasing; raises only on systemic failure (most of the
        sample diverging), which indicates a broken translation pipeline rather
        than a single imperfect line."""
        sample_idx = list(range(0, len(timed), 5)) or [0]
        suspects: list[dict] = []
        checked = 0
        for i in sample_idx:
            original = timed[i]["text"]
            for lang in self.config.languages:
                if lang.startswith("en"):
                    continue
                checked += 1
                back = self.providers.translation.back_translate(
                    raw_by_lang[lang][i], lang)
                ratio = difflib.SequenceMatcher(
                    None, _norm(original), _norm(back)).ratio()
                if ratio < _BACKTRANS_MIN_RATIO:
                    suspects.append({"lang": lang, "original": original,
                                     "back": back, "ratio": round(ratio, 2)})
        self.log("subtitle_spot_check",
                 {"checked": checked, "suspect": len(suspects),
                  "examples": suspects[:5]}, episode_ref=ref,
                 status="ok" if not suspects else "warn")
        if checked and len(suspects) / checked > _BACKTRANS_FAIL_FRACTION:
            raise QualityCheckError(
                f"back-translation failed on {len(suspects)}/{checked} sampled "
                f"lines — translation pipeline likely broken")

    def run(self, script: Script, audio_path: str) -> AgentResult:
        return AgentResult(self.agent_id, True, output=self.build(script, audio_path))
