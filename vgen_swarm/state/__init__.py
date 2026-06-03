"""Persistent state stores for the swarm (SQLite-backed, zero external deps).

Implements the six stores from the spec's DATA & STATE MANAGEMENT table:

* Story Universe DB   — universe, season arcs, episode outlines, clue manifests
* Puzzle State DB     — full grid + solution key + clue placement log per season
* Visual Bible        — per-character appearance anchors
* Audio Theme DB      — season sonic identity / motif
* Production Queue    — per-episode stage status
* Publish Log         — platform post IDs, URLs, timestamps
"""
from .db import StateDB

__all__ = ["StateDB"]
