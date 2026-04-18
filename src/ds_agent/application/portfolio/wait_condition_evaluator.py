"""Evaluate wait conditions to determine resumability.

The evaluator only *judges* whether a condition is satisfied.
It does NOT perform state transitions — that is the LLM's decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ds_agent.domain.portfolio.wait_condition import WaitCondition, WaitConditionKind


class Clock(Protocol):
    def now(self) -> datetime: ...


@dataclass(frozen=True)
class EvaluationResult:
    """Result of evaluating one wait condition."""

    condition_id: str
    kind: WaitConditionKind
    satisfied: bool
    reason: str


class WaitConditionEvaluator:
    """Evaluate wait conditions without performing transitions.

    For each kind of condition, the evaluator checks whether the
    condition is met and returns a result.  The LLM receives these
    results via prompt context and decides whether to call
    ``resume_task``.
    """

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def evaluate(self, condition: WaitCondition) -> EvaluationResult:
        """Evaluate one wait condition."""
        if condition.kind == WaitConditionKind.TIMER:
            return self._evaluate_timer(condition)
        if condition.kind == WaitConditionKind.APPROVAL:
            return self._evaluate_approval(condition)
        if condition.kind == WaitConditionKind.DATA_FRESHNESS:
            return self._evaluate_data_freshness(condition)
        if condition.kind == WaitConditionKind.EXTERNAL_RESOURCE:
            return self._evaluate_external(condition)
        return EvaluationResult(
            condition_id=condition.condition_id,
            kind=condition.kind,
            satisfied=False,
            reason=f"unknown condition kind: {condition.kind}",
        )

    def evaluate_all(
        self,
        conditions: list[WaitCondition],
    ) -> list[EvaluationResult]:
        """Evaluate a batch of conditions."""
        return [self.evaluate(c) for c in conditions]

    def _evaluate_timer(self, condition: WaitCondition) -> EvaluationResult:
        resume_at_str = condition.spec.get("resume_at")
        if not resume_at_str:
            return EvaluationResult(
                condition_id=condition.condition_id,
                kind=condition.kind,
                satisfied=False,
                reason="timer spec missing resume_at",
            )
        resume_at = datetime.fromisoformat(resume_at_str)
        now = self._clock.now()
        if now >= resume_at:
            return EvaluationResult(
                condition_id=condition.condition_id,
                kind=condition.kind,
                satisfied=True,
                reason=f"timer expired at {resume_at.isoformat()}",
            )
        remaining = (resume_at - now).total_seconds()
        return EvaluationResult(
            condition_id=condition.condition_id,
            kind=condition.kind,
            satisfied=False,
            reason=f"timer pending, {remaining:.0f}s remaining",
        )

    def _evaluate_approval(self, condition: WaitCondition) -> EvaluationResult:
        # Approval evaluation requires the approval_store, which is
        # injected at runtime.  For now, return pending.
        return EvaluationResult(
            condition_id=condition.condition_id,
            kind=condition.kind,
            satisfied=False,
            reason="approval check requires runtime context",
        )

    def _evaluate_data_freshness(self, condition: WaitCondition) -> EvaluationResult:
        # Data freshness evaluation requires warehouse adapter.
        return EvaluationResult(
            condition_id=condition.condition_id,
            kind=condition.kind,
            satisfied=False,
            reason="data freshness check requires warehouse adapter",
        )

    def _evaluate_external(self, condition: WaitCondition) -> EvaluationResult:
        # External resource evaluation requires external adapter.
        return EvaluationResult(
            condition_id=condition.condition_id,
            kind=condition.kind,
            satisfied=False,
            reason="external resource check requires adapter",
        )
