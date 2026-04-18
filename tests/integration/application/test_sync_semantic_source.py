from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.infrastructure.semantic_memory_container import build_semantic_memory_container
from ds_agent.memory.semantic.application.ports import SemanticSyncPolicy
from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.domain.trust import TableTrust
from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery


class _StubExternalSource:
    name = "dbt_metricflow"

    def fetch_metrics(self, since: datetime | None) -> list[Metric]:
        del since
        return [
            Metric.model_validate(
                {
                    "metric_id": "monthly_churn_rate",
                    "display_name": "Monthly Churn Rate",
                    "owner": "growth_team",
                    "definition": "Monthly churn from external semantic layer",
                    "synonyms": ["churn"],
                    "grain": "monthly",
                    "unit": "ratio",
                    "direction": "lower_is_better",
                    "calculation": {
                        "numerator": {
                            "source": "prod.growth.subscription",
                            "filter": "event_type = 'cancel'",
                            "aggregation": "COUNT(*)",
                        },
                        "denominator": {
                            "source": "prod.growth.subscription",
                            "filter": "status = 'active'",
                            "aggregation": "COUNT(*)",
                        },
                    },
                    "verified_query_ids": ["vq-monthly-churn-postgres"],
                }
            )
        ]

    def fetch_glossary_terms(self, since: datetime | None) -> list[GlossaryTerm]:
        del since
        return [
            GlossaryTerm.model_validate(
                {
                    "term_id": "term.monthly_churn_rate",
                    "canonical_form": "monthly churn rate",
                    "definition": "Monthly churn business definition",
                    "linked_metric_ids": ["monthly_churn_rate"],
                    "category": "metric",
                    "owner": "growth_team",
                }
            )
        ]

    def fetch_tables(self, since: datetime | None) -> list[TableTrust]:
        del since
        return [
            TableTrust.model_validate(
                {
                    "fqtn": "prod.growth.subscription",
                    "grade": "gold",
                    "owner": "growth_team",
                    "description": "Subscription fact table",
                    "refresh": {"cadence": "daily", "max_staleness_minutes": 1440},
                    "grade_rationale": "Certified in external catalog",
                    "last_audited": "2026-04-16",
                }
            )
        ]

    def fetch_verified_queries(self, since: datetime | None) -> list[VerifiedQuery]:
        del since
        return [
            VerifiedQuery.model_validate(
                {
                    "vq_id": "vq-monthly-churn-postgres",
                    "metric_id": "monthly_churn_rate",
                    "dialect": "postgres",
                    "description": "Verified churn SQL",
                    "sql_template": "SELECT 0.05 AS monthly_churn_rate",
                    "referenced_tables": ["prod.growth.subscription"],
                    "verified_by": "reviewer@corp.example",
                    "last_verified": "2026-04-15",
                    "verification_evidence": "Dashboard parity",
                }
            )
        ]


def test_sync_semantic_source_apply_persists_namespaced_external_artifacts(tmp_path) -> None:
    container = build_semantic_memory_container(workspace_dir=str(tmp_path))

    result = container.sync_semantic_source.execute(
        _StubExternalSource(),
        policy=SemanticSyncPolicy(
            source_name="dbt_metricflow",
            overwrite=False,
            id_namespace="dbt:",
        ),
        since=datetime(2026, 4, 1, tzinfo=UTC),
        dry_run=False,
    )

    assert result.applied_metric_ids == ["dbt:monthly_churn_rate"]
    assert result.applied_glossary_term_ids == ["term.monthly_churn_rate"]
    assert result.applied_table_ids == ["prod.growth.subscription"]
    assert result.applied_verified_query_ids == ["dbt:vq-monthly-churn-postgres"]
    assert container.metrics.get("dbt:monthly_churn_rate") is not None
    assert container.glossary.get("term.monthly_churn_rate") is not None
    assert container.trust.get("prod.growth.subscription") is not None
    query = container.verified_queries.get("dbt:vq-monthly-churn-postgres")
    assert query is not None
    assert query.metric_id == "dbt:monthly_churn_rate"
