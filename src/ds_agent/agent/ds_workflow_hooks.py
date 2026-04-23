"""DS workflow hooks — automated verification for data science best practices.

Implements harness engineering principle: "enforce via code (hooks), not just docs."
Each hook monitors tool execution and emits events for the frontend UI.
"""

from __future__ import annotations

import copy
import re
import time
from dataclasses import dataclass

import structlog

from ds_agent.agent.hooks import (
    HookContext,
    PostToolUseResult,
    PreToolUseResult,
    ToolHook,
)
from ds_agent.application.services.ab_test_analyzer import ABTestAnalyzer
from ds_agent.application.services.drift_analyzer import DriftAnalyzer
from ds_agent.domain.value_objects.analysis_stage import ORDERED_STAGES, AnalysisStage

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Tracked tools: stage transitions only happen for tools listed here.
# Untracked tools (e.g. execute_code as general utility, read_file, bash)
# are intentionally excluded to avoid spurious stage transitions — a general
# utility tool is not a reliable proxy for the DS workflow stage being executed.
# To add a tool: map it to the DS_WORKFLOW_STAGES stage it primarily represents.
# Note: execute_code and run_code are deliberately absent; they serve as
# cross-stage general utilities (used in baseline guard, quality checks, etc.)
# and mapping them would cause incorrect stage jumps when the agent uses them
# outside the context of that stage's primary tool.
TOOL_TO_STAGE: dict[str, str] = {
    "create_task_contract": AnalysisStage.SCOPING.value,
    "data_loader": AnalysisStage.DATA_LOADING.value,
    "data_profiler": AnalysisStage.PROFILING.value,
    "run_eda": AnalysisStage.EDA.value,
    "feature_engineer": AnalysisStage.FEATURE_ENG.value,
    "train_model": AnalysisStage.MODELING.value,
    "evaluate_model": AnalysisStage.EVALUATION.value,
    "generate_report": AnalysisStage.REPORTING.value,
}

DS_WORKFLOW_STAGES: list[str] = [stage.value for stage in ORDERED_STAGES]

PLAN_ROOT_ID = "ds_workflow_plan"


@dataclass(frozen=True)
class StagePlanMeta:
    label: str
    description: str
    estimated_duration_sec: float


STAGE_PLAN_METADATA: dict[str, StagePlanMeta] = {
    AnalysisStage.SCOPING.value: StagePlanMeta(
        label="Scope mission",
        description="Clarify the objective, success metric, constraints, and delivery target.",
        estimated_duration_sec=120.0,
    ),
    AnalysisStage.DATA_LOADING.value: StagePlanMeta(
        label="Load data",
        description="Ingest workspace datasets and verify they can be used safely.",
        estimated_duration_sec=90.0,
    ),
    AnalysisStage.PROFILING.value: StagePlanMeta(
        label="Profile data",
        description="Inspect shape, missingness, schema quality, and obvious defects.",
        estimated_duration_sec=180.0,
    ),
    AnalysisStage.EDA.value: StagePlanMeta(
        label="Explore data",
        description="Check distributions, relationships, and early hypotheses.",
        estimated_duration_sec=240.0,
    ),
    AnalysisStage.FEATURE_ENG.value: StagePlanMeta(
        label="Engineer features",
        description="Prepare transformations and derived signals for modeling.",
        estimated_duration_sec=240.0,
    ),
    AnalysisStage.MODELING.value: StagePlanMeta(
        label="Train model",
        description="Fit baseline and candidate models against the prepared data.",
        estimated_duration_sec=300.0,
    ),
    AnalysisStage.EVALUATION.value: StagePlanMeta(
        label="Evaluate model",
        description="Measure generalization, error modes, and decision readiness.",
        estimated_duration_sec=180.0,
    ),
    AnalysisStage.REPORTING.value: StagePlanMeta(
        label="Report findings",
        description="Summarize outcomes, risks, and next actions for delivery.",
        estimated_duration_sec=120.0,
    ),
}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _stage_status_to_plan_status(status: str) -> str:
    if status == "done":
        return "completed"
    if status == "error":
        return "failed"
    return status


def _root_plan_status(stage_statuses: list[str]) -> str:
    if any(status == "running" for status in stage_statuses):
        return "running"
    if any(status == "failed" for status in stage_statuses):
        return "failed"
    if stage_statuses and all(status == "completed" for status in stage_statuses):
        return "completed"
    if any(status in {"completed", "skipped"} for status in stage_statuses):
        return "running"
    if stage_statuses and all(status == "skipped" for status in stage_statuses):
        return "skipped"
    return "pending"


def _flatten_plan_tree(node: dict[str, object] | None) -> list[dict[str, object]]:
    """Flatten a plan tree into a list of plan-node dicts (root first, DFS)."""
    if node is None:
        return []
    flat: list[dict[str, object]] = [node]
    children = node.get("children")
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                flat.extend(_flatten_plan_tree(child))
    return flat


def _plan_node_signature(node: dict[str, object]) -> tuple[object, ...]:
    """Return the tuple used to detect ``modified`` plan nodes.

    Spec: changes to ``label``, ``description``, ``status`` or
    ``estimatedDurationSec`` cause the node to appear in ``modified``.
    """
    return (
        node.get("label"),
        node.get("description"),
        node.get("status"),
        node.get("estimatedDurationSec"),
    )


