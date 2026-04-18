from __future__ import annotations

from datetime import UTC, date, datetime

from ds_agent.infrastructure.semantic_memory_container import build_semantic_memory_container
from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.domain.trust import TableTrust
from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery


def _metric(
    *,
    definition: str = "Monthly customer churn rate",
    synonyms: list[str] | None = None,
) -> Metric:
    return Metric.model_validate(
        {
            "metric_id": "monthly_churn_rate",
            "display_name": "Monthly Churn Rate",
            "owner": "growth_team",
            "definition": definition,
            "synonyms": synonyms or ["customer churn"],
            "grain": "monthly",
            "unit": "ratio",
            "direction": "lower_is_better",
            "verified_query_ids": ["vq-monthly-churn-postgres"],
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
        }
    )


def _glossary() -> GlossaryTerm:
    return GlossaryTerm.model_validate(
        {
            "term_id": "term.churn",
            "canonical_form": "churn",
            "definition": "Customer churn metric.",
            "linked_metric_ids": ["monthly_churn_rate"],
            "category": "metric",
            "owner": "growth_team",
        }
    )


def _trust(*, grade: str = "gold") -> TableTrust:
    return TableTrust.model_validate(
        {
            "fqtn": "prod.growth.subscription",
            "grade": grade,
            "owner": "growth_team",
            "description": "Subscription fact table",
            "refresh": {"cadence": "daily", "max_staleness_minutes": 1440},
            "grade_rationale": "Certified by analytics engineering",
            "last_audited": "2026-04-15",
        }
    )


def _verified_query(*, evidence: str = "Dashboard parity") -> VerifiedQuery:
    return VerifiedQuery.model_validate(
        {
            "vq_id": "vq-monthly-churn-postgres",
            "metric_id": "monthly_churn_rate",
            "dialect": "postgres",
            "description": "Verified monthly churn query",
            "sql_template": "SELECT 0.05 AS monthly_churn_rate",
            "referenced_tables": ["prod.growth.subscription"],
            "verified_by": "reviewer@corp.example",
            "last_verified": "2026-04-15",
            "verification_evidence": evidence,
        }
    )


def test_sqlite_semantic_snapshot_repo_restores_secondary_tables(tmp_path) -> None:
    container = build_semantic_memory_container(
        workspace_dir=str(tmp_path),
        db_path=str(tmp_path / "semantic.db"),
    )
    container.metrics.save(_metric())
    container.glossary.save(_glossary())
    container.trust.save(_trust())
    container.verified_queries.save(_verified_query())
    container.verified_queries.append_audit(
        "vq-monthly-churn-postgres",
        verified_by="reviewer@corp.example",
        verification_evidence="Dashboard parity",
        verified_at=date(2026, 4, 15),
    )

    created = container.snapshots.create(
        snapshot_id="semantic_snapshot-001",
        source_name="test",
        created_at=datetime(2026, 4, 16, 13, 0, tzinfo=UTC),
        note="baseline semantic state",
    )

    container.metrics.save(
        _metric(
            definition="Updated definition",
            synonyms=["gross churn"],
        )
    )
    container.trust.save(_trust(grade="silver"))
    container.verified_queries.save(_verified_query(evidence="New evidence"))
    container.verified_queries.append_audit(
        "vq-monthly-churn-postgres",
        verified_by="reviewer@corp.example",
        verification_evidence="New evidence",
        verified_at=date(2026, 4, 16),
    )

    summaries = container.list_semantic_snapshots.execute(limit=5)
    restored = container.restore_semantic_snapshot.execute("semantic_snapshot-001")

    assert created.total_rows == 6
    assert summaries[0].snapshot_id == "semantic_snapshot-001"
    assert restored.snapshot.snapshot_id == "semantic_snapshot-001"
    assert restored.restored_rows == 6
    assert "semantic_metric_synonym" in restored.restored_tables
    assert "semantic_verified_query_audit" in restored.restored_tables

    restored_metric = container.metrics.get("monthly_churn_rate")
    assert restored_metric is not None
    assert restored_metric.definition == "Monthly customer churn rate"
    assert container.metrics.resolve("customer churn")[0].metric_id == "monthly_churn_rate"

    with container.db.lock, container.db.connect() as conn:
        synonym_rows = conn.execute(
            """
            SELECT synonym
            FROM semantic_metric_synonym
            WHERE metric_id = ?
            ORDER BY synonym
            """,
            ("monthly_churn_rate",),
        ).fetchall()
        audit_count = conn.execute(
            "SELECT COUNT(*) AS count FROM semantic_verified_query_audit"
        ).fetchone()

    assert [str(row["synonym"]) for row in synonym_rows] == ["customer churn"]
    assert audit_count is not None
    assert int(audit_count["count"]) == 1
