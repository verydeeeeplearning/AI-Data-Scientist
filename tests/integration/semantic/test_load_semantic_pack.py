from __future__ import annotations

from pathlib import Path

from ds_agent.infrastructure.semantic_memory_container import build_semantic_memory_container


def _write_pack(pack_dir: Path, metric_yaml: str) -> None:
    (pack_dir / "metrics").mkdir(parents=True, exist_ok=True)
    (pack_dir / "glossary").mkdir(parents=True, exist_ok=True)
    (pack_dir / "trust").mkdir(parents=True, exist_ok=True)
    (pack_dir / "verified_queries").mkdir(parents=True, exist_ok=True)
    (pack_dir / "pack.yaml").write_text(
        "\n".join(
            [
                "pack_id: acme_corp_2026_q2",
                'display_name: "ACME Corp Semantic Pack (2026 Q2)"',
                "owner: data_platform_team",
                "version: 1.3.0",
                "requires_semantic_layer_schema_version: 6",
            ]
        ),
        encoding="utf-8",
    )
    (pack_dir / "metrics" / "monthly_churn_rate.yaml").write_text(
        metric_yaml,
        encoding="utf-8",
    )
    (pack_dir / "glossary" / "churn.yaml").write_text(
        "\n".join(
            [
                "term_id: term.churn",
                "canonical_form: churn",
                'definition: "Customer churn metric."',
                "linked_metric_ids:",
                "  - monthly_churn_rate",
                "category: metric",
                "owner: growth_team",
            ]
        ),
        encoding="utf-8",
    )
    (pack_dir / "trust" / "subscription.yaml").write_text(
        "\n".join(
            [
                "fqtn: prod.growth.subscription",
                "grade: gold",
                "owner: growth_team",
                'description: "Subscription fact table"',
                "refresh:",
                "  cadence: daily",
                "  max_staleness_minutes: 1440",
                "grade_rationale: Certified by analytics engineering",
                "last_audited: 2026-04-15",
            ]
        ),
        encoding="utf-8",
    )
    (pack_dir / "verified_queries" / "vq-monthly-churn-postgres.sql").write_text(
        "\n".join(
            [
                "---",
                "vq_id: vq-monthly-churn-postgres",
                "metric_id: monthly_churn_rate",
                "dialect: postgres",
                "description: Verified churn query",
                "referenced_tables:",
                "  - prod.growth.subscription",
                "verified_by: reviewer@corp.example",
                "last_verified: 2026-04-15",
                "verification_evidence: Dashboard parity",
                "---",
                "SELECT 0.05 AS monthly_churn_rate;",
            ]
        ),
        encoding="utf-8",
    )


def _metric_yaml() -> str:
    return "\n".join(
        [
            "metric_id: monthly_churn_rate",
            "display_name: Monthly Churn Rate",
            "owner: growth_team",
            'definition: "Monthly customer churn rate"',
            "synonyms:",
            "  - customer churn",
            "grain: monthly",
            "unit: ratio",
            "direction: lower_is_better",
            "verified_query_ids:",
            "  - vq-monthly-churn-postgres",
            "calculation:",
            "  numerator:",
            "    source: prod.growth.subscription",
            "    filter: event_type = 'cancel'",
            "    aggregation: COUNT(*)",
            "  denominator:",
            "    source: prod.growth.subscription",
            "    filter: status = 'active'",
            "    aggregation: COUNT(*)",
        ]
    )


def test_load_semantic_pack_round_trip(tmp_path) -> None:
    container = build_semantic_memory_container(db_path=str(tmp_path / "semantic.sqlite3"))
    pack_dir = tmp_path / "acme-pack"
    _write_pack(pack_dir, _metric_yaml())

    dry_run = container.load_semantic_pack.execute(str(pack_dir), dry_run=True)
    applied = container.load_semantic_pack.execute(str(pack_dir), dry_run=False)
    stored = container.metrics.get("monthly_churn_rate")

    assert dry_run.metric_diffs[0].status == "add"
    assert applied.applied_metric_ids == ["monthly_churn_rate"]
    assert applied.applied_glossary_term_ids == ["term.churn"]
    assert applied.applied_table_ids == ["prod.growth.subscription"]
    assert applied.applied_verified_query_ids == ["vq-monthly-churn-postgres"]
    assert stored is not None
    assert stored.metric_id == "monthly_churn_rate"
