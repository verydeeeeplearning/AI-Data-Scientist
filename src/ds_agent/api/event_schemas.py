"""Canonical backend/frontend event payload schemas.

Each TypedDict here is the single source of truth for an event emitted via
``context.emit(event_name, payload)`` or ``self._emit(event_name, payload)``.
The matching TypeScript interfaces live in
``electron/src/renderer/types/events.ts``.

Keep both files in sync when adding or changing events.
"""

from __future__ import annotations

from typing import NotRequired, Required, TypedDict

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


class VerifierAutoRunEvent(TypedDict, total=False):
    """``verifier.auto_run`` - auto-verifier execution telemetry."""

    sessionId: Required[str | None]
    runId: Required[str | None]
    taskId: Required[str]
    mode: Required[str]
    status: Required[str]  # "success" | "timeout" | "error"
    durationMs: Required[int]
    verdictId: str
    result: str
    blockingIssueCount: int
    confidenceScore: float
    confidenceGrade: str
    errorType: str


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


class MissionGoalEvent(TypedDict, total=False):
    title: str
    successCriteria: list[str]


class MissionDataSourceEvent(TypedDict, total=False):
    type: str
    label: str
    rowCount: int


class MissionConstraintsEvent(TypedDict, total=False):
    language: str
    requiresApproval: bool
    localOnlyModel: bool


class MissionStageEvent(TypedDict, total=False):
    current: int
    total: int
    label: str


class MissionModelEvent(TypedDict, total=False):
    primary: str
    fallbacks: list[str]
    capabilities: list[str]


class MissionBudgetEvent(TypedDict, total=False):
    spentUsd: float
    limitUsd: float
    elapsedSec: float
    nearLimit: bool


class MissionConnectionEvent(TypedDict, total=False):
    state: str
    latencyMs: float | None


class MissionContextUpdatedEvent(TypedDict, total=False):
    """``mission.context.updated`` - partial mission header patch."""

    sessionId: str
    goal: MissionGoalEvent
    dataSources: list[MissionDataSourceEvent]
    deliverables: list[str]
    constraints: MissionConstraintsEvent
    stage: MissionStageEvent
    mode: str
    model: MissionModelEvent
    budget: MissionBudgetEvent
    connection: MissionConnectionEvent


# ---------------------------------------------------------------------------
# Plan / reasoning events
# ---------------------------------------------------------------------------


class PlanNodePatchEvent(TypedDict, total=False):
    """Partial plan-node patch used by ``plan.updated``."""

    parentId: str | None
    label: str
    description: str
    status: str
    estimatedDurationSec: float
    startedAt: int
    completedAt: int
    reasoningRefs: list[str]
    toolEventRefs: list[str]
    children: list[PlanNodeEvent]


class PlanNodeEvent(PlanNodePatchEvent):
    """Recursive plan node used by plan-tree events.

    Inherits the optional patch fields from ``PlanNodePatchEvent`` but additionally
    requires ``id`` so consumers can address the node in tree traversals.
    """

    id: str


class ReplanDiffEvent(TypedDict):
    """``plan.replanned`` - plan diff after a re-plan."""

    oldNodes: list[PlanNodeEvent]
    newNodes: list[PlanNodeEvent]
    added: list[str]
    removed: list[str]
    modified: list[str]
    reason: str


class PlanCreatedEvent(TypedDict):
    """``plan.created`` - a new plan tree was produced."""

    planTree: PlanNodeEvent


class PlanUpdatedEvent(TypedDict):
    """``plan.updated`` - one plan node changed in-place."""

    nodeId: str
    updates: PlanNodePatchEvent


class PlanReplannedEvent(TypedDict):
    """``plan.replanned`` - a plan was rebuilt and diffed."""

    diff: ReplanDiffEvent


class ReasoningEmittedEvent(TypedDict, total=False):
    """``reasoning.emitted`` - first-slice reasoning trace payload.

    Wave 3 first slice emits ``thinking`` from the existing provider thinking
    path so the renderer can start consuming reasoning traces before the full
    4-tuple plan-linked contract lands.
    """

    emittedAt: Required[int]
    id: NotRequired[str]
    planNodeId: NotRequired[str]
    thinking: NotRequired[str]
    hypothesis: NotRequired[str]
    action: NotRequired[str]
    observation: NotRequired[str]
    decision: NotRequired[str]


# ---------------------------------------------------------------------------
# Stream events
# ---------------------------------------------------------------------------


class StreamDoneEvent(TypedDict, total=False):
    """``stream.done`` - terminal successful stream payload."""

    content: Required[str]
    cost: float
    messageId: str | None
    cards: list[dict[str, object]]


class StreamErrorEvent(TypedDict, total=False):
    """``stream.error`` - terminal failed stream payload."""

    message: str
    code: str
    messageId: str | None


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
