"""Application service for isolated subagent execution."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, Protocol

from ds_agent.domain.value_objects.subagent import SubagentSpec

SubagentStatus = Literal["running", "completed", "failed", "timed_out"]
RuntimeEventRecorderFn = Callable[..., object]


@dataclass(slots=True)
class SubagentRun:
    """In-flight subagent execution handle."""

    run_id: str
    spec: SubagentSpec
    status: SubagentStatus = "running"
    session_id: str | None = None
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None


@dataclass(slots=True)
class SubagentResult:
    """Terminal result for one subagent execution."""

    run_id: str
    spec: SubagentSpec
    status: Literal["completed", "failed", "timed_out"]
    output: str
    session_id: str | None
    model: str
    started_at: float
    completed_at: float
    budget_summary: dict[str, object] = field(default_factory=dict)
    error: str | None = None

    @property
    def duration_seconds(self) -> float:
        """Return elapsed wall time for the isolated run."""
        return max(self.completed_at - self.started_at, 0.0)


class SubagentExecutor(Protocol):
    """Infrastructure port used by the orchestrator."""

    async def execute(
        self,
        spec: SubagentSpec,
        *,
        run_id: str,
        context_summary: str | None = None,
        parent_session_id: str | None = None,
        parent_model: str | None = None,
    ) -> SubagentResult: ...


class SubagentOrchestrator:
    """Coordinate one or more isolated subagent runs."""

    def __init__(
        self,
        *,
        executor: SubagentExecutor,
        record_runtime_event: RuntimeEventRecorderFn | None = None,
    ) -> None:
        self._executor = executor
        self._record_runtime_event = record_runtime_event
        self._runs: dict[str, SubagentRun] = {}
        self._tasks: dict[str, asyncio.Task[SubagentResult]] = {}

    def spawn(
        self,
        spec: SubagentSpec,
        *,
        context_summary: str | None = None,
        parent_session_id: str | None = None,
        parent_model: str | None = None,
    ) -> SubagentRun:
        """Start one subagent asynchronously and return its run handle."""
        run_id = uuid.uuid4().hex[:12]
        run = SubagentRun(run_id=run_id, spec=spec)
        self._runs[run_id] = run
        task = asyncio.create_task(
            self._run_subagent(
                run,
                context_summary=context_summary,
                parent_session_id=parent_session_id,
                parent_model=parent_model,
            ),
            name=f"subagent:{spec.role}:{run_id}",
        )
        self._tasks[run_id] = task
        return run

    async def wait(self, run_id: str) -> SubagentResult:
        """Wait for one spawned subagent to reach a terminal state."""
        task = self._tasks.get(run_id)
        if task is None:
            raise ValueError(f"Unknown subagent run: {run_id}")
        return await task

    async def spawn_and_wait(
        self,
        spec: SubagentSpec,
        *,
        context_summary: str | None = None,
        parent_session_id: str | None = None,
        parent_model: str | None = None,
    ) -> SubagentResult:
        """Convenience wrapper for a single synchronous subagent call."""
        run = self.spawn(
            spec,
            context_summary=context_summary,
            parent_session_id=parent_session_id,
            parent_model=parent_model,
        )
        return await self.wait(run.run_id)

    async def spawn_parallel(
        self,
        specs: list[SubagentSpec],
        *,
        context_summary: str | None = None,
        parent_session_id: str | None = None,
        parent_model: str | None = None,
    ) -> list[SubagentResult]:
        """Spawn multiple subagents and wait for all results in input order."""
        runs = [
            self.spawn(
                spec,
                context_summary=context_summary,
                parent_session_id=parent_session_id,
                parent_model=parent_model,
            )
            for spec in specs
        ]
        return list(await asyncio.gather(*(self.wait(run.run_id) for run in runs)))

    def get_run(self, run_id: str) -> SubagentRun | None:
        """Return the current execution handle for one run id."""
        return self._runs.get(run_id)

    async def _run_subagent(
        self,
        run: SubagentRun,
        *,
        context_summary: str | None,
        parent_session_id: str | None,
        parent_model: str | None,
    ) -> SubagentResult:
        self._record_event("subagent.started", "warning", run, None)
        result = await self._executor.execute(
            run.spec,
            run_id=run.run_id,
            context_summary=context_summary,
            parent_session_id=parent_session_id,
            parent_model=parent_model,
        )
        run.status = result.status
        run.session_id = result.session_id
        run.completed_at = result.completed_at
        severity = "success" if result.status == "completed" else "error"
        self._record_event(f"subagent.{result.status}", severity, run, result)
        return result

    def _record_event(
        self,
        kind: str,
        severity: str,
        run: SubagentRun,
        result: SubagentResult | None,
    ) -> None:
        if self._record_runtime_event is None:
            return
        metadata: dict[str, object] = {
            "subagentRole": run.spec.role,
            "sessionTarget": run.spec.session_target,
        }
        if result is not None:
            metadata["model"] = result.model
            metadata["budgetUsedUsd"] = result.budget_summary.get("total_cost_usd", 0.0)
            metadata["budgetMaxUsd"] = result.budget_summary.get("max_cost_usd", 0.0)
            if result.error:
                metadata["error"] = result.error
        self._record_runtime_event(
            category="task",
            kind=kind,
            severity=severity,
            message=f"Subagent {run.spec.role} {kind.rsplit('.', 1)[-1]}.",
            session_id=result.session_id if result is not None else run.session_id,
            run_id=run.run_id,
            source="subagent",
            metadata=metadata,
        )
