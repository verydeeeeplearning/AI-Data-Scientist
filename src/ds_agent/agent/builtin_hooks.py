"""Built-in hooks — permission enforcement, audit, budget guard, experiment tracking."""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from ds_agent.agent.hooks import (
    FinalResponseResult,
    HookAction,
    HookContext,
    PostToolUseResult,
    PreToolUseResult,
    ToolHook,
)
from ds_agent.agent.permissions import PermissionPolicy
from ds_agent.application.services.analysis_type_router import AnalysisTypeRouter
from ds_agent.application.services.review_artifact_capture import (
    extract_review_artifact_captures,
    review_artifact_capture_instructions,
)
from ds_agent.domain.entities.review_verdict import ReviewVerdict
from ds_agent.domain.value_objects.authority_mode import AuthorityMode

if TYPE_CHECKING:
    from ds_agent.agent.prompt_builder import MissionPackLoaderLike
    from ds_agent.domain.interfaces.certification import CertificationStore
    from ds_agent.domain.interfaces.task_contract import TaskContractStore
    from ds_agent.infrastructure.decision_os_container import DecisionOsContainer
    from ds_agent.runtime.policy_store import JsonPolicyStore

logger = structlog.get_logger()


class PermissionHook(ToolHook):
    """Enforces PermissionPolicy — denies tools based on mode + safety level."""

    name = "permission"
    priority = 10

    def __init__(
        self,
        policy: PermissionPolicy | None = None,
        *,
        task_contract_store: TaskContractStore | None = None,
        mission_loader: MissionPackLoaderLike | None = None,
        certification_store: CertificationStore | None = None,
        policy_store: JsonPolicyStore | None = None,
    ) -> None:
        self._policy = policy or PermissionPolicy()
        self._task_contract_store = task_contract_store
        self._mission_loader = mission_loader
        self._certification_store = certification_store
        self._policy_store = policy_store

    @property
    def policy(self) -> PermissionPolicy:
        return self._policy

    async def pre_tool_use(
        self, tool_name: str, arguments: dict, context: HookContext
    ) -> PreToolUseResult:
        overlay_authority = _overlay_authority(context.authority_mode)
        authority = None
        audience = None
        mission = None
        mission_pack = None
        latest_review_verdict = None
        if self._task_contract_store is not None and context.session_id:
            bundle = self._task_contract_store.get_active_bundle(context.session_id)
            if bundle is not None:
                authority = bundle.contract.authority
                audience = bundle.contract.audience
                mission = bundle.contract.mission
                latest_review_verdict = _latest_review_verdict(bundle.review_verdicts)
                if mission and self._mission_loader is not None:
                    mission_pack = self._mission_loader.try_load(mission)
        if overlay_authority is not None:
            authority = overlay_authority

        policy = PermissionPolicy(
            mode=self._policy.mode,
            agent_mode=context.mode,
            denied_tools=self._policy.denied_tools,
            authority_mode=authority,
            audience_persona=audience,
            mission=mission,
            mission_pack=mission_pack,
            latest_review_verdict=latest_review_verdict,
            certification_store=self._certification_store,
            action_matrix=(
                self._policy_store.build_action_matrix() if self._policy_store is not None else None
            ),
        )
        allowed, reason = policy.check(tool_name, arguments)
        if not allowed:
            return PreToolUseResult(action=HookAction.DENY, deny_reason=reason)
        return PreToolUseResult()


class OrgPolicyHook(ToolHook):
    """Enforces organization export/network side-effect policies."""

    name = "org_policy"
    priority = 15

    def __init__(self, org_policy_supplier: object | None = None) -> None:
        self._org_policy_supplier = org_policy_supplier

    async def pre_tool_use(
        self, tool_name: str, arguments: dict, context: HookContext
    ) -> PreToolUseResult:
        if not callable(self._org_policy_supplier):
            return PreToolUseResult()

        organization = self._org_policy_supplier()
        if organization is None:
            return PreToolUseResult()

        from ds_agent.application.services.organization_policy import OrgPolicyGate

        reason = OrgPolicyGate().check_tool_allowed(tool_name, organization)
        if reason is None:
            return PreToolUseResult()
        return PreToolUseResult(action=HookAction.DENY, deny_reason=reason)