def _compute_plan_diff(
    old_nodes: list[dict[str, object]],
    new_nodes: list[dict[str, object]],
) -> tuple[list[str], list[str], list[str]]:
    """Compute (added, removed, modified) id lists between two plan node sets."""
    old_by_id: dict[str, dict[str, object]] = {}
    for node in old_nodes:
        node_id = node.get("id")
        if isinstance(node_id, str):
            old_by_id[node_id] = node
    new_by_id: dict[str, dict[str, object]] = {}
    for node in new_nodes:
        node_id = node.get("id")
        if isinstance(node_id, str):
            new_by_id[node_id] = node
    added = sorted(new_by_id.keys() - old_by_id.keys())
    removed = sorted(old_by_id.keys() - new_by_id.keys())
    modified: list[str] = []
    for node_id in sorted(old_by_id.keys() & new_by_id.keys()):
        if _plan_node_signature(old_by_id[node_id]) != _plan_node_signature(new_by_id[node_id]):
            modified.append(node_id)
    return added, removed, modified


# ---------------------------------------------------------------------------
# 1. WorkflowTrackerHook — tracks DS pipeline stage progression
# ---------------------------------------------------------------------------


class WorkflowTrackerHook(ToolHook):
    """Tracks which DS workflow stages have been executed.

    Replan trigger contract:
        ``mark_replan(context, reason)`` is the explicit replan trigger. It is
        called either by the agent core when a stage transitions back from a
        terminal state (``done``/``error``) into ``pending``/``running`` (e.g.,
        a user requests re-execution) or programmatically by tests/features
        that mutate ``STAGE_PLAN_METADATA`` mid-run. The hook itself ALSO
        auto-emits ``plan.replanned`` when ``pre_tool_use`` re-enters a stage
        that previously completed (``done``/``error``), without requiring a
        manual ``mark_replan`` call.

    Reasoning↔plan-node linkage:
        ``record_reasoning_ref(reasoning_id)`` appends a reasoning event id to
        the currently active stage node's ``reasoningRefs`` and emits a
        ``plan.updated`` patch so the renderer can display the link inline.
    """

    name = "workflow_tracker"
    priority = 5

    def __init__(self) -> None:
        self._stages: dict[str, str] = {s: "pending" for s in DS_WORKFLOW_STAGES}
        self._stage_started_at: dict[str, int | None] = {s: None for s in DS_WORKFLOW_STAGES}
        self._stage_completed_at: dict[str, int | None] = {s: None for s in DS_WORKFLOW_STAGES}
        self._stage_reasoning_refs: dict[str, list[str]] = {
            s: [] for s in DS_WORKFLOW_STAGES
        }
        self._current_stage_id: str | None = None
        self._plan_emitted = False
        self._previous_plan_tree: dict[str, object] | None = None

    @property
    def stages(self) -> dict[str, str]:
        return dict(self._stages)

    def current_active_stage_id(self) -> str | None:
        """Return the id of the first stage currently in ``running`` status.

        This is the authoritative "what is happening right now" accessor.
        Prefer this over ``current_stage_id()`` whenever you need to know
        which stage is actively executing (e.g. for reasoning-ref attachment).
        """
        for stage in DS_WORKFLOW_STAGES:
            if self._stages.get(stage) == "running":
                return stage
        return None

    def current_stage_id(self) -> str | None:
        """Return the most-recently *entered* (pre_tool_use) stage id.

        Semantics: this is set to ``stage`` when pre_tool_use fires for a
        tracked tool, i.e. the moment the stage transitions to "running".
        It is intentionally NOT updated in post_tool_use so that it always
        reflects the last stage that was *started*, not the last stage that
        *completed*.

        Use ``current_active_stage_id()`` when you need the stage that is
        currently in "running" status.  Use ``current_stage_id()`` when you
        need the stage the agent most recently began working on (e.g. for
        crash-recovery or session-resume context).

        The value persisted to working memory under the ``current_stage``
        field uses this accessor's semantics: "last stage entered/started".
        """
        return self._current_stage_id

    def current_stage_started_at(self) -> int | None:
        """Return the current stage's start timestamp in milliseconds."""
        if self._current_stage_id is None:
            return None
        return self._stage_started_at.get(self._current_stage_id)

    async def on_session_init(self, context: HookContext) -> str | None:
        self.reset()
        self._emit_plan_created(context)
        self._complete_scoping_from_active_contract(context)
        return None

    async def pre_tool_use(
        self, tool_name: str, arguments: dict, context: HookContext
    ) -> PreToolUseResult:
        self._ensure_plan_emitted(context)
        stage = TOOL_TO_STAGE.get(tool_name)
        if stage:
            self._current_stage_id = stage
            previous_status = self._stages.get(stage)
            re_entering_terminal = previous_status in {"done", "error"}
            if previous_status == "pending" or re_entering_terminal:
                started_at = _now_ms()
                self._stages[stage] = "running"
                self._stage_started_at[stage] = started_at
                if re_entering_terminal:
                    # Reset completion timestamp + reasoning refs so the new
                    # attempt isn't conflated with the prior run.
                    self._stage_completed_at[stage] = None
                    self._stage_reasoning_refs[stage] = []
                # Gap 3-2: Durable checkpoint — emit immediately after the
                # stage is set to "running" so that consumers (e.g. working
                # memory writer) can persist current_stage before the tool
                # body executes.  This ensures that a crash during a long-
                # running tool (e.g. train_model) does not lose the entered
                # stage.  The working_memory_store is not directly accessible
                # from inside the hook; instead we rely on the event bus
                # contract: any listener subscribed to "workflow.checkpoint"
                # MUST write {"current_stage": stage} to working memory
                # atomically before acknowledging the event.
                context.emit(
                    "workflow.checkpoint",
                    {"current_stage": stage, "status": "running", "started_at": started_at},
                )
                context.emit(
                    "workflow.step",
                    {"stage": stage, "status": "running", "stages": self._stages},
                )
                context.emit(
                    "plan.updated",
                    {
                        "nodeId": stage,
                        "updates": {
                            "status": "running",
                            "startedAt": started_at,
                        },
                    },
                )
                context.emit(
                    "plan.updated",
                    {
                        "nodeId": PLAN_ROOT_ID,
                        "updates": self._build_root_patch(),
                    },
                )
                if re_entering_terminal:
                    self._emit_plan_replanned(
                        context,
                        reason=f"Stage '{stage}' re-executed",
                    )
                else:
                    self._snapshot_plan_tree()
        return PreToolUseResult()

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        self._ensure_plan_emitted(context)
        stage = TOOL_TO_STAGE.get(tool_name)
        if stage:
            # Gap 3-3: Do NOT update _current_stage_id here. _current_stage_id
            # tracks "last stage entered (pre_tool_use)", not "last stage
            # completed (post_tool_use)".  Updating it here would make
            # current_stage_id() return the last *completed* stage, which
            # contradicts the "last entered / crash-recovery" semantics
            # documented on current_stage_id() and stored in working memory.
            # Use current_active_stage_id() to find the currently *running*
            # stage, and current_stage_id() for the last *started* stage.
            completed_at = _now_ms()
            self._stages[stage] = "error" if is_error else "done"
            self._stage_completed_at[stage] = completed_at
            context.emit(
                "workflow.step",
                {"stage": stage, "status": self._stages[stage], "stages": self._stages},
            )
            context.emit(
                "plan.updated",
                {
                    "nodeId": stage,
                    "updates": {
                        "status": _stage_status_to_plan_status(self._stages[stage]),
                        "completedAt": completed_at,
                    },
                },
            )
            context.emit(
                "plan.updated",
                {
                    "nodeId": PLAN_ROOT_ID,
                    "updates": self._build_root_patch(),
                },
            )
            self._snapshot_plan_tree()
        return PostToolUseResult()

    def mark_replan(
        self,
        context: HookContext,
        *,
        reason: str,
    ) -> dict[str, object] | None:
        """Emit a ``plan.replanned`` event with a diff vs the previous snapshot.

        Returns the emitted diff payload (for caller introspection / tests),
        or ``None`` when the plan is unchanged AND the previous snapshot is
        absent (i.e. nothing meaningful to diff against).
        """

        return self._emit_plan_replanned(context, reason=reason)

    def record_reasoning_ref(
        self,
        context: HookContext,
        reasoning_id: str,
        *,
        stage: str | None = None,
    ) -> str | None:
        """Append ``reasoning_id`` to the active stage's reasoningRefs.

        Returns the stage id the ref was attached to, or ``None`` when no
        active stage is available.
        """

        target_stage = stage or self.current_active_stage_id()
        if target_stage is None or target_stage not in self._stage_reasoning_refs:
            return None
        if not reasoning_id:
            return None
        refs = self._stage_reasoning_refs[target_stage]
        if reasoning_id in refs:
            return target_stage
        refs.append(reasoning_id)
        context.emit(
            "plan.updated",
            {
                "nodeId": target_stage,
                "updates": {"reasoningRefs": list(refs)},
            },
        )
        self._snapshot_plan_tree()
        return target_stage

    def get_completeness(self) -> dict:
        done = sum(1 for s in self._stages.values() if s == "done")
        total = len(self._stages)
        return {
            "completed": done,
            "total": total,
            "pct": round(done / total * 100) if total else 0,
            "missing": [s for s, v in self._stages.items() if v == "pending"],
        }

    def reset(self) -> None:
        self._stages = {s: "pending" for s in DS_WORKFLOW_STAGES}
        self._stage_started_at = {s: None for s in DS_WORKFLOW_STAGES}
        self._stage_completed_at = {s: None for s in DS_WORKFLOW_STAGES}
        self._stage_reasoning_refs = {s: [] for s in DS_WORKFLOW_STAGES}
        self._current_stage_id = None
        self._plan_emitted = False
        self._previous_plan_tree = None

    def restore(
        self,
        *,
        current_stage_id: str | None = None,
        stage_statuses: dict[str, str] | None = None,
    ) -> None:
        """Rehydrate tracker state from persisted working memory on session resume.

        Called after reset() so that recovered stage is not discarded by
        on_session_init. Only updates stages that exist in DS_WORKFLOW_STAGES.
        """
        if stage_statuses:
            for stage, status in stage_statuses.items():
                if stage in self._stages and status in {"pending", "running", "done", "error"}:
                    self._stages[stage] = status
        if current_stage_id and current_stage_id in self._stages:
            self._current_stage_id = current_stage_id

    def _ensure_plan_emitted(self, context: HookContext) -> None:
        if not self._plan_emitted:
            self._emit_plan_created(context)

    def _complete_scoping_from_active_contract(self, context: HookContext) -> None:
        if context.active_task_contract is None:
            return
        stage = AnalysisStage.SCOPING.value
        if self._stages.get(stage) == "done":
            return
        completed_at = _now_ms()
        self._current_stage_id = stage
        self._stages[stage] = "done"
        self._stage_started_at[stage] = completed_at
        self._stage_completed_at[stage] = completed_at
        context.emit(
            "workflow.step",
            {"stage": stage, "status": "done", "stages": self._stages},
        )
        context.emit(
            "plan.updated",
            {
                "nodeId": stage,
                "updates": {
                    "status": _stage_status_to_plan_status(self._stages[stage]),
                    "startedAt": completed_at,
                    "completedAt": completed_at,
                },
            },
        )
        context.emit(
            "plan.updated",
            {
                "nodeId": PLAN_ROOT_ID,
                "updates": self._build_root_patch(),
            },
        )
        self._snapshot_plan_tree()

    def _emit_plan_created(self, context: HookContext) -> None:
        tree = self._build_plan_tree()
        context.emit("plan.created", {"planTree": tree})
        self._plan_emitted = True
        self._previous_plan_tree = copy.deepcopy(tree)

    def _snapshot_plan_tree(self) -> None:
        self._previous_plan_tree = copy.deepcopy(self._build_plan_tree())

    def _emit_plan_replanned(
        self,
        context: HookContext,
        *,
        reason: str,
    ) -> dict[str, object] | None:
        previous = self._previous_plan_tree
        new_tree = self._build_plan_tree()
        old_nodes = _flatten_plan_tree(previous) if previous is not None else []
        new_nodes = _flatten_plan_tree(new_tree)
        added, removed, modified = _compute_plan_diff(old_nodes, new_nodes)
        if previous is None and not added and not removed and not modified:
            # Nothing to compare against AND nothing changed — skip the emit
            # so the renderer doesn't see noise.
            self._previous_plan_tree = copy.deepcopy(new_tree)
            return None
        diff_payload: dict[str, object] = {
            "oldNodes": old_nodes,
            "newNodes": new_nodes,
            "added": added,
            "removed": removed,
            "modified": modified,
            "reason": reason,
        }
        context.emit("plan.replanned", {"diff": diff_payload})
        self._previous_plan_tree = copy.deepcopy(new_tree)
        return diff_payload

    def _build_plan_tree(self) -> dict[str, object]:
        child_nodes = [self._build_stage_node(stage) for stage in DS_WORKFLOW_STAGES]
        root_status = _root_plan_status([str(node["status"]) for node in child_nodes])
        root_node: dict[str, object] = {
            "id": PLAN_ROOT_ID,
            "label": "Data Science Workflow",
            "description": "Stage-based execution plan emitted by the workflow tracker.",
            "status": root_status,
            "reasoningRefs": [],
            "toolEventRefs": [],
            "children": child_nodes,
        }
        root_started_at = self._root_started_at()
        if root_started_at is not None:
            root_node["startedAt"] = root_started_at
        root_completed_at = self._root_completed_at(root_status)
        if root_completed_at is not None:
            root_node["completedAt"] = root_completed_at
        return root_node

    def _build_stage_node(self, stage: str) -> dict[str, object]:
        metadata = STAGE_PLAN_METADATA[stage]
        node: dict[str, object] = {
            "id": stage,
            "parentId": PLAN_ROOT_ID,
            "label": metadata.label,
            "description": metadata.description,
            "status": _stage_status_to_plan_status(self._stages[stage]),
            "estimatedDurationSec": metadata.estimated_duration_sec,
            "reasoningRefs": list(self._stage_reasoning_refs.get(stage, [])),
            "toolEventRefs": [],
            "children": [],
        }
        started_at = self._stage_started_at[stage]
        if started_at is not None:
            node["startedAt"] = started_at
        completed_at = self._stage_completed_at[stage]
        if completed_at is not None:
            node["completedAt"] = completed_at
        return node

    def _build_root_patch(self) -> dict[str, object]:
        stage_statuses = [
            _stage_status_to_plan_status(self._stages[stage]) for stage in DS_WORKFLOW_STAGES
        ]
        patch: dict[str, object] = {
            "status": _root_plan_status(stage_statuses),
        }
        root_started_at = self._root_started_at()
        if root_started_at is not None:
            patch["startedAt"] = root_started_at
        root_completed_at = self._root_completed_at(str(patch["status"]))
        if root_completed_at is not None:
            patch["completedAt"] = root_completed_at
        return patch

    def _root_started_at(self) -> int | None:
        started = [value for value in self._stage_started_at.values() if value is not None]
        if not started:
            return None
        return min(started)

    def _root_completed_at(self, status: str) -> int | None:
        if status not in {"completed", "failed"}:
            return None
        completed = [value for value in self._stage_completed_at.values() if value is not None]
        if not completed:
            return None
        return max(completed)


