"""Trace reader port for reconstructing persisted runs."""

from __future__ import annotations

from typing import Protocol

from ds_agent.evaluation.domain.entities.eval_run import EvalRun


class TraceReader(Protocol):
    """Load a persisted autonomous run into an EvalRun model."""

    def read_session(
        self,
        *,
        session_id: str,
        task_id: str | None = None,
        run_id: str | None = None,
    ) -> EvalRun:
        """Return the reconstructed run for one persisted session."""

