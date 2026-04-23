"""Domain entities for runtime session/run/task tracking."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum


class RuntimeStatus(StrEnum):
    """Lifecycle states shared by runs and background tasks."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class RuntimeSession:
    """One logical session visible to a runtime surface."""

    session_id: str
    surface: str
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    last_run_id: str | None = None


@dataclass(slots=True)
class RunState:
    """Tracked execution unit for one agent turn."""

    run_id: str
    session_id: str
    surface: str
    message: str
    status: RuntimeStatus = RuntimeStatus.RUNNING
    created_at: float = field(default_factory=time.time)
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    task_id: str | None = None
    error: str | None = None
    result_preview: str | None = None
    cost_usd: float = 0.0
    resumed_from_checkpoint: bool = False
    branched_from_run_id: str | None = None
    rerun_from_node_id: str | None = None


@dataclass(slots=True)
class TaskState:
    """Tracked asyncio task bound to a run."""

    task_id: str
    run_id: str
    status: RuntimeStatus = RuntimeStatus.RUNNING
    created_at: float = field(default_factory=time.time)
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    error: str | None = None