# ---------------------------------------------------------------------------
# 2. LeakageDetectionHook — detects data leakage patterns in FE code
# ---------------------------------------------------------------------------

_LEAKAGE_PATTERNS: list[tuple[str, str]] = [
    (
        r"\.fit_transform\(.*(?:X_test|test|val)",
        "fit_transform applied to test/val data — fit on train only, then transform test",
    ),
    (
        r"\.fit\(.*(?:X_test|test|val)",
        "fit() called on test/val data — fit on train only",
    ),
    (
        r"(?:StandardScaler|MinMaxScaler|RobustScaler|LabelEncoder|OneHotEncoder)"
        r".*\.fit\((?!.*train)",
        "Scaler/encoder fit may include non-train data — verify fit uses train only",
    ),
]


class LeakageDetectionHook(ToolHook):
    """Scans feature engineering code for data leakage patterns."""

    name = "leakage_detection"
    priority = 30

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if tool_name != "feature_engineer" or is_error:
            return PostToolUseResult()

        code = arguments.get("code", "")
        warnings = self._scan(code)

        if warnings:
            context.emit(
                "harness.warning",
                {
                    "type": "leakage",
                    "severity": "high",
                    "message": "Data leakage pattern detected",
                    "details": warnings,
                },
            )
            warning_text = "\n\n---\n**Leakage Detection**:\n" + "\n".join(
                f"- {w}" for w in warnings
            )
            return PostToolUseResult(modified_result=result + warning_text)

        return PostToolUseResult(modified_result=result + "\n\n---\n**Leakage check**: passed")

    @staticmethod
    def _scan(code: str) -> list[str]:
        warnings: list[str] = []
        for pattern, message in _LEAKAGE_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                warnings.append(message)
        return warnings


