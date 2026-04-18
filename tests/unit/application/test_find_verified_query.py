from __future__ import annotations

from datetime import date

import pytest

from ds_agent.memory.semantic.application.find_verified_query import (
    FindVerifiedQueryUseCase,
)
from ds_agent.memory.semantic.domain.verified_query import QueryDialect, VerifiedQuery


class _VerifiedQueryRepo:
    def __init__(self, queries: list[VerifiedQuery]) -> None:
        self._queries = queries

    def get(self, vq_id: str) -> VerifiedQuery | None:
        return next((query for query in self._queries if query.vq_id == vq_id), None)

    def find_by_metric(
        self,
        metric_id: str,
        *,
        dialect: QueryDialect | None = None,
    ) -> list[VerifiedQuery]:
        return [
            query
            for query in self._queries
            if query.metric_id == metric_id
            and (dialect is None or query.dialect == dialect)
        ]

    def save(self, query: VerifiedQuery) -> None:
        self._queries.append(query)

    def append_audit(
        self,
        vq_id: str,
        *,
        verified_by: str,
        verification_evidence: str,
        verified_at: date,
    ) -> None:
        self.audit = (vq_id, verified_by, verification_evidence, verified_at)


def _query(dialect: QueryDialect = "postgres") -> VerifiedQuery:
    return VerifiedQuery(
        vq_id=f"vq-{dialect}",
        metric_id="monthly_churn_rate",
        dialect=dialect,
        description="Monthly churn",
        sql_template="SELECT {{ start_date }} AS start_at, {{ end_date }} AS end_at",
        parameters=[
            {"name": "start_date", "type": "date", "description": "inclusive start"},
            {"name": "end_date", "type": "date", "description": "exclusive end"},
        ],
        referenced_tables=["prod.growth.subscription"],
        verified_by="reviewer",
        last_verified=date(2026, 4, 15),
        verification_evidence="Dashboard parity",
    )


def test_find_verified_query_filters_by_dialect_and_binds_params() -> None:
    repo = _VerifiedQueryRepo([_query("postgres"), _query("bigquery")])
    result = FindVerifiedQueryUseCase(repo).execute(
        "monthly_churn_rate",
        dialect="postgres",
        bindings={"start_date": "2026-01-01", "end_date": "2026-02-01"},
    )

    assert result.query is not None
    assert result.query.dialect == "postgres"
    assert result.rendered_sql == "SELECT 2026-01-01 AS start_at, 2026-02-01 AS end_at"


def test_find_verified_query_raises_on_missing_required_parameter() -> None:
    use_case = FindVerifiedQueryUseCase(_VerifiedQueryRepo([_query("postgres")]))

    with pytest.raises(ValueError, match="missing required parameter"):
        use_case.execute(
            "monthly_churn_rate",
            dialect="postgres",
            bindings={"start_date": "2026-01-01"},
        )
