"""Application service for running verifier layers in parallel."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from ds_agent.application.ports.task_contract_support import Clock
from ds_agent.application.services.mission_required_checks import (
    MissionRequiredCheckResolver,
    MissionRequiredChecksResolution,
    build_mission_required_check_metadata,
)
from ds_agent.domain.dtos.verifier_context import VerifierContext
from ds_agent.domain.entities.review_verdict import (
    ActionHint,
    Issue,
    LayerResult,
    ReviewVerdict,
)
from ds_agent.domain.interfaces.verifier_ports import (
    ConfidenceScorerPort,
    DataVerifierPort,
    NarrativeVerifierPort,
    PolicyVerifierPort,
    ShadowComparatorPort,
    ShadowComparisonRepository,
    StatisticalVerifierPort,
    VerdictRepository,
)

_LAYER_TIMEOUTS = {
    "statistical": "statistical_timeout_s",
    "data": "data_timeout_s",
    "policy": "policy_timeout_s",
    "narrative": "narrative_timeout_s",
}
_LAYER_PRIORITY = {"error": 4, "fail": 3, "warn": 2, "pass": 1}


class VerifierOrchestrator:
    """Coordinate layer verifiers, aggregate a verdict, and persist it."""

    def __init__(
        self,
        *,
        statistical: StatisticalVerifierPort,
        data: DataVerifierPort,
        policy: PolicyVerifierPort,
        narrative: NarrativeVerifierPort,
        repo: VerdictRepository,
        scorer: ConfidenceScorerPort,
        clock: Clock,
        shadow_comparator: ShadowComparatorPort | None = None,
        shadow_repo: ShadowComparisonRepository | None = None,
        mission_required_check_resolver: MissionRequiredCheckResolver | None = None,
    ) -> None:
        self._statistical = statistical
        self._data = data
        self._policy = policy
        self._narrative = narrative
        self._repo = repo
        self._scorer = scorer
        self._clock = clock
        self._shadow_comparator = shadow_comparator
        self._shadow_repo = shadow_repo
        self._mission_required_check_resolver = mission_required_check_resolver

    async def run(self, ctx: VerifierContext) -> ReviewVerdict:
        layers: list[LayerResult] = []
        mission_preflight = self._resolve_mission_preflight(ctx)
        async with asyncio.TaskGroup() as tg:
            tasks = {
                "statistical": tg.create_task(
                    self._with_timeout(
                        "statistical",
                        self._statistical.run(ctx),
                        timeout_s=ctx.config.statistical_timeout_s,
                    )
                ),
                "data": tg.create_task(
                    self._with_timeout(
                        "data",
                        self._data.run(ctx),
                        timeout_s=ctx.config.data_timeout_s,
                    )
                ),
                "policy": tg.create_task(
                    self._with_timeout(
                        "policy",
                        self._policy.run(ctx),
                        timeout_s=ctx.config.policy_timeout_s,
                    )
                ),
                "narrative": tg.create_task(
                    self._with_timeout(
                        "narrative",
                        self._narrative.run(ctx),
                        timeout_s=ctx.config.narrative_timeout_s,
                    )
                ),
            }
        for name in ("statistical", "data", "policy", "narrative"):
            layers.append(tasks[name].result())

        verdict = ReviewVerdict(
            verdict_id=f"RV-{time.time_ns()}",
            task_id=ctx.task_contract.task_id,
            run_id=ctx.run_id,
            category="orchestrator",
            reviewer="verifier_orchestrator",
            created_at=self._clock.now(),
            layers=layers,
            blocking_issues=self._derive_issues(layers),
        )
        confidence = self._scorer.score(verdict)
        verdict.confidence = confidence
        verdict.summary = confidence.rationale
        verdict.metadata.update(self._derive_metadata(layers))
        if mission_preflight is not None:
            verdict.metadata.update(
                build_mission_required_check_metadata(mission_preflight, layers)
            )
        verdict.recommended_actions = self._derive_actions(verdict)
        self._record_shadow_comparison(ctx, verdict)
        self._repo.save(verdict)
        return verdict

    def _resolve_mission_preflight(
        self,
        ctx: VerifierContext,
    ) -> MissionRequiredChecksResolution | None:
        if self._mission_required_check_resolver is None:
            return None
        return self._mission_required_check_resolver.resolve_for_mission(
            ctx.task_contract.mission
        )

    def _record_shadow_comparison(self, ctx: VerifierContext, verdict: ReviewVerdict) -> None:
        if not ctx.config.shadow_mode:
            return
        if self._shadow_comparator is None or self._shadow_repo is None:
            return
        record = self._shadow_comparator.compare(ctx, verdict)
        if record is None:
            return
        self._shadow_repo.save(record)
        verdict.metadata["shadow_comparison_id"] = record.comparison_id
        verdict.metadata["shadow_match_rate"] = record.match_rate
        verdict.metadata["shadow_mismatch_count"] = record.mismatch_count
        verdict.metadata["shadow_applicable_count"] = record.applicable_count

    async def _with_timeout(
        self,
        layer_name: str,
        coro: Any,
        *,
        timeout_s: int,
    ) -> LayerResult:
        try:
            return await asyncio.wait_for(coro, timeout=timeout_s)
        except TimeoutError:
            return LayerResult(
                layer=layer_name,  # type: ignore[arg-type]
                overall="error",
                score=0.0,
                summary=f"{layer_name} verifier timed out",
                partial_failure=True,
            )
        except Exception as exc:
            return LayerResult(
                layer=layer_name,  # type: ignore[arg-type]
                overall="error",
                score=0.0,
                summary=str(exc),
                partial_failure=True,
                metadata={"exception_type": type(exc).__name__},
            )

    @staticmethod
    def _derive_issues(layers: list[LayerResult]) -> list[Issue]:
        issues: list[Issue] = []
        for layer in layers:
            for check in layer.checks:
                if check.status not in {"fail", "error"}:
                    continue
                severity = "critical" if layer.layer == "policy" else "high"
                issues.append(
                    Issue(
                        issue_id=f"{layer.layer}:{check.check_id}",
                        layer=layer.layer,
                        check_id=check.check_id,
                        severity=severity,  # type: ignore[arg-type]
                        message=check.message,
                        evidence=check.evidence,
                        blocking=True,
                    )
                )
            if layer.overall == "error" and not layer.checks:
                issues.append(
                    Issue(
                        issue_id=f"{layer.layer}:layer_error",
                        layer=layer.layer,
                        severity="high",
                        message=layer.summary or f"{layer.layer} layer failed",
                        evidence=layer.metadata,
                        blocking=True,
                    )
                )
        return issues

    @staticmethod
    def _derive_metadata(layers: list[LayerResult]) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        narrative_layer = next((layer for layer in layers if layer.layer == "narrative"), None)
        if narrative_layer is None:
            return metadata

        judge_mode = narrative_layer.metadata.get("judge_mode")
        if isinstance(judge_mode, str) and judge_mode.strip():
            metadata["judge_mode"] = judge_mode.strip()

        judge_check_count = narrative_layer.metadata.get("judge_check_count")
        if isinstance(judge_check_count, int):
            metadata["judge_check_count"] = judge_check_count

        for key in ("judge_error", "judge_error_message"):
            value = narrative_layer.metadata.get(key)
            if isinstance(value, str) and value.strip():
                metadata[key] = value.strip()
        return metadata

    @staticmethod
    def _derive_actions(verdict: ReviewVerdict) -> list[ActionHint]:
        actions: list[ActionHint] = []
        for issue in verdict.blocking_issues:
            title = f"Resolve {issue.layer or 'verifier'} issue"
            actions.append(
                ActionHint(
                    action_id=f"action:{issue.issue_id}",
                    title=title,
                    description=issue.message,
                    priority="high" if issue.severity in {"high", "critical"} else "medium",
                    scope=issue.layer,
                    related_issue_ids=[issue.issue_id] if issue.issue_id else [],
                )
            )
        if not actions and verdict.confidence is not None and verdict.confidence.grade != "high":
            actions.append(
                ActionHint(
                    action_id="action:review-low-confidence",
                    title="Review verifier caveats",
                    description=verdict.confidence.rationale,
                    priority="medium",
                )
            )
        return actions
