"""Policy adapter for workflow integration outbound actions."""

from __future__ import annotations

import threading
import time

from ds_agent.application.ports.work_object_support import (
    PolicyActionSpec,
    PolicyCheckResult,
    WorkflowIntegrationPolicyPort,
)
from ds_agent.application.services.policy_evaluator import PolicyEvaluator, get_policy_evaluator


class EvaluatorWorkflowIntegrationPolicy(WorkflowIntegrationPolicyPort):
    """Workflow-integration policy adapter backed by PolicyEvaluator."""

    def __init__(self, evaluator: PolicyEvaluator | None = None) -> None:
        self._evaluator = evaluator or get_policy_evaluator()
        self._lock = threading.Lock()
        self._counter = 0

    def check(self, spec: PolicyActionSpec) -> PolicyCheckResult:
        decision = self._evaluator.evaluate(
            spec.action,
            sensitivity=spec.data_sensitivity,
            env=spec.environment,
            confidence=spec.confidence,
        )
        return PolicyCheckResult(
            decision=decision.decision,
            reason=decision.reason,
            decision_id=self._new_decision_id(),
        )

    def _new_decision_id(self) -> str:
        with self._lock:
            self._counter += 1
            return f"PD-{time.time_ns() + self._counter}"