class AuditLogHook(ToolHook):
    """Logs every tool call to a JSONL audit file."""

    name = "audit_log"
    priority = 0  # Always runs first

    def __init__(self, log_path: Path | None = None) -> None:
        self._log_path = log_path or Path("data/audit_log.jsonl")

    async def pre_tool_use(
        self, tool_name: str, arguments: dict, context: HookContext
    ) -> PreToolUseResult:
        self._write(
            "pre_tool_use",
            tool_name,
            {
                "arguments_keys": list(arguments.keys()),
                "mode": context.mode,
                "authority_mode": context.authority_mode,
                "session_id": context.session_id,
            },
        )
        return PreToolUseResult()

    async def post_tool_use(
        self, tool_name: str, arguments: dict, result: str, is_error: bool, context: HookContext
    ) -> PostToolUseResult:
        self._write(
            "post_tool_use",
            tool_name,
            {
                "is_error": is_error,
                "result_length": len(result),
                "authority_mode": context.authority_mode,
                "session_id": context.session_id,
            },
        )
        return PostToolUseResult()

    def _write(self, event: str, tool_name: str, data: dict) -> None:
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "event": event,
                "tool": tool_name,
                "timestamp": time.time(),
                **data,
            }
            with self._log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError as e:
            logger.warning("audit_log_write_failed", tool=tool_name, error=str(e))


class BudgetGuardHook(ToolHook):
    """Denies expensive tools when budget is critical (>= 95%)."""

    name = "budget_guard"
    priority = 20

    EXPENSIVE_TOOLS = frozenset(
        {
            "train_model",
            "execute_code",
            "run_eda",
            "feature_engineer",
            "generate_deployment",
        }
    )

    def __init__(self, max_cost_usd: float = 10.0, critical_pct: float = 95.0) -> None:
        self._max_cost = max_cost_usd
        self._critical_pct = critical_pct

    async def pre_tool_use(
        self, tool_name: str, arguments: dict, context: HookContext
    ) -> PreToolUseResult:
        if tool_name not in self.EXPENSIVE_TOOLS:
            return PreToolUseResult()

        if self._max_cost <= 0:
            return PreToolUseResult()

        pct = (context.total_cost_usd / self._max_cost) * 100
        if pct >= self._critical_pct:
            return PreToolUseResult(
                action=HookAction.DENY,
                deny_reason=(
                    f"Budget critical ({pct:.0f}%): "
                    f"${context.total_cost_usd:.2f}/${self._max_cost:.2f}"
                ),
            )
        return PreToolUseResult()


class SessionInitHook(ToolHook):
    """Force-injects safety rules and DS methodology at session start.

    Ensures critical rules are always present in context, regardless of
    whether the agent reads documentation files. This follows the harness
    engineering principle: "enforce via code (hooks), not just docs."
    """

    name = "session_init"
    priority = 0  # Runs first

    async def on_session_init(self, context: HookContext) -> str:
        return (
            "## Session Rules (auto-injected)\n"
            "\n"
            "### Safety\n"
            "- Execute code only inside ProcessSandbox\n"
            "- Never transmit user data to external servers\n"
            "- Validate file paths — no directory traversal outside workspace\n"
            "\n"
            "### DS Methodology\n"
            "- Always establish a baseline (DummyClassifier/DummyRegressor) before complex models\n"
            "- Split data BEFORE fitting transformers — fit on train only, transform both\n"
            "- Use cross-validation (default 5-fold) — report mean +/- std\n"
            "- Never draw conclusions without statistical significance (p < 0.05)\n"
            "- Evaluate on held-out test set only — never on training data\n"
            "- Check for data leakage: no future info, no target proxies, no test in fit\n"
            "\n"
            "### Quality\n"
            "- Profile data quality before any analysis\n"
            "- Compare all models against baseline — improvement must be measurable\n"
            "- Report limitations honestly — document what could go wrong\n"
            "- Save reproducible code and log all experiment metrics"
        )


