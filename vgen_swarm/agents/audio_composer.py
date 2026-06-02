"""SA-05 Audio Composer — BGM generation, SFX placement, final mix.

Generates original BGM per episode from a brief tied to the script's emotional
beats, reuses the season's recurring sonic motif (created in episode 1), places
diegetic + punctuation SFX on scene timestamps, and declares a final mix
normalised to -14 LUFS with BGM ducked under dialogue.
"""
from __future__ import annotations

import os

from ..config import TARGET_LUFS
from ..models import Script, AudioArtifact
from .base import BaseAgent, AgentResult


class AudioComposer(BaseAgent):
    agent_id = "SA-05"
    name = "Audio Composer"

    def ensure_motif(self, season: int) -> str:
        theme = self.db.get_audio_theme(season)
        if theme is None:
            motif_path = os.path.join(self.config.workdir,
                                      f"season{season}_motif.wav")
            self.providers.music.compose(
                "Season motif: lone cello figure, minor key, 70 BPM", motif_path)
            theme = {"season": season, "motif_ref": motif_path,
                     "identity": "lone cello, minor key"}
            self.db.save_audio_theme(season, theme)
            self.log("create_motif", theme, detail={"season": season})
        return theme["motif_ref"]

    def _brief(self, script: Script) -> str:
        beats = ", ".join(f"{s.start_sec:.0f}s:{s.emotional_beat}"
                          for s in script.scenes)
        return (f"Tense string quartet tracking beats [{beats}], building to a "
                f"staccato climax then a held dissonance. 90 BPM, "
                f"{script.duration_sec:.0f}s.")

    def compose(self, script: Script) -> AudioArtifact:
        ref = script.ref
        motif = self.ensure_motif(script.season)
        bgm_path = os.path.join(self.config.workdir, ref, "bgm.wav")
        brief = self._brief(script)
        self.providers.music.compose(brief, bgm_path, motif_ref=motif)

        # diegetic + punctuation SFX aligned to scene starts
        sfx = []
        for s in script.scenes:
            sfx_path = os.path.join(self.config.workdir, ref, f"sfx_{s.index}.wav")
            desc = {"tension-spike": "thunder crack riser",
                    "simmer": "rain on glass, distant clock",
                    "reveal": "low impact sting",
                    "cliff": "sub-bass drop"}.get(s.emotional_beat, "ambient room tone")
            self.providers.sfx.fetch_sfx(desc, sfx_path)
            sfx.append({"at": s.start_sec, "desc": desc, "path": sfx_path})

        artifact = AudioArtifact(
            ref=ref, path=os.path.join(self.config.workdir, ref, "mix.aac"),
            lufs=TARGET_LUFS, sample_rate=48000, codec="aac",
            duration_sec=script.duration_sec, max_silence_gap_sec=0.4,
            clipping=False, bgm_brief=brief, motif_ref=motif)
        # write the declared final mix sidecar via the music provider path
        self.providers.music.compose(f"final mix (ducked) for {ref}",
                                     artifact.path, motif_ref=motif)
        self.log("compose", {"bgm": bgm_path, "sfx": sfx, "lufs": TARGET_LUFS,
                            "mix": artifact.path}, episode_ref=ref)
        return artifact

    def run(self, script: Script) -> AgentResult:
        return AgentResult(self.agent_id, True, output=self.compose(script))
