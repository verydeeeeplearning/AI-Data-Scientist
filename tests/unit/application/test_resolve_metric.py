from __future__ import annotations

from ds_agent.memory.semantic.application.resolve_metric import ResolveMetricUseCase
from ds_agent.memory.semantic.domain.metric import Metric, MetricGrain


class _MetricRepo:
    def __init__(self, metrics: list[Metric]) -> None:
        self._metrics = metrics

    def get(self, metric_id: str) -> Metric | None:
        return next(
            (metric for metric in self._metrics if metric.metric_id == metric_id),
            None,
        )

    def resolve(
        self,
        query: str,
        *,
        grain: MetricGrain | None = None,
        limit: int = 5,
    ) -> list[Metric]:
        filtered = self._metrics
        if grain is not None:
            filtered = [metric for metric in filtered if metric.grain == grain]
        return filtered[:limit]

    def save(self, metric: Metric) -> None:
        self._metrics.append(metric)


def _metric(metric_id: str, display_name: str, *, synonyms: list[str], owner: str) -> Metric:
    return Metric(
        metric_id=metric_id,
        display_name=display_name,
        owner=owner,
        definition=f"{display_name} definition",
        synonyms=synonyms,
        grain="monthly",
        unit="ratio",
        direction="lower_is_better",
        calculation={
            "numerator": {
                "source": "prod.metric",
                "filter": "x = 1",
                "aggregation": "COUNT(*)",
            }
        },
    )


def test_resolve_metric_exact_match() -> None:
    repo = _MetricRepo(
        [
            _metric(
                "monthly_churn_rate",
                "Monthly Churn Rate",
                synonyms=["churn"],
                owner="growth",
            )
        ]
    )
    result = ResolveMetricUseCase(repo).execute("Monthly Churn Rate")

    assert result.kind == "exact"
    assert result.best_match is not None
    assert result.best_match.metric.metric_id == "monthly_churn_rate"


def test_resolve_metric_prefers_synonym_match() -> None:
    repo = _MetricRepo(
        [
            _metric(
                "monthly_churn_rate",
                "Monthly Churn Rate",
                synonyms=["customer churn"],
                owner="growth",
            )
        ]
    )
    result = ResolveMetricUseCase(repo).execute("customer churn")

    assert result.kind == "synonym"
    assert result.best_match is not None
    assert result.best_match.match_kind == "synonym"


def test_resolve_metric_re_ranks_with_preferred_owner() -> None:
    repo = _MetricRepo(
        [
            _metric(
                "finance_churn_rate",
                "Monthly Churn Rate",
                synonyms=["churn"],
                owner="finance",
            ),
            _metric(
                "monthly_churn_rate",
                "Monthly Churn Rate",
                synonyms=["churn"],
                owner="growth",
            ),
        ]
    )
    result = ResolveMetricUseCase(repo).execute("churn", preferred_owners=["growth"])

    assert result.best_match is not None
    assert result.best_match.metric.owner == "growth"


def test_resolve_metric_returns_no_match() -> None:
    result = ResolveMetricUseCase(_MetricRepo([])).execute("unknown metric")

    assert result.kind == "no_match"
    assert result.matches == []
