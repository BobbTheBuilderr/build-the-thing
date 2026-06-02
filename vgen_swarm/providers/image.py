"""Thumbnail image-generation adapters (Module 4.1 / SA-07).

Two real backends, both pure standard library (urllib), plus a fallback wrapper:

* :class:`OpenAIImage`    — DALL·E 3 (``OPENAI_API_KEY``). Portrait 1024x1792.
* :class:`TogetherFlux`   — FLUX via Together AI (``TOGETHER_API_KEY``).
* :class:`ImageWithFallback` — wraps a real provider and writes the mock
  placeholder if the API errors, so a network hiccup never breaks a production
  run.

``best_available_image()`` selects the first backend whose key is present, else
the offline mock.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.request
from pathlib import Path
from typing import Optional


def _write_bytes(out_path: str, data: bytes, meta: dict) -> dict:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    Path(out_path + ".meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def _post_json(url: str, headers: dict, body: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_image(item: dict) -> bytes:
    """Handle both b64_json and url-style responses."""
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        with urllib.request.urlopen(item["url"], timeout=120) as r:
            return r.read()
    raise RuntimeError("image response contained neither b64_json nor url")


class OpenAIImage:
    """DALL·E 3 via the OpenAI Images API. Portrait size approximates 9:16."""

    name = "dall-e-3"

    def __init__(self, model: str = "dall-e-3", size: str = "1024x1792",
                 api_key: Optional[str] = None,
                 base_url: str = "https://api.openai.com/v1") -> None:
        self.model = model
        self.size = size
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url.rstrip("/")

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def generate_image(self, prompt: str, out_path: str) -> dict:
        data = _post_json(
            f"{self.base_url}/images/generations",
            {"Authorization": f"Bearer {self._api_key}"},
            {"model": self.model, "prompt": prompt, "n": 1,
             "size": self.size, "response_format": "b64_json"})
        img = _extract_image(data["data"][0])
        w, h = (int(x) for x in self.size.split("x"))
        return _write_bytes(out_path, img, {
            "kind": "thumbnail", "prompt": prompt, "model": self.model,
            "width": w, "height": h, "path": out_path})


class TogetherFlux:
    """FLUX via Together AI's images endpoint."""

    name = "flux"

    def __init__(self, model: str = "black-forest-labs/FLUX.1-schnell",
                 width: int = 768, height: int = 1344,
                 api_key: Optional[str] = None,
                 base_url: str = "https://api.together.xyz/v1") -> None:
        self.model = model
        self.width, self.height = width, height
        self._api_key = api_key or os.environ.get("TOGETHER_API_KEY")
        self.base_url = base_url.rstrip("/")

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def generate_image(self, prompt: str, out_path: str) -> dict:
        data = _post_json(
            f"{self.base_url}/images/generations",
            {"Authorization": f"Bearer {self._api_key}"},
            {"model": self.model, "prompt": prompt, "n": 1,
             "width": self.width, "height": self.height,
             "response_format": "b64_json"})
        img = _extract_image(data["data"][0])
        return _write_bytes(out_path, img, {
            "kind": "thumbnail", "prompt": prompt, "model": self.model,
            "width": self.width, "height": self.height, "path": out_path})


class ImageWithFallback:
    """Try a real provider; on any error, write the mock placeholder instead."""

    def __init__(self, primary) -> None:
        from .mock import MockImage
        self.primary = primary
        self.name = getattr(primary, "name", "image")
        self._fallback = MockImage()

    def generate_image(self, prompt: str, out_path: str) -> dict:
        try:
            return self.primary.generate_image(prompt, out_path)
        except Exception as exc:  # noqa: BLE001
            meta = self._fallback.generate_image(prompt, out_path)
            meta["fallback_error"] = str(exc)
            return meta


def best_available_image():
    """First real image backend whose key is present (DALL·E 3, then FLUX),
    wrapped with a placeholder fallback; else the plain offline mock."""
    for provider in (OpenAIImage(), TogetherFlux()):
        if provider.available:
            return ImageWithFallback(provider)
    from .mock import MockImage
    return MockImage()
