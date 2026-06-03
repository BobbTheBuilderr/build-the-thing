"""VGEN-SWARM: autonomous multi-agent short-form video production pipeline.

This package implements the orchestration, state, puzzle, agent, QA, and review
layers described in the VGEN-SWARM spec. Deterministic logic (puzzle solving,
continuity tracking, QA checks, metadata limits, the orchestration state machine)
is implemented for real. Every external AI / social-media service is accessed
through a provider interface (``vgen_swarm.providers``) with a working mock
implementation, so the full pipeline runs offline and is testable.
"""

__version__ = "1.0.0"