# ---------------------------------------------------------------------------
# 3. BaselineGuardHook — warns if no baseline before model training
# ---------------------------------------------------------------------------


class BaselineGuardHook(ToolHook):
    """Warns when train_model is called without a baseline being established."""

    name = "baseline_guard"
    priority = 25

    def __init__(self) -> None:
        self._baseline_established = False

    @property
    def baseline_established(self) -> bool:
        return self._baseline_established

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if tool_name in ("train_model", "execute_code") and not is_error:
            code = arguments.get("code", "")
            if _has_baseline_keywords(code):
                self._baseline_established = True
        return PostToolUseResult()

    async def pre_tool_use(
        self, tool_name: str, arguments: dict, context: HookContext
    ) -> PreToolUseResult:
        if tool_name == "train_model" and not self._baseline_established:
            context.emit(
                "harness.warning",
                {
                    "type": "baseline_missing",
                    "severity": "medium",
                    "message": "No baseline established before model training",
                    "suggestion": (
                        "Train a DummyClassifier/DummyRegressor first "
                        "to establish a baseline for comparison"
                    ),
                },
            )
        return PreToolUseResult()

    def reset(self) -> None:
        self._baseline_established = False


def _has_baseline_keywords(code: str) -> bool:
    lower = code.lower()
    return any(
        kw in lower
        for kw in [
            "dummyclassifier",
            "dummyregressor",
            "baseline",
            "majority_class",
            "most_frequent",
            "zeroruler",
        ]
    )


