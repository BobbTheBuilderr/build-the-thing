"""Auditable action log.

Constraint (non-negotiable): *every* agent action must be logged with a
timestamp and an output hash for auditability. ``AuditLog`` provides a single
append-only sink that all agents share, writing JSON lines plus a stable hash
of the produced output.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional


def output_hash(payload: Any) -> str:
    """Deterministic SHA-256 of any JSON-serialisable payload."""
    blob = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class AuditEntry:
    ts: float
    agent: str
    action: str
    episode_ref: Optional[str]
    status: str
    output_sha256: str
    detail: dict = field(default_factory=dict)

    def as_line(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)


class AuditLog:
    """Thread-safe append-only audit log (in-memory + optional file sink)."""

    def __init__(self, path: Optional[str | Path] = None) -> None:
        self._path = Path(path) if path else None
        self._lock = threading.Lock()
        self.entries: list[AuditEntry] = []
        if self._path:
            self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        agent: str,
        action: str,
        output: Any,
        *,
        episode_ref: Optional[str] = None,
        status: str = "ok",
        detail: Optional[dict] = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            ts=time.time(),
            agent=agent,
            action=action,
            episode_ref=episode_ref,
            status=status,
            output_sha256=output_hash(output),
            detail=detail or {},
        )
        with self._lock:
            self.entries.append(entry)
            if self._path:
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(entry.as_line() + "\n")
        return entry

    def for_episode(self, episode_ref: str) -> list[AuditEntry]:
        return [e for e in self.entries if e.episode_ref == episode_ref]