class ProblemTypeRouterHook(ToolHook):
    """Classify the user's analysis type at session start."""

    name = "problem_type_router"
    priority = 3

    def __init__(self, router: AnalysisTypeRouter | None = None) -> None:
        self._router = router or AnalysisTypeRouter()

    async def on_session_init(self, context: HookContext) -> str | None:
        if not context.user_message:
            return None

        analysis_type = self._router.route(context.user_message)
        context.emit(
            "analysis_type.detected",
            {
                "type": analysis_type.type,
                "skills": analysis_type.required_skills,
                "guards": analysis_type.required_guards,
                "workflow": analysis_type.workflow_stages,
            },
        )
        lines = [
            "## Analysis Routing",
            f"- Detected type: {analysis_type.type}",
            f"- Required skills: {', '.join(analysis_type.required_skills) or 'none'}",
            f"- Required guards: {', '.join(analysis_type.required_guards) or 'none'}",
            f"- Workflow: {' -> '.join(analysis_type.workflow_stages)}",
        ]
        return "\n".join(lines)


class ExecPlanSaveHook(ToolHook):
    """Saves the agent's first response as an execution plan to disk.

    When the first tool call completes, extracts any plan/steps from the
    result and persists it to ``data/exec-plans/{session_id}.md``.
    """

    name = "exec_plan_save"
    priority = 55

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or Path("data/exec-plans")
        self._saved = False

    async def post_tool_use(
        self, tool_name: str, arguments: dict, result: str, is_error: bool, context: HookContext
    ) -> PostToolUseResult:
        if self._saved or is_error or not context.session_id:
            return PostToolUseResult()
        if context.iteration > 3:
            # Only capture early planning steps
            self._saved = True
            return PostToolUseResult()

        # Look for plan-like content in tool results
        plan_text = self._extract_plan(result)
        if plan_text:
            self._save_plan(context.session_id, plan_text)
            self._saved = True

        return PostToolUseResult()

    @staticmethod
    def _extract_plan(text: str) -> str | None:
        """Heuristic: return text if it contains plan-like structure."""
        indicators = ["step", "plan", "1.", "- [", "phase", "approach"]
        lower = text.lower()
        if sum(1 for ind in indicators if ind in lower) >= 2:
            return text
        return None

    def _save_plan(self, session_id: str, plan: str) -> None:
        try:
            self._base_dir.mkdir(parents=True, exist_ok=True)
            path = self._base_dir / f"{session_id}.md"
            path.write_text(
                f"# Execution Plan — Session {session_id}\n\n{plan}\n",
                encoding="utf-8",
            )
            logger.info("exec_plan_saved", session_id=session_id, path=str(path))
        except OSError:
            logger.debug("exec_plan_save_failed", session_id=session_id)


class ProcessMetricsHook(ToolHook):
    """Collects process-level metrics: tool calls, retries, timing.

    Tracks how the agent works (tool usage patterns, error recovery)
    rather than just the output quality.

    Priority 1 ensures this runs before any deny hooks, so ALL tool
    attempts are counted — including denied ones.
    """

    name = "process_metrics"
    priority = 1

    def __init__(self) -> None:
        self._tool_call_count = 0
        self._retry_count = 0
        self._error_count = 0
        self._start_time: float | None = None
        self._last_tool: str | None = None
        self._last_was_error = False
        self._tool_counts: dict[str, int] = {}

    @property
    def metrics(self) -> dict:
        elapsed = (time.time() - self._start_time) if self._start_time else 0.0
        return {
            "tool_call_count": self._tool_call_count,
            "retry_count": self._retry_count,
            "error_count": self._error_count,
            "wall_time_seconds": round(elapsed, 1),
            "tool_counts": dict(self._tool_counts),
        }

    async def on_session_init(self, context: HookContext) -> str | None:
        self._start_time = time.time()
        return None

    async def pre_tool_use(
        self, tool_name: str, arguments: dict, context: HookContext
    ) -> PreToolUseResult:
        self._tool_call_count += 1
        self._tool_counts[tool_name] = self._tool_counts.get(tool_name, 0) + 1

        # Detect retries: same tool called again right after an error
        if tool_name == self._last_tool and self._last_was_error:
            self._retry_count += 1

        return PreToolUseResult()

    async def post_tool_use(
        self, tool_name: str, arguments: dict, result: str, is_error: bool, context: HookContext
    ) -> PostToolUseResult:
        self._last_tool = tool_name
        self._last_was_error = is_error
        if is_error:
            self._error_count += 1
        return PostToolUseResult()

    def reset(self) -> None:
        self._tool_call_count = 0
        self._retry_count = 0
        self._error_count = 0
        self._start_time = None
        self._last_tool = None
        self._last_was_error = False
        self._tool_counts.clear()