# ---------------------------------------------------------------------------
# 4. OverfittingDetectorHook — detects train/test performance gap
# ---------------------------------------------------------------------------

_METRIC_PATTERN = re.compile(
    r"(?:train|training)[\s_]*(?:acc|accuracy|f1|auc|score|rmse|mae|r2)"
    r"[\s:=]*([0-9]*\.?[0-9]+)",
    re.IGNORECASE,
)
_TEST_METRIC_PATTERN = re.compile(
    r"(?:test|val|validation)[\s_]*(?:acc|accuracy|f1|auc|score|rmse|mae|r2)"
    r"[\s:=]*([0-9]*\.?[0-9]+)",
    re.IGNORECASE,
)


class OverfittingDetectorHook(ToolHook):
    """Detects large train-test performance gap indicating overfitting."""

    name = "overfitting_detector"
    priority = 35

    OVERFITTING_THRESHOLD = 0.15  # 15% gap

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if tool_name not in ("train_model", "evaluate_model") or is_error:
            return PostToolUseResult()

        train_score, test_score = self._extract_scores(result)
        if train_score is not None and test_score is not None:
            gap = train_score - test_score
            if gap > self.OVERFITTING_THRESHOLD:
                context.emit(
                    "harness.warning",
                    {
                        "type": "overfitting",
                        "severity": "high",
                        "message": (
                            f"Overfitting detected: train={train_score:.3f}, "
                            f"test={test_score:.3f} (gap={gap:.3f})"
                        ),
                        "suggestion": (
                            "Increase regularization, reduce model complexity, "
                            "or add more training data"
                        ),
                    },
                )
                warning_text = (
                    f"\n\n---\n**Overfitting warning**: "
                    f"train={train_score:.3f}, test={test_score:.3f} (gap={gap:.3f})"
                )
                return PostToolUseResult(modified_result=result + warning_text)

        return PostToolUseResult()

    @staticmethod
    def _extract_scores(text: str) -> tuple[float | None, float | None]:
        train_match = _METRIC_PATTERN.search(text)
        test_match = _TEST_METRIC_PATTERN.search(text)
        train_score = float(train_match.group(1)) if train_match else None
        test_score = float(test_match.group(1)) if test_match else None
        return train_score, test_score


