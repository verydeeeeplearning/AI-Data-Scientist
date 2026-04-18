"""Confidence scoring for review verdicts."""

from __future__ import annotations

from ds_agent.domain.entities.review_verdict import ConfidenceBand, LayerResult, ReviewVerdict

_DEFAULT_LAYER_WEIGHTS: dict[str, float] = {
    "statistical": 0.40,
    "data": 0.25,
    "policy": 0.15,
    "narrative": 0.20,
}
_LEGACY_RESULT_SCORES: dict[str, float] = {
    "pass": 0.85,
    "warn": 0.55,
    "fail": 0.20,
}


def _clamp_score(value: float) -> float:
    return max(0.0, min(1.0, value))


class ConfidenceScorer:
    """Deterministic scorer for verifier verdict confidence."""

    def __init__(
        self,
        *,
        layer_weights: dict[str, float] | None = None,
        blocker_penalty: float = 0.25,
    ) -> None:
        self._layer_weights = dict(layer_weights or _DEFAULT_LAYER_WEIGHTS)
        self._blocker_penalty = blocker_penalty

    def score(self, verdict: ReviewVerdict) -> ConfidenceBand:
        """Convert a verdict into a confidence band."""

        raw_score = self._score_layers(verdict)
        blocker_count = sum(1 for issue in verdict.blocking_issues if issue.blocking)
        penalty_multiplier = max(0.0, 1.0 - (self._blocker_penalty * blocker_count))
        score = _clamp_score(raw_score * penalty_multiplier)
        return ConfidenceBand(score=score, rationale=self.explain(verdict))

    def explain(self, verdict: ReviewVerdict) -> str:
        """Summarize the most confidence-reducing factors in one short sentence."""

        parts: list[str] = []
        blockers = [issue.message.strip() for issue in verdict.blocking_issues if issue.blocking]
        if blockers:
            parts.append(f"blocked by: {', '.join(blockers[:2])}")

        scored_checks = [
            check
            for layer in verdict.layers
            for check in layer.checks
            if check.status != "skipped"
        ]
        scored_checks.sort(key=lambda item: item.score)
        for check in scored_checks[:3]:
            parts.append(f"{check.check_id}: {check.message}")

        if not parts and verdict.summary:
            parts.append(verdict.summary)
        if not parts:
            parts.append(f"{verdict.category} review {verdict.result}")

        rationale = " | ".join(part for part in parts if part)
        return rationale[:350]

    def _score_layers(self, verdict: ReviewVerdict) -> float:
        weighted_score = 0.0
        weighted_layers = 0
        for layer in verdict.layers:
            weight = self._layer_weights.get(layer.layer)
            if weight is None:
                continue
            weighted_score += weight * self._score_layer(layer)
            weighted_layers += 1

        if weighted_layers == 0:
            return _LEGACY_RESULT_SCORES.get(verdict.result or "warn", 0.55)
        return weighted_score

    @staticmethod
    def _score_layer(layer: LayerResult) -> float:
        score = layer.score if layer.score is not None else 0.0
        if layer.partial_failure:
            return _clamp_score(score * 0.75)
        return _clamp_score(score)
