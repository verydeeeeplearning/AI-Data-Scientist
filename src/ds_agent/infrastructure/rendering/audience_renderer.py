"""Audience-aware result-card rendering for backend-authoritative reads."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ds_agent.application.use_cases.render_card_for_audience_usecase import (
    CardAudience,
    CardRenderingPort,
    RenderedAudienceCard,
    RenderedCardSection,
)
from ds_agent.domain.result_card import (
    ArtifactCard,
    ExperimentCard,
    InsightCard,
    OtherCard,
    ResultCard,
    RiskCard,
)


class AudienceRenderer(CardRenderingPort):
    """Deterministically render a persisted card for one audience."""

    def render(self, card: ResultCard, audience: CardAudience) -> RenderedAudienceCard:
        if isinstance(card, InsightCard):
            return self._render_insight(card, audience)
        if isinstance(card, ExperimentCard):
            return self._render_experiment(card, audience)
        if isinstance(card, RiskCard):
            return self._render_risk(card, audience)
        if isinstance(card, ArtifactCard):
            return self._render_artifact(card, audience)
        if isinstance(card, OtherCard):
            return self._render_other(card, audience)
        return RenderedAudienceCard(
            summary="Additional result",
            body="No structured rendering was available for this card.",
            sections=[],
        )

    def _render_insight(self, card: InsightCard, audience: CardAudience) -> RenderedAudienceCard:
        metric = card.key_metric
        summary = _first_non_empty(
            _metric_summary(metric),
            card.title,
        )

        if audience == "exec":
            sections = [
                _section(
                    "impact",
                    "Why it matters",
                    _bullet_block(
                        [
                            f"Decision signal: {summary}",
                            f"Trust status: {card.trust_status}",
                        ]
                    ),
                ),
                _section("evidence", "Evidence", _bullet_block(card.evidence)),
            ]
            body = _intro(
                f"Executive view: {summary}.",
                "Focus on the decision signal and the evidence that supports it.",
            )
        elif audience == "ml":
            sections = [
                _section("metric", "Key metric", _metric_section(metric)),
                _section("evidence", "Evidence", _bullet_block(card.evidence)),
                _section("trust", "Trust", f"Trust status: {card.trust_status}"),
            ]
            body = _intro(
                f"Technical view: {summary}.",
                "Review the metric, evidence, and trust details below.",
            )
        else:
            sections = [
                _section("metric", "Key metric", _metric_section(metric)),
                _section("evidence", "Evidence", _bullet_block(card.evidence)),
                _section("trust", "Trust", f"Trust status: {card.trust_status}"),
            ]
            body = _intro(
                f"Data-scientist view: {summary}.",
                "This preserves the structured signal and the supporting evidence.",
            )

        return RenderedAudienceCard(summary=summary, body=body, sections=sections)

    def _render_experiment(
        self,
        card: ExperimentCard,
        audience: CardAudience,
    ) -> RenderedAudienceCard:
        metric = card.primary_metric
        summary = _first_non_empty(
            _metric_summary(metric),
            card.data_version,
            card.model_label,
        )

        if audience == "exec":
            sections = [
                _section("outcome", "Outcome", _metric_section(metric)),
                _section("model", "Model", card.model_label),
                _section("data", "Data version", card.data_version),
            ]
            body = _intro(
                f"Executive view: {summary}.",
                "This summarizes the experiment result and the deployment-relevant context.",
            )
        else:
            sections = [
                _section("metric", "Primary metric", _metric_section(metric)),
                _section("model", "Model", card.model_label),
                _section("data", "Data version", card.data_version),
                _section("artifacts", "Linked artifacts", _artifact_refs_block(card.artifact_refs)),
            ]
            body = _intro(
                f"Technical view: {summary}.",
                "Use the sections below for the model, data, and linked artifact details.",
            )

        return RenderedAudienceCard(summary=summary, body=body, sections=sections)

    def _render_risk(self, card: RiskCard, audience: CardAudience) -> RenderedAudienceCard:
        summary = _first_non_empty(f"{card.severity} / {card.category}", card.title)

        if audience == "exec":
            sections = [
                _section("impact", "Impact", card.impact),
                _section("mitigation", "Mitigation", card.recommendation),
            ]
            body = _intro(
                f"Executive view: {summary}.",
                "Prioritize mitigation before the risk reaches a decision gate.",
            )
        else:
            sections = [
                _section("target", "Target", card.target),
                _section("impact", "Impact", card.impact),
                _section("recommendation", "Recommendation", card.recommendation),
            ]
            body = _intro(
                f"Technical view: {summary}.",
                "Review the impacted surface, the expected impact, and the recommendation.",
            )

        return RenderedAudienceCard(summary=summary, body=body, sections=sections)

    def _render_artifact(
        self,
        card: ArtifactCard,
        audience: CardAudience,
    ) -> RenderedAudienceCard:
        summary = _first_non_empty(f"{card.artifact_kind} / {card.file_ref}", card.title)

        if audience == "exec":
            sections = [
                _section("artifact", "Artifact", card.artifact_kind),
                _section("location", "File", card.file_ref),
            ]
            body = _intro(
                f"Executive view: {summary}.",
                "This is the handoff surface for the generated deliverable.",
            )
        else:
            sections = [
                _section("artifact", "Artifact kind", card.artifact_kind),
                _section("origin", "Generated by", card.generated_by_tool),
                _section("location", "File", card.file_ref),
            ]
            if card.source_experiment_run_id:
                sections.append(
                    _section(
                        "source-experiment",
                        "Source experiment",
                        card.source_experiment_run_id,
                    ),
                )
            body = _intro(
                f"Technical view: {summary}.",
                "Use the sections below for the artifact origin and file location.",
            )

        return RenderedAudienceCard(summary=summary, body=body, sections=sections)

    def _render_other(self, card: OtherCard, audience: CardAudience) -> RenderedAudienceCard:
        del audience
        summary = _first_non_empty(card.title, "Additional result")
        body = card.body or "No structured card body was provided."
        return RenderedAudienceCard(
            summary=summary,
            body=body,
            sections=[_section("content", "Content", body)],
        )


def _section(section_id: str, title: str, body: str | None) -> RenderedCardSection:
    return RenderedCardSection(
        id=section_id,
        title=title,
        body=body if body and body.strip() else "No evidence provided.",
    )


def _intro(headline: str, detail: str) -> str:
    return f"{headline}\n\n{detail}"


def _first_non_empty(*values: str | None) -> str:
    for value in values:
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed:
                return trimmed
    return "Additional result"


def _metric_summary(metric: Any) -> str | None:
    if metric is None:
        return None
    name = getattr(metric, "label", None) or getattr(metric, "name", None)
    value = getattr(metric, "value", None)
    if name is None or value is None:
        return None
    return f"{name}: {value}"


def _metric_section(metric: Any) -> str:
    if metric is None:
        return "No metric provided."
    name = getattr(metric, "label", None) or getattr(metric, "name", None)
    value = getattr(metric, "value", None)
    delta = getattr(metric, "delta", None) or getattr(metric, "delta_vs_baseline", None)
    lines = [
        f"- {name}: {value}" if name is not None and value is not None else "- Metric unavailable",
    ]
    if delta not in {None, ""}:
        lines.append(f"- Delta: {delta}")
    return "\n".join(lines)


def _artifact_refs_block(refs: Sequence[Any]) -> str:
    if not refs:
        return "No linked artifacts."
    lines: list[str] = []
    for ref in refs:
        label = getattr(ref, "artifact_id", None) or getattr(ref, "ref", None) or "artifact"
        target = getattr(ref, "kind", None)
        if target:
            lines.append(f"- {label} ({target})")
        else:
            lines.append(f"- {label}")
    return "\n".join(lines)


def _bullet_block(values: Sequence[str]) -> str:
    cleaned = [value.strip() for value in values if isinstance(value, str) and value.strip()]
    if not cleaned:
        return "No evidence provided."
    return "\n".join(f"- {value}" for value in cleaned)