# ---------------------------------------------------------------------------
# 5. StageQualityHook — scores each DS stage based on quality rubric
# ---------------------------------------------------------------------------

_STAGE_CHECKS: dict[str, list[tuple[str, list[str], int, bool]]] = {
    # (check_name, keywords, points, is_critical)
    AnalysisStage.PROFILING.value: [
        ("missing_analysis", ["missing", "null", "isnull"], 25, False),
        ("distribution_analysis", ["mean", "std", "describe"], 25, False),
        ("outlier_detection", ["outlier", "iqr", "z-score", "boxplot"], 25, False),
        ("quality_grade", ["quality_grade", "grade"], 25, False),
    ],
    AnalysisStage.EDA.value: [
        (
            "statistical_test",
            ["ttest", "chi2", "pearsonr", "spearmanr", "f_oneway", "pvalue"],
            30,
            False,
        ),
        ("visualization", ["savefig", "plt.save", "plot"], 20, False),
        ("hypothesis", ["hypothesis", "hypothes", "expect", "predict"], 20, False),
        ("correlation", ["corr()", "heatmap", "pearson"], 15, False),
        ("outlier_analysis", ["outlier", "iqr", "z-score"], 15, False),
    ],
    AnalysisStage.FEATURE_ENG.value: [
        ("train_test_split", ["train_test_split", "x_train"], 40, True),
        (
            "encoding",
            ["labelencoder", "onehotencoder", "targetencoder", "get_dummies"],
            20,
            False,
        ),
        ("scaling", ["standardscaler", "minmaxscaler", "robustscaler"], 20, False),
        ("leakage_check", [], 20, True),  # scored by warning absence
    ],
    AnalysisStage.MODELING.value: [
        (
            "baseline",
            ["dummyclassifier", "dummyregressor", "baseline", "majority_class"],
            30,
            True,
        ),
        (
            "cross_validation",
            ["cross_val_score", "stratifiedkfold", "kfold", "cross_validate"],
            25,
            False,
        ),
        (
            "multiple_models",
            ["randomforest", "lightgbm", "xgboost", "logistic", "linear"],
            20,
            False,
        ),
        (
            "hyperparameter_tuning",
            ["optuna", "gridsearchcv", "randomizedsearchcv"],
            15,
            False,
        ),
        ("class_imbalance", ["class_weight", "smote", "balanced"], 10, False),
    ],
    AnalysisStage.EVALUATION.value: [
        ("test_set_eval", ["x_test", "test_data", "holdout"], 30, True),
        (
            "multiple_metrics",
            ["accuracy", "f1", "auc", "rmse", "mae", "precision", "recall"],
            20,
            False,
        ),
        (
            "error_analysis",
            ["confusion_matrix", "residual", "worst_pred", "misclassif"],
            20,
            False,
        ),
        (
            "feature_importance",
            ["shap", "permutation_importance", "feature_importances_"],
            15,
            False,
        ),
        (
            "fairness",
            ["demographic_parity", "equal_opportunity", "protected"],
            15,
            False,
        ),
    ],
    AnalysisStage.REPORTING.value: [
        ("summary", ["summary", "conclusion", "executive"], 25, False),
        ("limitations", ["limitation", "caveat", "risk", "weakness"], 25, False),
        ("recommendations", ["recommend", "suggestion", "next_step"], 25, False),
        ("model_card", ["model_card", "model card"], 25, False),
    ],
}

# Map tool names to stage quality checks
_TOOL_TO_QUALITY_STAGE: dict[str, str] = {
    "data_profiler": AnalysisStage.PROFILING.value,
    "run_eda": AnalysisStage.EDA.value,
    "feature_engineer": AnalysisStage.FEATURE_ENG.value,
    "train_model": AnalysisStage.MODELING.value,
    "evaluate_model": AnalysisStage.EVALUATION.value,
    "generate_report": AnalysisStage.REPORTING.value,
}


class StageQualityHook(ToolHook):
    """Scores each DS workflow stage based on quality rubric checks."""

    name = "stage_quality"
    priority = 45

    def __init__(self) -> None:
        self._scores: dict[str, int] = {}
        self._checks: dict[str, list[dict]] = {}

    @property
    def scores(self) -> dict[str, int]:
        return dict(self._scores)

    @property
    def all_checks(self) -> dict[str, list[dict]]:
        return dict(self._checks)

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        stage = _TOOL_TO_QUALITY_STAGE.get(tool_name)
        if not stage or is_error:
            return PostToolUseResult()

        code = arguments.get("code", "")
        combined_text = (code + " " + result).lower()

        score, checks = self._score_stage(stage, combined_text)
        self._scores[stage] = score
        self._checks[stage] = checks

        context.emit(
            "quality.update",
            {
                "stage": stage,
                "score": score,
                "checks": checks,
            },
        )
        return PostToolUseResult()

    def get_overall_score(self) -> tuple[int, str]:
        """Compute weighted overall score and grade."""
        weights = {
            "profiling": 0.10,
            "eda": 0.15,
            "feature_eng": 0.15,
            "modeling": 0.25,
            "evaluation": 0.25,
            "reporting": 0.10,
        }
        total = 0.0
        weight_sum = 0.0
        for stage, weight in weights.items():
            if stage in self._scores:
                total += self._scores[stage] * weight
                weight_sum += weight

        overall = round(total / weight_sum) if weight_sum > 0 else 0
        grade = _score_to_grade(overall)
        return overall, grade

    def reset(self) -> None:
        self._scores.clear()
        self._checks.clear()

    @staticmethod
    def _score_stage(stage: str, text: str) -> tuple[int, list[dict]]:
        checks_def = _STAGE_CHECKS.get(stage, [])
        checks: list[dict] = []
        score = 0

        for check_name, keywords, points, critical in checks_def:
            # Special case: leakage_check is scored by absence of warnings
            if check_name == "leakage_check":
                passed = "leakage" not in text or "leakage check" in text
            else:
                passed = any(kw in text for kw in keywords) if keywords else False
            checks.append({"name": check_name, "passed": passed, "critical": critical})
            if passed:
                score += points

        # CRITICAL penalty: -30 per failed critical check
        for check in checks:
            if check.get("critical") and not check["passed"]:
                score = max(0, score - 30)

        return min(100, score), checks


