"""Base class shared by all sub-agents.

Provides the shared handles (state DB, provider bundle, audit log, config) and a
single ``log`` helper so every agent action is recorded with a timestamp and
output hash, satisfying the auditability non-negotiable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ..audit_log import AuditLog
from ..config import SwarmConfig
from ..providers.base import ProviderBundle
from ..state.db import StateDB


class QualityCheckError(Exception):
    """Raised by an agent when its own output fails an internal quality gate.
    The orchestrator catches this and applies retry logic."""


@dataclass
class AgentResult:
    agent: str
    ok: bool
    output: Any = None
    detail: dict = None  # type: ignore[assignment]


class BaseAgent:
    agent_id: str = "SA-00"
    name: str = "Base"

    def __init__(self, db: StateDB, providers: ProviderBundle,
                 audit: AuditLog, config: SwarmConfig) -> None:
        self.db = db
        self.providers = providers
        self.audit = audit
        self.config = config

    def log(self, action: str, output: Any, *, episode_ref: Optional[str] = None,
            status: str = "ok", detail: Optional[dict] = None):
        return self.audit.record(
            f"{self.agent_id}:{self.name}", action, output,
            episode_ref=episode_ref, status=status, detail=detail)
