from __future__ import annotations

from pathlib import Path

import pytest

from ds_agent.memory.semantic.infrastructure.yaml_metric_loader import YamlMetricLoader


def _write_pack(pack_dir: Path, *, schema_version: int = 6, checksum: str | None = None) -> None:
    (pack_dir / "metrics").mkdir(parents=True, exist_ok=True)
    lines = [
        "pack_id: acme_corp_2026_q2",
        'display_name: "ACME Corp Semantic Pack (2026 Q2)"',
        "owner: data_platform_team",
        "version: 1.3.0",
        f"requires_semantic_layer_schema_version: {schema_version}",
    ]
    if checksum is not None:
        lines.append(f'checksum: "{checksum}"')
    (pack_dir / "pack.yaml").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def _metric_yaml(metric_id: str, display_name: str) -> str:
    return "\n".join(
        [
            f"metric_id: {metric_id}",
            f"display_name: {display_name}",
            "owner: growth_team",
            'definition: "Monthly customer churn rate"',
            "synonyms:",
            "  - customer churn",
            "grain: monthly",
            "unit: ratio",
            "direction: lower_is_better",
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


def _glossary_yaml() -> str:
    return "\n".join(
        [
            "term_id: term.churn",
            "canonical_form: churn",
            'definition: "Customer churn metric."',
            "synonyms:",
            "  - customer churn",
            "linked_metric_ids:",
            "  - monthly_churn_rate",
            "category: metric",
            "owner: growth_team",
        ]
    )


def _trust_yaml() -> str:
    return "\n".join(
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
    )


def _verified_query_sql() -> str:
    return "\n".join(
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
    )


def test_yaml_metric_loader_loads_pack_metadata_and_semantic_artifacts(tmp_path) -> None:
    pack_dir = tmp_path / "acme-pack"
    _write_pack(pack_dir)
    (pack_dir / "glossary").mkdir(parents=True, exist_ok=True)
    (pack_dir / "trust").mkdir(parents=True, exist_ok=True)
    (pack_dir / "verified_queries").mkdir(parents=True, exist_ok=True)
    (pack_dir / "metrics" / "monthly_churn_rate.yaml").write_text(
        _metric_yaml("monthly_churn_rate", "Monthly Churn Rate"),
        encoding="utf-8",
    )
    (pack_dir / "glossary" / "churn.yaml").write_text(_glossary_yaml(), encoding="utf-8")
    (pack_dir / "trust" / "subscription.yaml").write_text(_trust_yaml(), encoding="utf-8")
    (pack_dir / "verified_queries" / "vq-monthly-churn-postgres.sql").write_text(
        _verified_query_sql(),
        encoding="utf-8",
    )

    loaded = YamlMetricLoader().load_pack(pack_dir)

    assert loaded.pack_metadata["pack_id"] == "acme_corp_2026_q2"
    assert [metric.metric_id for metric in loaded.metrics] == ["monthly_churn_rate"]
    assert [term.term_id for term in loaded.glossary_terms] == ["term.churn"]
    assert [table.fqtn for table in loaded.table_trust] == ["prod.growth.subscription"]
    assert [query.vq_id for query in loaded.verified_queries] == ["vq-monthly-churn-postgres"]


def test_yaml_metric_loader_rejects_duplicate_metric_ids(tmp_path) -> None:
    pack_dir = tmp_path / "acme-pack"
    _write_pack(pack_dir)
    (pack_dir / "metrics" / "metric_a.yaml").write_text(
        _metric_yaml("monthly_churn_rate", "Monthly Churn Rate"),
        encoding="utf-8",
    )
    (pack_dir / "metrics" / "metric_b.yaml").write_text(
        _metric_yaml("monthly_churn_rate", "Monthly Churn Rate Copy"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate metric_id"):
        YamlMetricLoader().load_pack(pack_dir)


def test_yaml_metric_loader_rejects_schema_version_mismatch(tmp_path) -> None:
    pack_dir = tmp_path / "acme-pack"
    _write_pack(pack_dir, schema_version=5)

    with pytest.raises(ValueError, match="schema version mismatch"):
        YamlMetricLoader().load_pack(pack_dir)


def test_yaml_metric_loader_accepts_matching_checksum(tmp_path) -> None:
    pack_dir = tmp_path / "acme-pack"
    _write_pack(pack_dir)
    (pack_dir / "metrics" / "monthly_churn_rate.yaml").write_text(
        _metric_yaml("monthly_churn_rate", "Monthly Churn Rate"),
        encoding="utf-8",
    )
    loader = YamlMetricLoader()
    checksum = loader.compute_pack_checksum(pack_dir)
    _write_pack(pack_dir, checksum=checksum)

    loaded = loader.load_pack(pack_dir)

    assert loaded.pack_metadata["checksum"] == checksum


def test_yaml_metric_loader_rejects_checksum_mismatch(tmp_path) -> None:
    pack_dir = tmp_path / "acme-pack"
    _write_pack(pack_dir, checksum="sha256:deadbeef")
    (pack_dir / "metrics" / "monthly_churn_rate.yaml").write_text(
        _metric_yaml("monthly_churn_rate", "Monthly Churn Rate"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="checksum mismatch"):
        YamlMetricLoader().load_pack(pack_dir)


def test_yaml_metric_loader_rejects_missing_verified_query_frontmatter(tmp_path) -> None:
    pack_dir = tmp_path / "acme-pack"
    _write_pack(pack_dir)
    (pack_dir / "verified_queries").mkdir(parents=True, exist_ok=True)
    (pack_dir / "verified_queries" / "broken.sql").write_text(
        "SELECT 1;",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="frontmatter"):
        YamlMetricLoader().load_pack(pack_dir)


def test_yaml_metric_loader_loads_builtin_enterprise_pack_seed_baseline() -> None:
    pack_dir = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "ds_agent"
        / "skills"
        / "domain"
        / "domain-pack-enterprise"
    )

    loaded = YamlMetricLoader().load_pack(pack_dir)

    assert len(loaded.metrics) >= 10
    assert len(loaded.glossary_terms) >= 30
    assert len(loaded.table_trust) >= 20
    assert len(loaded.verified_queries) >= 15
    assert "monthly_churn_rate" in {metric.metric_id for metric in loaded.metrics}
    assert "monthly_active_users" in {metric.metric_id for metric in loaded.metrics}
    assert "lifetime_value" in {metric.metric_id for metric in loaded.metrics}