# ---------------------------------------------------------------------------
# 5b. ProfileResultsHook — emits structured profile results for UI
# ---------------------------------------------------------------------------

_ROW_COL_PATTERN = re.compile(r"(\d+)\s*rows?.*?(\d+)\s*col", re.IGNORECASE)
_MISSING_PCT_PATTERN = re.compile(r"missing.*?(\d+(?:\.\d+)?)\s*%", re.IGNORECASE)
_GRADE_PATTERN = re.compile(r"grade[\s:=]*([ABCD])", re.IGNORECASE)


class ProfileResultsHook(ToolHook):
    """Emits structured profile.results event when data_profiler completes."""

    name = "profile_results"
    priority = 46

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if tool_name != "data_profiler" or is_error:
            return PostToolUseResult()

        payload = self._parse_profile(result)
        context.emit("profile.results", payload)
        return PostToolUseResult()

    @staticmethod
    def _parse_profile(text: str) -> dict:
        """Extract structured profile data from profiler output."""
        rows, cols = 0, 0
        rc_match = _ROW_COL_PATTERN.search(text)
        if rc_match:
            rows = int(rc_match.group(1))
            cols = int(rc_match.group(2))

        missing_pct = 0.0
        miss_match = _MISSING_PCT_PATTERN.search(text)
        if miss_match:
            missing_pct = float(miss_match.group(1))

        grade = "C"
        grade_match = _GRADE_PATTERN.search(text)
        if grade_match:
            grade = grade_match.group(1).upper()

        # Extract issue mentions
        issues: list[dict] = []
        issue_keywords = {
            "high_missing": ["high missing", "many null", "> 50% missing"],
            "high_cardinality": ["high cardinality", "unique values"],
            "outliers": ["outlier", "extreme values"],
        }
        for issue_type, keywords in issue_keywords.items():
            if any(kw in text.lower() for kw in keywords):
                issues.append({"issue": issue_type, "detail": issue_type.replace("_", " ")})

        return {
            "summary": text[:500] if len(text) > 500 else text,
            "grade": grade,
            "rows": rows,
            "columns": cols,
            "missingPct": missing_pct,
            "issues": issues,
        }


