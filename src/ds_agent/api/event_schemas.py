"""Canonical backend/frontend event payload schemas.

Each TypedDict here is the single source of truth for an event emitted via
``context.emit(event_name, payload)`` or ``self._emit(event_name, payload)``.
The matching TypeScript interfaces live in
``electron/src/renderer/types/events.ts``.

Keep both files in sync when adding or changing events.
"""

from __future__ import annotations

from typing import TypedDict

# ---------------------------------------------------------------------------
# DS Workflow events
# ---------------------------------------------------------------------------


class WorkflowStepEvent(TypedDict):
    """``workflow.step`` - DS pipeline stage transition."""

    stage: str  # e.g. "data_loading", "profiling", "modeling"
    status: str  # "running" | "done" | "error"
    score: float | None


class QualityUpdateEvent(TypedDict):
    """``quality.update`` - per-stage quality score update."""

    stage: str
    score: float | None
    overall: float | None  # 0-100 overall quality score
    grade: str | None  # "A" | "B" | "C" | "D" | "F"


class ExperimentLogEvent(TypedDict):
    """``experiment.log`` - ML model training/evaluation result.

    Emitted by ``ExperimentTrackerHook`` after ``train_model`` or
    ``evaluate_model`` succeeds. Matches ``Experiment`` interface in
    ``workflowStore.ts``.
    """

    id: str  # unique experiment identifier
    model: str  # model algorithm / type
    isBaseline: bool
    metrics: dict[str, float]  # {"accuracy": 0.847, "roc_auc": 0.912, ...}
    trainingTime: float | None  # seconds
    timestamp: int  # Unix epoch milliseconds


class HarnessWarningEvent(TypedDict):
    """``harness.warning`` - DS harness quality warning."""

    id: str
    type: str
    severity: str  # "high" | "medium" | "low"
    message: str
    suggestion: str | None


class ProfileResultsEvent(TypedDict):
    """``profile.results`` - structured data profiling results.

    Emitted by ``ProfileResultsHook`` after ``data_profiler`` succeeds.
    """

    summary: str  # truncated profile output (max 500 chars)
    grade: str  # "A" | "B" | "C" | "D"
    rows: int
    columns: int
    missingPct: float  # 0-100
    issues: list[dict]  # [{"issue": "high_missing", "detail": "..."}]


# ---------------------------------------------------------------------------
# Budget / context events
# ---------------------------------------------------------------------------


class BudgetDetailEvent(TypedDict):
    """``budget.detail`` - token/cost usage update."""

    tokensUsed: int
    tokensMax: int
    costUsd: float
    costMax: float
    iterationsUsed: int
    iterationsMax: int


class BudgetWarningEvent(TypedDict):
    """``budget.warning`` - budget threshold notification."""

    dimension: str
    level: str
    pct: float
    message: str


class ContextStatusEvent(TypedDict):
    """``context.status`` - context window usage."""

    usedPct: float  # 0-100
    compressed: bool


# ---------------------------------------------------------------------------
# Approval events
# ---------------------------------------------------------------------------


class ApprovalEvent(TypedDict):
    """``approval.requested`` / ``approval.resolved`` - approval bus payload."""

    approvalId: str
    sessionId: str
    runId: str | None
    surface: str
    question: str
    kind: str
    metadata: dict[str, object]
    options: list[str]
    default: str | None
    status: str
    response: str | None
    source: str | None
    actor: str | None
    createdAt: float
    updatedAt: float
    resolvedAt: float | None


class SandboxViolationEvent(TypedDict):
    """``sandbox.violation`` - a single policy breach surfaced to the UI.

    Emitted once per `SandboxViolation` after a tool runs in the sandbox.
    The renderer uses these to render non-blocking toasts so the user
    learns when the sandbox stopped something the LLM tried to do.
    """

    kind: str  # "filesystem" | "network" | "subprocess" | "resource"
    detail: str
    blocked: bool
    sessionId: str | None
    runId: str | None
    tool: str
    timestamp: float


# ---------------------------------------------------------------------------
# File / artifact events
# ---------------------------------------------------------------------------


class FileCreatedEvent(TypedDict):
    """``file.created`` - a file was written in the workspace."""

    path: str  # workspace-relative path (forward slashes)
    type: str  # file extension without dot
    size: int  # bytes


class WorkspaceChangedEvent(TypedDict):
    """``workspace.changed`` - workspace contents changed; refresh file list."""

    tool: str


# ---------------------------------------------------------------------------
# Agent events
# ---------------------------------------------------------------------------


class AgentThinkingEvent(TypedDict):
    """``agent.thinking`` - LLM extended thinking block."""

    thinking: str


class AgentDeltaEvent(TypedDict):
    """``agent.delta`` - streaming LLM token delta."""

    delta: str


class AgentDoneEvent(TypedDict):
    """``agent.done`` - agent turn completed."""

    content: str
    iterations: int
    totalCostUsd: float
