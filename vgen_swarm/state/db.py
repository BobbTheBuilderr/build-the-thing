"""SQLite-backed implementation of the six VGEN-SWARM state stores.

Kept deliberately simple: JSON blobs keyed by their natural identifiers. This is
enough to drive the orchestrator, survive restarts, and back the review
dashboard. Swap for PostgreSQL/Supabase by reimplementing this class against the
same method surface.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS universe (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS season_arcs (
    season INTEGER PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS episode_outlines (
    ref TEXT PRIMARY KEY,
    season INTEGER NOT NULL,
    episode INTEGER NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS puzzle_state (
    season INTEGER PRIMARY KEY,
    data TEXT NOT NULL          -- {categories, solution, clues, placement_log}
);
CREATE TABLE IF NOT EXISTS clue_placements (
    clue_id TEXT PRIMARY KEY,
    season INTEGER NOT NULL,
    episode INTEGER NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS visual_bible (
    character TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audio_theme (
    season INTEGER PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS production_queue (
    ref TEXT PRIMARY KEY,
    stage TEXT NOT NULL,
    updated REAL NOT NULL,
    data TEXT NOT NULL          -- artifact references + qa report + notes
);
CREATE TABLE IF NOT EXISTS publish_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ref TEXT NOT NULL,
    platform TEXT NOT NULL,
    post_id TEXT,
    url TEXT,
    ts REAL NOT NULL
);
"""


class StateDB:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._path = str(path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- helpers -------------------------------------------------------------
    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    @staticmethod
    def _j(v: Any) -> str:
        return json.dumps(v, default=str, ensure_ascii=False)

    # -- Story Universe DB ---------------------------------------------------
    def save_universe(self, universe: dict) -> None:
        self._exec("INSERT OR REPLACE INTO universe (id, data) VALUES (1, ?)",
                   (self._j(universe),))

    def get_universe(self) -> Optional[dict]:
        row = self._exec("SELECT data FROM universe WHERE id = 1").fetchone()
        return json.loads(row["data"]) if row else None

    def save_season_arc(self, season: int, arc: dict) -> None:
        self._exec("INSERT OR REPLACE INTO season_arcs (season, data) VALUES (?, ?)",
                   (season, self._j(arc)))

    def get_season_arcs(self) -> list[dict]:
        rows = self._exec("SELECT data FROM season_arcs ORDER BY season").fetchall()
        return [json.loads(r["data"]) for r in rows]

    def save_episode_outline(self, ref: str, season: int, episode: int,
                             outline: dict) -> None:
        self._exec(
            "INSERT OR REPLACE INTO episode_outlines (ref, season, episode, data) "
            "VALUES (?, ?, ?, ?)", (ref, season, episode, self._j(outline)))

    def get_episode_outline(self, ref: str) -> Optional[dict]:
        row = self._exec("SELECT data FROM episode_outlines WHERE ref = ?",
                         (ref,)).fetchone()
        return json.loads(row["data"]) if row else None

    # -- Puzzle State DB -----------------------------------------------------
    def save_puzzle_state(self, season: int, state: dict) -> None:
        self._exec("INSERT OR REPLACE INTO puzzle_state (season, data) VALUES (?, ?)",
                   (season, self._j(state)))

    def get_puzzle_state(self, season: int) -> Optional[dict]:
        row = self._exec("SELECT data FROM puzzle_state WHERE season = ?",
                         (season,)).fetchone()
        return json.loads(row["data"]) if row else None

    def log_clue_placement(self, clue_id: str, season: int, episode: int,
                           data: dict) -> None:
        self._exec(
            "INSERT OR REPLACE INTO clue_placements (clue_id, season, episode, data) "
            "VALUES (?, ?, ?, ?)", (clue_id, season, episode, self._j(data)))

    def clue_placements_for_episode(self, season: int, episode: int) -> list[dict]:
        rows = self._exec(
            "SELECT data FROM clue_placements WHERE season = ? AND episode = ?",
            (season, episode)).fetchall()
        return [json.loads(r["data"]) for r in rows]

    # -- Visual Bible --------------------------------------------------------
    def save_visual_anchor(self, character: str, anchor: dict) -> None:
        self._exec("INSERT OR REPLACE INTO visual_bible (character, data) VALUES (?, ?)",
                   (character, self._j(anchor)))

    def get_visual_anchor(self, character: str) -> Optional[dict]:
        row = self._exec("SELECT data FROM visual_bible WHERE character = ?",
                         (character,)).fetchone()
        return json.loads(row["data"]) if row else None

    # -- Audio Theme DB ------------------------------------------------------
    def save_audio_theme(self, season: int, theme: dict) -> None:
        self._exec("INSERT OR REPLACE INTO audio_theme (season, data) VALUES (?, ?)",
                   (season, self._j(theme)))

    def get_audio_theme(self, season: int) -> Optional[dict]:
        row = self._exec("SELECT data FROM audio_theme WHERE season = ?",
                         (season,)).fetchone()
        return json.loads(row["data"]) if row else None

    # -- Production Queue ----------------------------------------------------
    def set_stage(self, ref: str, stage: str, data: Optional[dict] = None) -> None:
        existing = self.get_queue_entry(ref)
        merged = (existing.get("data") if existing else {}) or {}
        if data:
            merged.update(data)
        self._exec(
            "INSERT OR REPLACE INTO production_queue (ref, stage, updated, data) "
            "VALUES (?, ?, ?, ?)", (ref, stage, time.time(), self._j(merged)))

    def get_queue_entry(self, ref: str) -> Optional[dict]:
        row = self._exec(
            "SELECT ref, stage, updated, data FROM production_queue WHERE ref = ?",
            (ref,)).fetchone()
        if not row:
            return None
        return {"ref": row["ref"], "stage": row["stage"],
                "updated": row["updated"], "data": json.loads(row["data"])}

    def queue(self) -> list[dict]:
        rows = self._exec(
            "SELECT ref, stage, updated, data FROM production_queue "
            "ORDER BY ref").fetchall()
        return [{"ref": r["ref"], "stage": r["stage"], "updated": r["updated"],
                 "data": json.loads(r["data"])} for r in rows]

    def episodes_in_stage(self, stage: str) -> list[str]:
        rows = self._exec("SELECT ref FROM production_queue WHERE stage = ?",
                          (stage,)).fetchall()
        return [r["ref"] for r in rows]

    # -- Publish Log ---------------------------------------------------------
    def log_publish(self, ref: str, platform: str, post_id: str, url: str) -> None:
        self._exec(
            "INSERT INTO publish_log (ref, platform, post_id, url, ts) "
            "VALUES (?, ?, ?, ?, ?)", (ref, platform, post_id, url, time.time()))

    def publish_records(self, ref: Optional[str] = None) -> list[dict]:
        if ref:
            rows = self._exec(
                "SELECT * FROM publish_log WHERE ref = ? ORDER BY ts", (ref,)).fetchall()
        else:
            rows = self._exec("SELECT * FROM publish_log ORDER BY ts").fetchall()
        return [dict(r) for r in rows]
