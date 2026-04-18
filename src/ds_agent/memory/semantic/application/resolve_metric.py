"""Use case for resolving metrics from semantic memory."""

from __future__ import annotations

from typing import Literal

from ds_agent.memory.semantic.application.dtos import MetricMatchDTO, ResolveMetricResultDTO
from ds_agent.memory.semantic.application.ports import MetricRepository
from ds_agent.memory.semantic.domain.metric import Metric, MetricGrain

MetricMatchKind = Literal["exact", "synonym", "fuzzy"]


class ResolveMetricUseCase:
    """Resolve and rank metrics for a free-form query."""

    def __init__(self, metrics: MetricRepository) -> None:
        self._metrics = metrics

    def execute(
        self,
        query: str,
        *,
        grain: MetricGrain | None = None,
        preferred_metric_ids: list[str] | None = None,
        preferred_owners: list[str] | None = None,
        limit: int = 5,
    ) -> ResolveMetricResultDTO:
        candidates = self._metrics.resolve(query, grain=grain, limit=limit)
        if not candidates:
            return ResolveMetricResultDTO(query=query, kind="no_match")

        preferred_metric_ids = preferred_metric_ids or []
        preferred_owners = preferred_owners or []
        ranked = sorted(
            (
                self._score_match(
                    metric,
                    query=query,
                    preferred_metric_ids=preferred_metric_ids,
                    preferred_owners=preferred_owners,
                )
                for metric in candidates
            ),
            key=lambda item: item.score,
            reverse=True,
        )
        return ResolveMetricResultDTO(
            query=query,
            kind=ranked[0].match_kind,
            matches=ranked[:limit],
        )

    @staticmethod
    def _score_match(
        metric: Metric,
        *,
        query: str,
        preferred_metric_ids: list[str],
        preferred_owners: list[str],
    ) -> MetricMatchDTO:
        normalized = query.strip().casefold()
        synonyms = [item.casefold() for item in metric.synonyms]
        metric_id = metric.metric_id.casefold()
        display_name = metric.display_name.casefold()
        definition = metric.definition.casefold()
        kind: MetricMatchKind

        if normalized in {metric_id, display_name}:
            score = 1.0
            kind = "exact"
        elif normalized in synonyms:
            score = 0.96
            kind = "synonym"
        else:
            search_space = f"{display_name} {definition}"
            token_hits = sum(1 for token in normalized.split() if token in search_space)
            score = 0.7 + min(token_hits, 3) * 0.05
            kind = "fuzzy"

        if metric.metric_id in preferred_metric_ids:
            score += 0.05
        if metric.owner in preferred_owners:
            score += 0.03

        return MetricMatchDTO(metric=metric, score=score, match_kind=kind)
