"""Narrative verifier layer."""

from __future__ import annotations

import re
from collections.abc import Sequence
from time import perf_counter

from ds_agent.domain.dtos.verifier_context import VerifierContext
from ds_agent.domain.entities.review_verdict import CheckResult, CheckStatus, LayerResult
from ds_agent.domain.interfaces.verifier_ports import (
    LLMJudgePort,
    NarrativeCheck,
    NarrativeVerifierPort,
)
from ds_agent.infrastructure.verifiers.common import (
    aggregate_layer,
    artifact,
    elapsed_ms,
    safe_run_check,
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?%?")
_STRONG_TERMS = (
    "always",
    "never",
    "clearly",
    "definitely",
    "prove",
    "guarantee",
    "명확",
    "반드시",
)
_HEDGE_TERMS = ("may", "might", "could", "possibly", "perhaps", "가능", "추정")
_CAUSAL_TERMS = (
    "cause",
    "causes",
    "caused",
    "drives",
    "driven",
    "because",
    "effect",
    "원인",
    "유발",
)


class ClaimEvidenceAlignmentCheck:
    """Check whether narrative claims are supported by evidence excerpts."""

    name = "claim_evidence_alignment"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        narrative = str(artifact(ctx, "narrative", default="") or "").strip()
        if not narrative:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="narrative text is unavailable",
                duration_ms=elapsed_ms(start),
            )

        claims = [part.strip() for part in _SENTENCE_SPLIT_RE.split(narrative) if part.strip()]
        evidence_text = " ".join(
            filter(None, (ref.excerpt or "" for ref in ctx.evidence_refs))
        ).lower()
        unsupported: list[str] = []
        for claim in claims:
            if not self._is_supported(claim, evidence_text):
                unsupported.append(claim)

        unsupported_rate = 0.0 if not claims else len(unsupported) / len(claims)
        evidence = {
            "claim_count": len(claims),
            "unsupported_claims": unsupported,
            "unsupported_rate": unsupported_rate,
        }
        if unsupported_rate > 0.20:
            status: CheckStatus = "fail"
            score = 0.0
            message = "too many unsupported narrative claims"
        elif unsupported_rate > 0.05:
            status = "warn"
            score = 0.55
            message = "some narrative claims are weakly supported"
        else:
            status = "pass"
            score = 1.0
            message = "narrative claims align with evidence excerpts"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Link every important claim to an explicit evidence excerpt."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )

    @staticmethod
    def _is_supported(claim: str, evidence_text: str) -> bool:
        if not evidence_text:
            return False
        numbers = [value.rstrip("%") for value in _NUMBER_RE.findall(claim)]
        if numbers and any(number in evidence_text for number in numbers):
            return True
        tokens = {token.lower() for token in re.findall(r"[A-Za-z]{4,}", claim)}
        if not tokens:
            return False
        overlap = sum(token in evidence_text for token in tokens)
        return overlap >= max(1, min(2, len(tokens)))


class OverstatementHedgeCheck:
    """Flag narratives that over-claim or hedge excessively."""

    name = "overstatement_hedge_detection"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        narrative = str(artifact(ctx, "narrative", default="") or "").strip().lower()
        if not narrative:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="narrative text is unavailable",
                duration_ms=elapsed_ms(start),
            )

        strong_count = sum(term in narrative for term in _STRONG_TERMS)
        hedge_count = sum(term in narrative for term in _HEDGE_TERMS)
        evidence_strength = len(ctx.evidence_refs)
        evidence = {
            "strong_count": strong_count,
            "hedge_count": hedge_count,
            "evidence_ref_count": evidence_strength,
        }
        if strong_count > evidence_strength and evidence_strength == 0:
            status: CheckStatus = "fail"
            score = 0.0
            message = "narrative overstates unsupported certainty"
        elif strong_count > evidence_strength or hedge_count > max(2, strong_count * 2):
            status = "warn"
            score = 0.55
            message = "narrative tone is imbalanced for the evidence"
        else:
            status = "pass"
            score = 1.0
            message = "narrative tone matches the evidence strength"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Reduce absolute language or trim unnecessary hedging."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )


class CausalLanguageAppropriatenessCheck:
    """Prevent causal language for observational analyses."""

    name = "causal_language_appropriateness"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        narrative = str(artifact(ctx, "narrative", default="") or "").lower()
        if not narrative:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="narrative text is unavailable",
                duration_ms=elapsed_ms(start),
            )

        analysis_mode = str(artifact(ctx, "analysis_mode", default=ctx.task_contract.type)).lower()
        causal_found = [term for term in _CAUSAL_TERMS if term in narrative]
        experimental = any(
            token in analysis_mode for token in ("experiment", "ab_test", "rct", "quasi")
        )
        evidence = {"analysis_mode": analysis_mode, "causal_terms": causal_found}
        if causal_found and not experimental:
            status: CheckStatus = "fail"
            score = 0.0
            message = "causal language used for a non-experimental analysis"
        elif causal_found:
            status = "pass"
            score = 1.0
            message = "causal language matches the experiment design"
        else:
            status = "pass"
            score = 1.0
            message = "no problematic causal language detected"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint=(
                "Rewrite causal claims as associations unless the design is experimental."
                if status != "pass"
                else None
            ),
            duration_ms=elapsed_ms(start),
        )