def _overlay_authority(value: str | None) -> AuthorityMode | None:
    if value is None or not value.strip():
        return None
    resolved = AuthorityMode.coerce(value)
    if resolved in {AuthorityMode.INCIDENT, AuthorityMode.FREEZE}:
        return resolved
    return None


def _latest_review_verdict(review_verdicts: list[ReviewVerdict]) -> ReviewVerdict | None:
    if not review_verdicts:
        return None
    return max(review_verdicts, key=lambda verdict: verdict.created_at)


def _parse_experiment_metrics(result: str) -> dict[str, float]:
    """Extract numeric DS metrics from sandbox stdout.

    Tries JSON blocks first (most reliable), then falls back to
    ``key: value`` line patterns for well-known metric names.
    """
    metrics: dict[str, float] = {}

    # JSON dict scanning — handles print({"accuracy": 0.87, ...})
    for json_str in re.findall(r"\{[^{}]+\}", result):
        try:
            obj = json.loads(json_str)
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, (int, float)) and k not in ("error", "rc", "returncode"):
                        metrics[str(k).lower()] = round(float(v), 6)
        except (json.JSONDecodeError, ValueError):
            pass

    if not metrics:
        # Line-based fallback: "accuracy: 0.847" or "F1 = 84.7%"
        ds_metric_names = frozenset(
            {
                "accuracy",
                "precision",
                "recall",
                "f1",
                "f1_score",
                "roc_auc",
                "auc",
                "r2",
                "rmse",
                "mae",
                "mse",
                "logloss",
                "log_loss",
                "mape",
                "balanced_accuracy",
                "matthews_corrcoef",
                "average_precision",
                "cv_score",
                "test_score",
                "val_score",
                "train_score",
            }
        )
        pattern = re.compile(
            r"^\s*([A-Za-z][A-Za-z0-9_ ]*?)\s*[=:]\s*([\d.]+)%?\s*$",
            re.MULTILINE,
        )
        for m in pattern.finditer(result):
            key = m.group(1).strip().lower().replace(" ", "_")
            if key in ds_metric_names:
                try:
                    val = float(m.group(2))
                    if 1.0 < val <= 100.0:
                        val /= 100.0  # percentage → fraction
                    metrics[key] = round(val, 6)
                except ValueError:
                    pass

    return metrics


