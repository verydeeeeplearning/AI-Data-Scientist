"""Application service for policy-based approval decisions."""

from __future__ import annotations

import json
import time
from fnmatch import fnmatch
from pathlib import Path

from ds_agent.domain.entities.approval_policy import (
    ApprovalPolicy,
    DataSensitivity,
    PolicyDecisionType,
    PolicyRule,
    StandingApproval,
)


class PolicyDecision:
    """Decision returned by the policy evaluator."""

    def __init__(
        self,
        *,
        decision: PolicyDecisionType,
        reason: str,
        matched_rule: PolicyRule | None = None,
        standing_approval: StandingApproval | None = None,
    ) -> None:
        self.decision = decision
        self.reason = reason
        self.matched_rule = matched_rule
        self.standing_approval = standing_approval


class PolicyEvaluator:
    """Evaluate tool actions against policy rules and standing approvals."""

    def __init__(
        self,
        policy: ApprovalPolicy | None = None,
        *,
        standing_threshold: int = 3,
        storage_path: str = "data/policy/standing_approvals.json",
    ) -> None:
        self._policy = policy or ApprovalPolicy(rules=_default_rules())
        self._standing_threshold = standing_threshold
        self._storage_path = Path(storage_path)
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_standing_approvals()

    @property
    def policy(self) -> ApprovalPolicy:
        return self._policy

    def evaluate(
        self,
        action: str,
        sensitivity: str | DataSensitivity = DataSensitivity.INTERNAL,
        env: str = "dev",
        confidence: float = 1.0,
    ) -> PolicyDecision:
        sensitivity_value = (
            sensitivity
            if isinstance(sensitivity, DataSensitivity)
            else DataSensitivity(sensitivity)
        )
        standing = self._policy.standing_approvals.get(
            _standing_key(action, sensitivity_value, env)
        )
        if standing is not None and standing.promoted:
            return PolicyDecision(
                decision=PolicyDecisionType.AUTO,
                reason="standing approval promoted after repeated approvals",
                standing_approval=standing,
            )

        rules = sorted(self._policy.rules, key=lambda rule: rule.specificity(), reverse=True)
        for rule in rules:
            if not fnmatch(action, rule.action_pattern):
                continue
            if rule.data_sensitivity is not None and rule.data_sensitivity != sensitivity_value:
                continue
            if rule.environment is not None and rule.environment != env:
                continue
            if rule.confidence_threshold is not None and confidence >= rule.confidence_threshold:
                continue
            return PolicyDecision(
                decision=rule.decision,
                reason=self._build_reason(
                    rule, action=action, sensitivity=sensitivity_value, env=env
                ),
                matched_rule=rule,
            )

        return PolicyDecision(
            decision=PolicyDecisionType.AUTO,
            reason="no restrictive policy rule matched",
        )

    def record_approval(
        self,
        action: str,
        approved_by: str,
        *,
        sensitivity: str | DataSensitivity = DataSensitivity.INTERNAL,
        env: str = "dev",
    ) -> StandingApproval:
        sensitivity_value = (
            sensitivity
            if isinstance(sensitivity, DataSensitivity)
            else DataSensitivity(sensitivity)
        )
        key = _standing_key(action, sensitivity_value, env)
        standing = self._policy.standing_approvals.get(key)
        if standing is None:
            standing = StandingApproval(
                action=action,
                data_sensitivity=sensitivity_value,
                environment=env,
            )
            self._policy.standing_approvals[key] = standing

        standing.count += 1
        standing.updated_at = time.time()
        if approved_by not in standing.approved_by:
            standing.approved_by.append(approved_by)
        if standing.count >= self._standing_threshold:
            standing.promoted = True
        self._save_standing_approvals()
        return standing

    def promote_to_standing(
        self,
        action: str,
        *,
        sensitivity: str | DataSensitivity = DataSensitivity.INTERNAL,
        env: str = "dev",
    ) -> StandingApproval:
        standing = self.record_approval(
            action,
            approved_by="policy",
            sensitivity=sensitivity,
            env=env,
        )
        standing.count = max(standing.count, self._standing_threshold)
        standing.promoted = True
        self._save_standing_approvals()
        return standing

    def _build_reason(
        self,
        rule: PolicyRule,
        *,
        action: str,
        sensitivity: DataSensitivity,
        env: str,
    ) -> str:
        parts = [f"policy matched for action '{action}'"]
        parts.append(f"sensitivity={sensitivity.value}")
        parts.append(f"env={env}")
        if rule.confidence_threshold is not None:
            parts.append(f"confidence<{rule.confidence_threshold}")
        return ", ".join(parts)

    def _load_standing_approvals(self) -> None:
        if not self._storage_path.exists():
            return
        payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            return
        for item in payload:
            if not isinstance(item, dict):
                continue
            standing = StandingApproval(
                action=str(item.get("action", "")),
                data_sensitivity=DataSensitivity(str(item.get("data_sensitivity", "internal"))),
                environment=str(item.get("environment", "dev")),
                count=int(item.get("count", 0)),
                approved_by=[
                    str(actor) for actor in item.get("approved_by", []) if isinstance(actor, str)
                ],
                promoted=bool(item.get("promoted", False)),
                created_at=float(item.get("created_at", time.time())),
                updated_at=float(item.get("updated_at", time.time())),
            )
            self._policy.standing_approvals[standing.key] = standing

    def _save_standing_approvals(self) -> None:
        payload = [
            {
                "action": approval.action,
                "data_sensitivity": approval.data_sensitivity.value,
                "environment": approval.environment,
                "count": approval.count,
                "approved_by": approval.approved_by,
                "promoted": approval.promoted,
                "created_at": approval.created_at,
                "updated_at": approval.updated_at,
            }
            for approval in self._policy.standing_approvals.values()
        ]
        self._storage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _default_rules() -> list[PolicyRule]:
    return [
        PolicyRule(action_pattern="delete*", decision=PolicyDecisionType.DOUBLE_CHECK),
        PolicyRule(
            action_pattern="file_read",
            data_sensitivity=DataSensitivity.PII,
            decision=PolicyDecisionType.APPROVAL,
        ),
        PolicyRule(
            action_pattern="file_read",
            data_sensitivity=DataSensitivity.PUBLIC,
            decision=PolicyDecisionType.AUTO,
        ),
        PolicyRule(
            action_pattern="sql_query",
            data_sensitivity=DataSensitivity.PII,
            environment="prod",
            decision=PolicyDecisionType.APPROVAL,
        ),
        PolicyRule(
            action_pattern="sql_query",
            data_sensitivity=DataSensitivity.INTERNAL,
            environment="dev",
            decision=PolicyDecisionType.AUTO,
        ),
        PolicyRule(action_pattern="execute_code", decision=PolicyDecisionType.AUTO),
        PolicyRule(action_pattern="train_model", decision=PolicyDecisionType.AUTO),
        PolicyRule(
            action_pattern="deploy_model",
            environment="prod",
            confidence_threshold=0.7,
            decision=PolicyDecisionType.APPROVAL,
        ),
        PolicyRule(
            action_pattern="deploy_model",
            environment="prod",
            decision=PolicyDecisionType.AUTO,
        ),
        PolicyRule(action_pattern="web_search", decision=PolicyDecisionType.AUTO),
        PolicyRule(
            action_pattern="file_write",
            environment="prod",
            decision=PolicyDecisionType.APPROVAL,
        ),
        PolicyRule(action_pattern="*", decision=PolicyDecisionType.AUTO),
    ]


def _standing_key(action: str, sensitivity: DataSensitivity, env: str) -> str:
    return f"{action}|{sensitivity.value}|{env}"


_policy_evaluator: PolicyEvaluator | None = None


def get_policy_evaluator() -> PolicyEvaluator:
    """Return the process-global policy evaluator."""
    global _policy_evaluator
    if _policy_evaluator is None:
        _policy_evaluator = PolicyEvaluator()
    return _policy_evaluator


def set_policy_evaluator(evaluator: PolicyEvaluator) -> None:
    """Replace the process-global policy evaluator."""
    global _policy_evaluator
    _policy_evaluator = evaluator
