"""Policy verifier layer."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from time import perf_counter
from typing import Any

from ds_agent.domain.dtos.verifier_context import VerifierContext
from ds_agent.domain.entities.review_verdict import CheckResult, LayerResult
from ds_agent.domain.interfaces.verifier_ports import PolicyCheck, PolicyVerifierPort
from ds_agent.infrastructure.pii_detector import PIIDetector
from ds_agent.infrastructure.verifiers.common import (
    aggregate_layer,
    artifact,
    elapsed_ms,
    safe_run_check,
)

_DESTRUCTIVE_KEYWORDS = ("delete", "drop", "truncate", "remove", "destroy", "overwrite")
_RISK_THRESHOLDS: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 999,
}


class PiiExposureCheck:
    """Detect policy-violating PII in deliverable payloads."""

    name = "pii_exposure"
    version = "1"

    def __init__(self, detector: PIIDetector | None = None) -> None:
        self._detector = detector or PIIDetector()

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        payload = artifact(ctx, "deliverable_payload", "report_payload", "narrative")
        if payload is None:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="deliverable payload is unavailable",
                duration_ms=elapsed_ms(start),
            )

        pii_policy = str(artifact(ctx, "pii_policy", default="mask")).lower()
        matches = self._detector.detect(payload)
        evidence = {
            "pii_policy": pii_policy,
            "matches": [
                {"type": match.pii_type, "location": match.location, "sample": match.sample}
                for match in matches
            ],
        }
        if not matches or pii_policy == "allow":
            return CheckResult(
                check_id=self.name,
                status="pass",
                score=1.0,
                evidence=evidence,
                message="no policy-violating PII found",
                duration_ms=elapsed_ms(start),
            )

        rendered = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        is_masked = "[REDACTED_" in rendered
        if pii_policy == "mask" and is_masked:
            status, score, message = "warn", 0.55, "PII is present but appears masked"
        else:
            status, score, message = "fail", 0.0, "unmasked PII found in deliverable payload"
        return CheckResult(
            check_id=self.name,
            status=status,  # type: ignore[arg-type]
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint=(
                "Mask or drop sensitive fields before delivery."
                if status != "pass"
                else None
            ),
            duration_ms=elapsed_ms(start),
        )


class AccessScopeCheck:
    """Ensure data sources accessed during execution were explicitly allowed."""

    name = "access_scope"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        run_log = list(artifact(ctx, "run_log", default=[]))
        allowed = {
            f"{grant.warehouse}.{grant.schema_name}"
            for grant in ctx.task_contract.allowed_data_sources
        }
        extra_allowed = set(str(item) for item in artifact(ctx, "allowed_sources", default=[]))
        allowed |= extra_allowed

        accessed: list[str] = []
        violations: list[str] = []
        for event in run_log:
            if not isinstance(event, Mapping):
                continue
            if str(event.get("type", "")).lower() != "source_access":
                continue
            source = str(event.get("source") or f"{event.get('warehouse')}.{event.get('schema')}")
            accessed.append(source)
            if allowed and source not in allowed:
                violations.append(source)

        evidence = {"allowed_sources": sorted(allowed), "accessed_sources": accessed}
        if violations:
            return CheckResult(
                check_id=self.name,
                status="fail",
                score=0.0,
                evidence={**evidence, "violations": violations},
                message=f"accessed sources outside contract: {', '.join(violations[:3])}",
                remediation_hint="Restrict reads to the task contract's approved sources.",
                duration_ms=elapsed_ms(start),
            )
        if not accessed:
            status, score, message = "skipped", 1.0, "source access events are unavailable"
        else:
            status, score, message = "pass", 1.0, "all accessed sources were allowed"
        return CheckResult(
            check_id=self.name,
            status=status,  # type: ignore[arg-type]
            score=score,
            evidence=evidence,
            message=message,
            duration_ms=elapsed_ms(start),
        )


class CostBudgetComplianceCheck:
    """Compare observed run costs to the declared budget."""

    name = "cost_budget_compliance"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        observed_cost = artifact(ctx, "observed_cost_usd")
        if observed_cost is None:
            observed_cost = self._sum_costs(artifact(ctx, "run_log", default=[]))

        budget = (
            artifact(ctx, "cost_budget_usd")
            or ctx.task_contract.budget.max_compute_cost_usd
            or ctx.task_contract.budget.max_llm_cost_usd
        )
        if observed_cost is None or budget is None:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="cost budget inputs are unavailable",
                duration_ms=elapsed_ms(start),
            )

        cost = float(observed_cost)
        budget_limit = float(budget)
        ratio = 0.0 if budget_limit == 0 else cost / budget_limit
        evidence = {"observed_cost_usd": cost, "budget_usd": budget_limit, "ratio": ratio}
        if cost > budget_limit:
            status, score, message = "fail", 0.0, "run cost exceeds the declared budget"
        elif ratio >= 0.8:
            status, score, message = "warn", 0.55, "run cost is approaching the declared budget"
        else:
            status, score, message = "pass", 1.0, "run cost is within budget"
        return CheckResult(
            check_id=self.name,
            status=status,  # type: ignore[arg-type]
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint=(
                "Trim tool usage or narrow scope before retrying."
                if status != "pass"
                else None
            ),
            duration_ms=elapsed_ms(start),
        )

    @staticmethod
    def _sum_costs(run_log: Sequence[Any]) -> float | None:
        total = 0.0
        found = False
        for event in run_log:
            if not isinstance(event, Mapping):
                continue
            for key in ("cost_usd", "llm_cost_usd", "query_cost_usd", "storage_cost_usd"):
                if event.get(key) is not None:
                    total += float(event[key])
                    found = True
        return total if found else None


class RiskyActionDetectionCheck:
    """Flag destructive actions that exceed the allowed risk level."""

    name = "risky_action_detection"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        run_log = list(artifact(ctx, "run_log", default=[]))
        risk_level = str(artifact(ctx, "risk_level", default="low")).lower()
        destructive: list[str] = []
        write_like: list[str] = []
        for event in run_log:
            if not isinstance(event, Mapping):
                continue
            action = str(event.get("action", event.get("tool", ""))).lower()
            if not action:
                continue
            if any(keyword in action for keyword in _DESTRUCTIVE_KEYWORDS):
                destructive.append(action)
            elif "write" in action or "update" in action:
                write_like.append(action)

        evidence = {
            "risk_level": risk_level,
            "destructive_actions": destructive,
            "write_actions": write_like,
        }
        threshold = _RISK_THRESHOLDS.get(risk_level, 0)
        if len(destructive) > threshold:
            status, score, message = (
                "fail",
                0.0,
                "destructive actions exceed the allowed risk level",
            )
        elif destructive or write_like:
            status, score, message = "warn", 0.55, "write/destructive actions require review"
        else:
            status, score, message = "pass", 1.0, "no risky actions detected"
        return CheckResult(
            check_id=self.name,
            status=status,  # type: ignore[arg-type]
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Escalate destructive steps or lower execution privileges."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )


class RetentionPolicyCheck:
    """Verify every emitted artifact has a compatible retention label."""

    name = "retention_policy"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        items = artifact(ctx, "retention_items")
        if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="retention metadata is unavailable",
                duration_ms=elapsed_ms(start),
            )

        violations: list[str] = []
        normalized: list[dict[str, str | None]] = []
        for item in items:
            if not isinstance(item, Mapping):
                continue
            artifact_name = str(item.get("artifact", "artifact"))
            retention_label = item.get("retention_label")
            storage_retention = item.get("storage_retention")
            normalized.append(
                {
                    "artifact": artifact_name,
                    "retention_label": None if retention_label is None else str(retention_label),
                    "storage_retention": (
                        None if storage_retention is None else str(storage_retention)
                    ),
                }
            )
            if retention_label is None:
                violations.append(f"{artifact_name}:missing_label")
            elif storage_retention is not None and str(retention_label) != str(storage_retention):
                violations.append(f"{artifact_name}:mismatch")

        evidence = {"retention_items": normalized, "violations": violations}
        if violations:
            status, score, message = (
                "fail",
                0.0,
                "retention policy metadata is incomplete or mismatched",
            )
        else:
            status, score, message = "pass", 1.0, "retention metadata is consistent"
        return CheckResult(
            check_id=self.name,
            status=status,  # type: ignore[arg-type]
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Attach explicit retention labels before persisting artifacts."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )


class WriteSideEffectPreviewCheck:
    """Confirm planned writes have an explicit preview or approval path."""

    name = "write_side_effect_preview"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        write_events = [
            event
            for event in artifact(ctx, "run_log", default=[])
            if isinstance(event, Mapping)
            and str(event.get("type", "")).lower() == "write"
        ]
        if not write_events:
            return CheckResult(
                check_id=self.name,
                status="pass",
                score=1.0,
                evidence={"write_events": []},
                message="no write side effects recorded",
                duration_ms=elapsed_ms(start),
            )

        preview_missing = [
            str(event.get("target", event.get("action", "write")))
            for event in write_events
            if not bool(event.get("preview_available", False))
        ]
        auto_approved = all(bool(event.get("auto_approved", False)) for event in write_events)
        evidence = {
            "write_events": [dict(event) for event in write_events],
            "preview_missing": preview_missing,
            "auto_approved": auto_approved,
        }
        if auto_approved and not preview_missing:
            status, score, message = "pass", 1.0, "write previews were approved automatically"
        else:
            status, score, message = "warn", 0.55, "write side effects require explicit review"
        return CheckResult(
            check_id=self.name,
            status=status,  # type: ignore[arg-type]
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint=(
                "Generate dry-run previews before committing writes."
                if status != "pass"
                else None
            ),
            duration_ms=elapsed_ms(start),
        )


class PolicyVerifier(PolicyVerifierPort):
    """Run the policy verifier layer deterministically."""

    def __init__(self, checks: Sequence[PolicyCheck] | None = None) -> None:
        self._checks = list(
            checks
            or [
                PiiExposureCheck(),
                AccessScopeCheck(),
                CostBudgetComplianceCheck(),
                RiskyActionDetectionCheck(),
                RetentionPolicyCheck(),
                WriteSideEffectPreviewCheck(),
            ]
        )

    async def run(self, ctx: VerifierContext) -> LayerResult:
        results = [safe_run_check(ctx, check) for check in self._checks]
        return aggregate_layer(layer="policy", checks=results)