def _score_to_grade(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# 6. ModelSanityCheckHook — auto sanity checks after model training
# ---------------------------------------------------------------------------

_PREDICTION_DIST_PATTERN = re.compile(
    r"predict(?:ion)?[\s_]*(?:distribution|unique|classes)[\s:=]*(\S+)",
    re.IGNORECASE,
)
_SINGLE_CLASS_PATTERN = re.compile(
    r"(?:all\s+predictions?\s+(?:are|=)\s+\d|only\s+(?:one|1)\s+class\s+predicted)",
    re.IGNORECASE,
)


class ModelSanityCheckHook(ToolHook):
    """Runs 3 automated sanity checks after model training.

    1. **Prediction distribution**: Checks if model predicts multiple classes
       (not collapsed to a single output).
    2. **Permutation test indicator**: Checks if the result mentions
       label shuffling / permutation importance.
    3. **Single-feature baseline**: Checks if single-feature performance
       is suspiciously close to full-model performance (potential leakage).
    """

    name = "model_sanity_check"
    priority = 40

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if tool_name != "train_model" or is_error:
            return PostToolUseResult()

        checks = []

        # Check 1: Prediction distribution — warn if all predictions are same class
        pred_ok = not bool(_SINGLE_CLASS_PATTERN.search(result))
        checks.append(
            {
                "name": "prediction_distribution",
                "passed": pred_ok,
                "detail": (
                    "Predictions span multiple classes"
                    if pred_ok
                    else "Model may predict only one class (collapsed)"
                ),
            }
        )

        # Check 2: Permutation test presence
        perm_keywords = ["permutation_importance", "permutation test", "label_shuffle"]
        perm_ok = any(kw in result.lower() for kw in perm_keywords)
        checks.append(
            {
                "name": "permutation_test",
                "passed": perm_ok,
                "detail": (
                    "Permutation importance computed"
                    if perm_ok
                    else "Consider running permutation importance to validate model"
                ),
            }
        )

        # Check 3: Single-feature baseline — flag if mentioned with suspicious gap
        single_ok = not self._detect_single_feature_concern(result)
        checks.append(
            {
                "name": "single_feature_baseline",
                "passed": single_ok,
                "detail": (
                    "No single-feature dominance detected"
                    if single_ok
                    else "Single feature achieves near-full performance — check for leakage"
                ),
            }
        )

        failed = [c for c in checks if not c["passed"]]
        if failed:
            context.emit(
                "harness.warning",
                {
                    "type": "sanity_check",
                    "severity": "medium",
                    "message": f"{len(failed)} sanity check(s) flagged",
                    "details": [c["detail"] for c in failed],
                },
            )

        context.emit(
            "quality.update",
            {
                "stage": "modeling",
                "checks": checks,
            },
        )

        check_lines = [
            f"{'PASS' if c['passed'] else 'WARN'} {c['name']}: {c['detail']}" for c in checks
        ]
        suffix = "\n\n---\n**Sanity Checks**:\n" + "\n".join(f"- {line}" for line in check_lines)
        return PostToolUseResult(modified_result=result + suffix)

    @staticmethod
    def _detect_single_feature_concern(text: str) -> bool:
        """Return True if text indicates a single feature nearly matches full model."""
        lower = text.lower()
        if "single feature" not in lower and "single_feature" not in lower:
            return False
        # Look for a score >= 0.9 near the single feature mention
        match = re.search(
            r"single[_\s]feature.*?([0-9]+\.[0-9]+)",
            lower,
        )
        if match:
            try:
                score = float(match.group(1))
                return score >= 0.90
            except ValueError:
                pass
        return False


class ExperimentDesignHook(ToolHook):
    """Check SRM and power adequacy for experiment workflows."""

    name = "experiment_design"
    priority = 42

    def __init__(self, analyzer: ABTestAnalyzer | None = None) -> None:
        self._analyzer = analyzer or ABTestAnalyzer()

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if tool_name != "ab_test" or is_error:
            return PostToolUseResult()

        checks: dict[str, dict[str, object]] = {}
        notes: list[str] = []

        control_n = arguments.get("control_n")
        treatment_n = arguments.get("treatment_n")
        if isinstance(control_n, int) and isinstance(treatment_n, int):
            srm = self._analyzer.srm_check(
                control_n=control_n,
                treatment_n=treatment_n,
                expected_ratio=(
                    float(arguments.get("expected_control_ratio", 0.5)),
                    float(arguments.get("expected_treatment_ratio", 0.5)),
                ),
            )
            checks["srm"] = srm.to_dict()
            if not srm.is_valid:
                notes.append(
                    f"SRM failed (p={srm.p_value:.4f}). "
                    "Check traffic allocation before interpreting lift."
                )

        effect_size = arguments.get("effect_size")
        observed_total_n = arguments.get("observed_total_n")
        if isinstance(effect_size, (int, float)) and isinstance(observed_total_n, int):
            required = self._analyzer.power_analysis(
                effect_size=float(effect_size),
                alpha=float(arguments.get("alpha", 0.05)),
                power=float(arguments.get("power", 0.8)),
                test_type=str(arguments.get("test_type", "proportion")),
            )
            checks["power"] = {
                "required_total_n": required.total_n,
                "observed_total_n": observed_total_n,
                "is_sufficient": observed_total_n >= required.total_n,
            }
            if observed_total_n < required.total_n:
                notes.append(
                    "Experiment is underpowered "
                    f"({observed_total_n} < required {required.total_n} total samples)."
                )

        if not notes:
            return PostToolUseResult()

        context.emit("experiment.design_warning", {"checks": checks, "notes": notes})
        suffix = (
            "\n\n---\n**Experiment Design Checks**:\n"
            + "\n".join(f"- {note}" for note in notes)
        )
        return PostToolUseResult(modified_result=result + suffix)


class DriftDetectionHook(ToolHook):
    """Check for drift after evaluation or deployment steps."""

    name = "drift_detection"
    priority = 60

    def __init__(self, analyzer: DriftAnalyzer | None = None) -> None:
        self._analyzer = analyzer or DriftAnalyzer()

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if tool_name not in {"evaluate_model", "deploy_model"} or is_error:
            return PostToolUseResult()

        reference = (
            arguments.get("reference_data")
            or arguments.get("train_data_path")
            or arguments.get("reference_path")
        )
        current = (
            arguments.get("current_data")
            or arguments.get("test_data_path")
            or arguments.get("current_path")
        )
        if reference is None or current is None:
            return PostToolUseResult()

        report = self._analyzer.analyze(reference, current, features=arguments.get("features"))
        if report.overall_status == "ok":
            return PostToolUseResult()

        context.emit("drift.detected", report.to_dict())
        summary = {
            "overall_status": report.overall_status,
            "top_drifting_features": report.top_drifting_features,
            "recommended_action": report.recommended_action,
        }
        suffix = (
            "\n\n---\n**Drift monitoring**:\n"
            f"- status: {summary['overall_status']}\n"
            f"- top features: {', '.join(summary['top_drifting_features'])}\n"
            f"- action: {summary['recommended_action']}"
        )
        return PostToolUseResult(modified_result=result + suffix)