class MetricCitationAccuracyCheck:
    """Compare cited numeric metrics to the artifact metrics dictionary."""

    name = "metric_citation_accuracy"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        narrative = str(artifact(ctx, "narrative", default="") or "").strip()
        metrics = artifact(ctx, "metrics")
        if not narrative or not isinstance(metrics, dict) or not metrics:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="narrative metrics are unavailable",
                duration_ms=elapsed_ms(start),
            )

        cited_values = []
        for token in _NUMBER_RE.findall(narrative):
            normalized = float(token.rstrip("%"))
            if token.endswith("%"):
                normalized /= 100.0
            cited_values.append(normalized)

        metric_values = [
            float(value) for value in metrics.values() if isinstance(value, (int, float))
        ]
        mismatches = [
            value for value in cited_values if not self._matches_metric(value, metric_values)
        ]
        evidence = {
            "cited_values": cited_values,
            "metric_values": metric_values,
            "mismatches": mismatches,
        }
        if mismatches:
            status: CheckStatus = "fail"
            score = 0.0
            message = "narrative cites metrics that do not match artifacts"
        else:
            status = "pass"
            score = 1.0
            message = "narrative metrics match artifact values"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Regenerate the summary from the latest metric payload."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )

    @staticmethod
    def _matches_metric(cited: float, metric_values: Sequence[float]) -> bool:
        for metric in metric_values:
            tolerance = max(0.005, abs(metric) * 0.01)
            if abs(cited - metric) <= tolerance:
                return True
        return False


class RecommendationFeasibilityCheck:
    """Ensure recommendations remain within known constraints."""

    name = "recommendation_feasibility"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        recommendations = artifact(ctx, "recommendations")
        if not isinstance(recommendations, Sequence) or isinstance(recommendations, (str, bytes)):
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="recommendations are unavailable",
                duration_ms=elapsed_ms(start),
            )

        infeasible_terms = [
            str(value).lower() for value in artifact(ctx, "infeasible_actions", default=[])
        ]
        infeasible: list[str] = []
        for item in recommendations:
            text = str(item)
            lowered = text.lower()
            if any(term in lowered for term in infeasible_terms):
                infeasible.append(text)

        evidence = {"recommendations": list(recommendations), "infeasible": infeasible}
        if infeasible:
            status: CheckStatus = "fail"
            score = 0.0
            message = "recommendations exceed current scope or constraints"
        else:
            status = "pass"
            score = 1.0
            message = "recommendations are feasible within scope"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Remove or caveat recommendations that cannot be executed."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )


class NarrativeVerifier(NarrativeVerifierPort):
    """Run the narrative verifier layer with lightweight deterministic heuristics."""

    def __init__(
        self,
        checks: Sequence[NarrativeCheck] | None = None,
        *,
        judge: LLMJudgePort | None = None,
    ) -> None:
        self._checks = list(
            checks
            or [
                ClaimEvidenceAlignmentCheck(),
                OverstatementHedgeCheck(),
                CausalLanguageAppropriatenessCheck(),
                MetricCitationAccuracyCheck(),
                RecommendationFeasibilityCheck(),
            ]
        )
        self._judge = judge

    async def run(self, ctx: VerifierContext) -> LayerResult:
        heuristic_results = [safe_run_check(ctx, check) for check in self._checks]
        judge_results: list[CheckResult] = []
        judge_error: Exception | None = None

        if self._judge is not None:
            try:
                judge_results = await self._judge.evaluate(ctx)
            except Exception as exc:  # pragma: no cover - defensive fallback
                judge_error = exc

        results = self._merge_results(heuristic_results, judge_results)
        layer = aggregate_layer(layer="narrative", checks=results)
        if judge_results:
            layer.metadata["judge_mode"] = "llm"
            layer.metadata["judge_check_count"] = len(judge_results)
        elif judge_error is not None:
            layer.metadata["judge_mode"] = "heuristic_fallback"
            layer.metadata["judge_error"] = type(judge_error).__name__
            layer.metadata["judge_error_message"] = str(judge_error)
        else:
            layer.metadata["judge_mode"] = "heuristic_only"
        return layer

    @staticmethod
    def _merge_results(
        heuristic_results: Sequence[CheckResult],
        judge_results: Sequence[CheckResult],
    ) -> list[CheckResult]:
        if not judge_results:
            return list(heuristic_results)

        judge_by_id = {check.check_id: check for check in judge_results}
        merged = [judge_by_id.pop(check.check_id, check) for check in heuristic_results]
        merged.extend(judge_by_id.values())
        return merged
