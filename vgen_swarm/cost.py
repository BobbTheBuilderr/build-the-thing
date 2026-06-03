"""Per-episode cost estimator and budget guard.

Prints what an episode will cost *before* any paid API is called, and lets the
operator set a hard per-episode cap (``SwarmConfig.max_cost_per_episode``) that
blocks generation above it. Free/mock/slideshow providers report $0; the report
also shows what a paid text-to-video model *would* cost, so the saving from the
budget pipeline is explicit.

All numbers are rough public-list approximations (they change often and vary by
resolution/tier) — treat them as planning estimates, not invoices.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Reference prices (USD), approximate. Used for comparison + paid providers.
REF_PRICES = {
    # text: per 1K tokens (input+output blended, rough)
    "deepseek_text_per_1k": 0.0008,
    # images: per image
    "dall-e-3": 0.04,
    "flux": 0.01,
    "mock-image": 0.0,
    # video: per second of output
    "veo3": 0.40,
    "kling": 0.10,
    "seedance": 0.03,
    "runway": 0.10,
    "slideshow": 0.0,
    "mock-video": 0.0,
}


@dataclass
class CostLine:
    label: str
    detail: str
    usd: float


@dataclass
class EpisodeEstimate:
    lines: list[CostLine] = field(default_factory=list)
    comparisons: list[CostLine] = field(default_factory=list)

    @property
    def total(self) -> float:
        return round(sum(l.usd for l in self.lines), 4)

    def as_dict(self) -> dict:
        return {"total_usd": self.total,
                "lines": [vars(l) for l in self.lines],
                "comparisons": [vars(c) for c in self.comparisons]}

    def format(self) -> str:
        out = ["Estimated cost for this episode (approx):"]
        for l in self.lines:
            out.append(f"  ${l.usd:>7.4f}  {l.label:<18} {l.detail}")
        out.append(f"  {'-'*7}")
        out.append(f"  ${self.total:>7.4f}  TOTAL")
        if self.comparisons:
            out.append("  For comparison, a full AI text-to-video episode would cost:")
            for c in self.comparisons:
                out.append(f"     ~${c.usd:>7.2f}  {c.label}  ({c.detail})")
        return "\n".join(out)


def _provider_name(p) -> str:
    return getattr(p, "name", type(p).__name__).lower()


def estimate_episode(providers, *, duration_sec: float, num_scenes: int,
                     num_dialogue_lines: int, num_languages: int,
                     num_platforms: int) -> EpisodeEstimate:
    est = EpisodeEstimate()

    # --- text (LLM): script hooks + subtitle translation + back-translation ---
    llm_live = getattr(providers.llm, "live", False)
    tr_live = getattr(providers.translation, "live", False)
    if llm_live or tr_live:
        translate_calls = num_dialogue_lines * max(num_languages - 1, 0)
        back_calls = max(1, num_dialogue_lines // 5) * max(num_languages - 1, 0)
        calls = 2 + translate_calls + back_calls   # +2 hook lines
        approx_tokens = calls * 120                 # ~120 tok/call blended
        usd = round(approx_tokens / 1000 * REF_PRICES["deepseek_text_per_1k"], 4)
        est.lines.append(CostLine("text/LLM",
                                  f"~{calls} calls (~{approx_tokens} tok)", usd))
    else:
        est.lines.append(CostLine("text/LLM", "offline mock", 0.0))

    # --- images: one still per scene (slideshow) + 1 thumbnail ---------------
    img_name = _provider_name(providers.image)
    per_img = REF_PRICES.get(img_name, 0.0)
    video_name = _provider_name(providers.video)
    n_images = (num_scenes + 1) if video_name == "slideshow" else 1
    img_usd = round(per_img * n_images, 4)
    est.lines.append(CostLine("images",
                              f"{n_images} x {img_name} @ ${per_img}", img_usd))

    # --- video ----------------------------------------------------------------
    per_sec = REF_PRICES.get(video_name, 0.0)
    vid_usd = round(per_sec * duration_sec, 4)
    label = "video"
    detail = (f"{video_name} (free)" if per_sec == 0
              else f"{video_name} @ ${per_sec}/s x {duration_sec:.0f}s")
    est.lines.append(CostLine(label, detail, vid_usd))

    # --- audio (free budget providers) ---------------------------------------
    est.lines.append(CostLine("audio", "BGM+SFX (free/synth)", 0.0))

    # --- comparison: paid text-to-video alternatives -------------------------
    if per_sec == 0:
        for model in ("seedance", "kling", "veo3"):
            est.comparisons.append(CostLine(
                model, f"${REF_PRICES[model]}/s x {duration_sec:.0f}s",
                round(REF_PRICES[model] * duration_sec, 2)))
    return est


class BudgetExceeded(RuntimeError):
    """Raised when an episode's estimated cost exceeds the configured cap."""
