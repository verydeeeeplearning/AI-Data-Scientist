"""BacktrackTriggerHook — automatic workflow backtracking on poor performance.

Priority 37: runs after OverfittingDetector (35) and before ModelSanityCheck (40).

When evaluation results show poor performance, this hook:
1. Extracts metrics from the evaluation result
2. Determines the appropriate stage to backtrack to
3. Emits a backtrack.trigger event with context
4. Appends a backtrack instruction to the result for the LLM
5. Tracks backtrack history and enforces depth limits
"""

from __future__ import annotations

import json
import re

from ds_agent.agent.ds_workflow_hooks import DS_WORKFLOW_STAGES, WorkflowTrackerHook
from ds_agent.agent.hooks import HookContext, PostToolUseResult, ToolHook
from ds_agent.domain.value_objects.backtrack import PreviousAttempt

# Metric names we monitor
_METRIC_NAMES = frozenset({
    "accuracy", "test_accuracy", "val_accuracy",
    "f1", "f1_score", "test_f1",
    "roc_auc", "auc", "test_auc",
    "r2", "test_r2",
    "precision", "recall",
})

# Threshold below which we consider performance "poor"
_DEFAULT_POOR_THRESHOLD = 0.60

# Metric patterns for extraction
_METRIC_PATTERN = re.compile(
    r"(?:test|val|validation)[\s_]*"
    r"(accuracy|f1|f1_score|auc|roc_auc|r2|precision|recall|score)"
    r"[\s:=]*([0-9]*\.?[0-9]+)",
    re.IGNORECASE,
)


def _extract_test_metrics(result: str) -> dict[str, float]:
    """Extract test/validation metrics from evaluation result."""
    metrics: dict[str, float] = {}

    # Try JSON blocks first
    for json_str in re.findall(r"\{[^{}]+\}", result):
        try:
            obj = json.loads(json_str)
            if isinstance(obj, dict):
                for k, v in obj.items():
                    key = k.lower().replace(" ", "_")
                    if isinstance(v, (int, float)) and key in _METRIC_NAMES:
                        metrics[key] = float(v)
        except (json.JSONDecodeError, ValueError):
            pass

    if not metrics:
        # Line-based extraction
        for m in _METRIC_PATTERN.finditer(result):
            key = f"test_{m.group(1).lower()}"
            try:
                val = float(m.group(2))
                if 1.0 < val <= 100.0:
                    val /= 100.0
                metrics[key] = val
            except ValueError:
                pass

    return metrics


def _determine_backtrack_target(
    metrics: dict[str, float],
    result_text: str,
) -> str | None:
    """Decide which stage to backtrack to based on metrics and context.

    Returns the target stage name, or None if no backtrack needed.
    """
    # Check if any test metric is below threshold
    test_metrics = {k: v for k, v in metrics.items() if v < _DEFAULT_POOR_THRESHOLD}
    if not test_metrics:
        return None

    # Heuristic: check for overfitting signal
    overfitting_signal = "overfitting" in result_text.lower() or any(
        "train" in result_text.lower() and "gap" in result_text.lower()
        for _ in [None]
    )

    if overfitting_signal:
        return "feature_eng"  # Reduce features / add regularization

    # Default: go back to feature engineering
    return "feature_eng"


def rewind_tracker_to_stage(
    tracker: WorkflowTrackerHook, target_stage: str
) -> None:
    """Rewind WorkflowTracker: set target and all subsequent stages to 'pending'.

    Stages before target_stage are preserved.
    """
    stage_list = DS_WORKFLOW_STAGES
    target_idx = stage_list.index(target_stage) if target_stage in stage_list else -1
    if target_idx < 0:
        return

    for i, stage in enumerate(stage_list):
        if i >= target_idx:
            tracker._stages[stage] = "pending"


class BacktrackTriggerHook(ToolHook):
    """Triggers workflow backtracking when evaluation shows poor performance.

    Monitors evaluate_model results, detects poor metrics, and instructs
    the LLM to backtrack to an earlier stage for a different approach.
    """

    name = "backtrack_trigger"
    priority = 37

    def __init__(self, max_backtracks: int = 2) -> None:
        self._max_backtracks = max_backtracks
        self._backtrack_count = 0
        self._previous_attempts: list[PreviousAttempt] = []

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if tool_name != "evaluate_model" or is_error:
            return PostToolUseResult()

        # Extract test metrics
        metrics = _extract_test_metrics(result)
        if not metrics:
            return PostToolUseResult()

        # Determine if backtracking is needed
        target_stage = _determine_backtrack_target(metrics, result)
        if target_stage is None:
            return PostToolUseResult()

        # Check depth limit
        if self._backtrack_count >= self._max_backtracks:
            context.emit(
                "backtrack.stop",
                {
                    "reason": "max_depth_reached",
                    "backtrack_count": self._backtrack_count,
                    "previous_attempts": [
                        {"stage": a.stage, "metrics": a.metrics, "reason": a.reason}
                        for a in self._previous_attempts
                    ],
                },
            )
            return PostToolUseResult(
                modified_result=(
                    f"{result}\n\n"
                    f"[BACKTRACK LIMIT] {self._max_backtracks} backtracks exhausted. "
                    f"Accept current results or use ask_user for guidance."
                ),
            )

        # Record this attempt
        best_metric_name = min(metrics, key=metrics.get)  # type: ignore[arg-type]
        reason = f"{best_metric_name}={metrics[best_metric_name]:.3f} below threshold"
        attempt = PreviousAttempt(
            stage="evaluation",
            metrics=dict(metrics),
            reason=reason,
        )
        self._previous_attempts.append(attempt)
        self._backtrack_count += 1

        # Emit backtrack event
        context.emit(
            "backtrack.trigger",
            {
                "target_stage": target_stage,
                "reason": reason,
                "backtrack_number": self._backtrack_count,
                "previous_attempts": [
                    {"stage": a.stage, "metrics": a.metrics, "reason": a.reason}
                    for a in self._previous_attempts
                ],
            },
        )

        # Build context string for LLM
        history_lines = []
        for i, a in enumerate(self._previous_attempts, 1):
            m_str = ", ".join(f"{k}={v:.3f}" for k, v in a.metrics.items())
            history_lines.append(f"  Attempt {i}: {m_str} ({a.reason})")
        history_text = "\n".join(history_lines)

        return PostToolUseResult(
            modified_result=(
                f"{result}\n\n"
                f"[BACKTRACK] Performance below threshold. "
                f"Rewinding to '{target_stage}' stage.\n"
                f"Previous attempts:\n{history_text}\n"
                f"Try a different approach: different features, "
                f"different model, or different preprocessing."
            ),
        )