class ExperimentTrackerHook(ToolHook):
    """Triggers learning after successful train_model or evaluate_model.

    Emits ``experiment.log`` event with schema matching the frontend
    ``ExperimentTable`` (id, model, isBaseline, metrics, trainingTime, timestamp).
    """

    name = "experiment_tracker"
    priority = 50

    TRACKED_TOOLS = frozenset({"train_model", "evaluate_model"})

    def __init__(self) -> None:
        self._start_times: dict[str, float] = {}

    async def pre_tool_use(
        self, tool_name: str, arguments: dict, context: HookContext
    ) -> PreToolUseResult:
        if tool_name in self.TRACKED_TOOLS:
            self._start_times[tool_name] = time.monotonic()
        return PreToolUseResult()

    async def post_tool_use(
        self, tool_name: str, arguments: dict, result: str, is_error: bool, context: HookContext
    ) -> PostToolUseResult:
        if tool_name in self.TRACKED_TOOLS and not is_error:
            training_time: float | None = None
            if tool_name in self._start_times:
                training_time = round(time.monotonic() - self._start_times.pop(tool_name), 2)

            model_type = str(arguments.get("model_type", "unknown"))
            is_baseline = bool(arguments.get("is_baseline", False)) or any(
                kw in model_type.lower()
                for kw in ("dummy", "baseline", "trivial", "constant", "random")
            )
            metrics = _parse_experiment_metrics(result)

            # WIRE-06: Emit experiment.log with schema matching frontend ExperimentTable
            context.emit(
                "experiment.log",
                {
                    "id": f"exp-{uuid.uuid4().hex[:8]}",
                    "model": model_type,
                    "isBaseline": is_baseline,
                    "metrics": metrics,
                    "trainingTime": training_time,
                    "timestamp": int(time.time() * 1000),
                },
            )
            return PostToolUseResult(trigger_learning=True)
        return PostToolUseResult()


class ReviewArtifactCaptureHook(ToolHook):
    """Capture hidden shared-skill artifacts into Decision OS experiment runs."""

    name = "review_artifact_capture"
    priority = 60

    def __init__(self, workspace_dir: str | None = None) -> None:
        self._workspace_dir = workspace_dir
        self._container: DecisionOsContainer | None = None

    async def on_session_init(self, context: HookContext) -> str | None:
        return review_artifact_capture_instructions()

    async def on_final_response(
        self,
        response: str,
        context: HookContext,
    ) -> FinalResponseResult:
        parsed = extract_review_artifact_captures(response)
        cleaned_response = parsed.cleaned_response if parsed.cleaned_response != response else None

        if not parsed.captures:
            if parsed.errors:
                logger.warning(
                    "review_artifact_capture_parse_failed",
                    session_id=context.session_id,
                    run_id=context.run_id,
                    errors=parsed.errors,
                )
                context.emit(
                    "decision_os.review_artifacts.capture_failed",
                    {
                        "sessionId": context.session_id,
                        "runId": context.run_id,
                        "errors": parsed.errors,
                    },
                )
            return FinalResponseResult(modified_response=cleaned_response)

        container = self._get_container()
        if container is None:
            return FinalResponseResult(modified_response=cleaned_response)

        captured: list[dict[str, str]] = []
        capture_errors: list[str] = list(parsed.errors)
        for item in parsed.captures:
            try:
                container.record_review_artifact.execute(
                    run_id=item.run_id,
                    skill_name=item.skill_name,
                    summary=item.summary,
                    artifact=item.artifact,
                    narrative=item.narrative,
                )
                captured.append(
                    {
                        "experimentRunId": item.run_id,
                        "skillName": item.skill_name,
                    }
                )
            except Exception as exc:
                capture_errors.append(f"{item.run_id}:{item.skill_name}: {exc}")

        if captured:
            context.emit(
                "decision_os.review_artifacts.captured",
                {
                    "sessionId": context.session_id,
                    "runId": context.run_id,
                    "captured": captured,
                    "count": len(captured),
                },
            )
        if capture_errors:
            logger.warning(
                "review_artifact_capture_failed",
                session_id=context.session_id,
                run_id=context.run_id,
                errors=capture_errors,
            )
            context.emit(
                "decision_os.review_artifacts.capture_failed",
                {
                    "sessionId": context.session_id,
                    "runId": context.run_id,
                    "errors": capture_errors,
                },
            )
        return FinalResponseResult(modified_response=cleaned_response)

    def _get_container(self) -> DecisionOsContainer | None:
        if self._workspace_dir is None:
            return None
        if self._container is None:
            from ds_agent.infrastructure.decision_os_container import build_decision_os_container

            self._container = build_decision_os_container(self._workspace_dir)
        return self._container
