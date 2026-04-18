from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ds_agent.memory.semantic.application.load_semantic_pack import (
    LoadSemanticPackUseCase,
)
from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.domain.trust import TableTrust
from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery
from ds_agent.memory.semantic.infrastructure.yaml_metric_loader import YamlMetricLoader


class _MetricRepo:
    def __init__(self, existing: list[Metric] | None = None) -> None:
        self._items = {metric.metric_id: metric for metric in (existing or [])}
        self.saved: list[Metric] = []

    def get(self, metric_id: str) -> Metric | None:
        return self._items.get(metric_id)

    def resolve(self, query: str, *, grain=None, limit: int = 5) -> list[Metric]:
        return list(self._items.values())[:limit]

    def save(self, metric: Metric) -> None:
        self._items[metric.metric_id] = metric
        self.saved.append(metric)


class _GlossaryRepo:
    def __init__(self, existing: list[GlossaryTerm] | None = None) -> None:
        self._items = {term.term_id: term for term in (existing or [])}
        self.saved: list[GlossaryTerm] = []

    def get(self, term_id: str) -> GlossaryTerm | None:
        return self._items.get(term_id)

    def lookup(self, query: str, *, limit: int = 5) -> list[GlossaryTerm]:
        return list(self._items.values())[:limit]

    def save(self, term: GlossaryTerm) -> None:
        self._items[term.term_id] = term
        self.saved.append(term)


class _TrustRepo:
    def __init__(self, existing: list[TableTrust] | None = None) -> None:
        self._items = {table.fqtn: table for table in (existing or [])}
        self.saved: list[TableTrust] = []

    def get(self, fqtn: str) -> TableTrust | None:
        return self._items.get(fqtn)

    def bulk_get(self, fqtns: list[str]) -> list[TableTrust]:
        return [self._items[fqtn] for fqtn in fqtns if fqtn in self._items]

    def save(self, table: TableTrust) -> None:
        self._items[table.fqtn] = table
        self.saved.append(table)


class _VerifiedQueryRepo:
    def __init__(self, existing: list[VerifiedQuery] | None = None) -> None:
        self._items = {query.vq_id: query for query in (existing or [])}
        self.saved: list[VerifiedQuery] = []

    def get(self, vq_id: str) -> VerifiedQuery | None:
        return self._items.get(vq_id)

    def find_by_metric(self, metric_id: str, *, dialect=None) -> list[VerifiedQuery]:
        return [
            item
            for item in self._items.values()
            if item.metric_id == metric_id and (dialect is None or item.dialect == dialect)
        ]

    def save(self, query: VerifiedQuery) -> None:
        self._items[query.vq_id] = query
        self.saved.append(query)

    def append_audit(
        self,
        vq_id: str,
        *,
        verified_by: str,
        verification_evidence: str,
        verified_at,
    ) -> None:
        return None


class _SnapshotRepo:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []

    def create(
        self,
        *,
        snapshot_id: str,
        source_name: str,
        created_at: datetime,
        note: str | None = None,
    ):
        self.created.append(
            {
                "snapshot_id": snapshot_id,
                "source_name": source_name,
                "created_at": created_at,
                "note": note,
            }
        )
        return None

    def get(self, snapshot_id: str):
        raise NotImplementedError

    def list(self, *, limit: int = 20):
        raise NotImplementedError

    def restore(self, snapshot_id: str):
        raise NotImplementedError


class _FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


class _FixedIds:
    def new_task_id(self, now: datetime) -> str:
        return f"task-{int(now.timestamp())}"

    def new_artifact_id(self, prefix: str) -> str:
        return f"{prefix}-001"


def _write_pack(pack_dir: Path, metric_yaml: str) -> None:
    (pack_dir / "metrics").mkdir(parents=True, exist_ok=True)
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


def _write_glossary(pack_dir: Path) -> None:
    (pack_dir / "glossary").mkdir(parents=True, exist_ok=True)
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


def _write_verified_query(pack_dir: Path) -> None:
    (pack_dir / "verified_queries").mkdir(parents=True, exist_ok=True)
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


def _metric_yaml(*, definition: str = "Monthly customer churn rate") -> str:
    return "\n".join(
        [
            "metric_id: monthly_churn_rate",
            "display_name: Monthly Churn Rate",
            "owner: growth_team",
            f'definition: "{definition}"',
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


def _existing_metric(*, definition: str = "Monthly customer churn rate") -> Metric:
    return Metric.model_validate(
        {
            "metric_id": "monthly_churn_rate",
            "display_name": "Monthly Churn Rate",
            "owner": "growth_team",
            "definition": definition,
                "synonyms": ["customer churn"],
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


def test_load_semantic_pack_dry_run_reports_add(tmp_path) -> None:
    pack_dir = tmp_path / "acme-pack"
    _write_pack(pack_dir, _metric_yaml())
    _write_glossary(pack_dir)
    _write_verified_query(pack_dir)
    repo = _MetricRepo()
    glossary = _GlossaryRepo()
    trust = _TrustRepo()
    verified_queries = _VerifiedQueryRepo()

    result = LoadSemanticPackUseCase(
        repo,
        glossary,
        trust,
        verified_queries,
        YamlMetricLoader(),
    ).execute(str(pack_dir))

    assert result.dry_run is True
    assert result.metric_diffs[0].status == "add"
    assert result.glossary_diffs[0].status == "add"
    assert result.verified_query_diffs[0].status == "add"
    assert repo.saved == []


def test_load_semantic_pack_apply_saves_new_metric(tmp_path) -> None:
    pack_dir = tmp_path / "acme-pack"
    _write_pack(pack_dir, _metric_yaml())
    _write_glossary(pack_dir)
    _write_verified_query(pack_dir)
    repo = _MetricRepo()
    glossary = _GlossaryRepo()
    trust = _TrustRepo()
    verified_queries = _VerifiedQueryRepo()

    result = LoadSemanticPackUseCase(
        repo,
        glossary,
        trust,
        verified_queries,
        YamlMetricLoader(),
    ).execute(
        str(pack_dir),
        dry_run=False,
    )

    assert result.applied_metric_ids == ["monthly_churn_rate"]
    assert result.applied_glossary_term_ids == ["term.churn"]
    assert result.applied_verified_query_ids == ["vq-monthly-churn-postgres"]
    assert [metric.metric_id for metric in repo.saved] == ["monthly_churn_rate"]


def test_load_semantic_pack_apply_creates_snapshot_before_write(tmp_path) -> None:
    pack_dir = tmp_path / "acme-pack"
    _write_pack(pack_dir, _metric_yaml())
    _write_glossary(pack_dir)
    _write_verified_query(pack_dir)
    snapshot_repo = _SnapshotRepo()

    result = LoadSemanticPackUseCase(
        _MetricRepo(),
        _GlossaryRepo(),
        _TrustRepo(),
        _VerifiedQueryRepo(),
        YamlMetricLoader(),
        snapshot_repo,
        _FixedClock(),
        _FixedIds(),
    ).execute(
        str(pack_dir),
        dry_run=False,
    )

    assert result.snapshot_id == "semantic_snapshot-001"
    assert snapshot_repo.created[0]["source_name"] == "pack:acme_corp_2026_q2"


def test_load_semantic_pack_blocks_definition_conflict_on_apply(tmp_path) -> None:
    pack_dir = tmp_path / "acme-pack"
    _write_glossary(pack_dir)
    _write_verified_query(pack_dir)
    _write_pack(pack_dir, _metric_yaml(definition="Updated churn definition"))
    repo = _MetricRepo([_existing_metric()])
    glossary = _GlossaryRepo()
    trust = _TrustRepo()
    verified_queries = _VerifiedQueryRepo()

    with pytest.raises(ValueError, match="conflicting artifact definitions"):
        LoadSemanticPackUseCase(
            repo,
            glossary,
            trust,
            verified_queries,
            YamlMetricLoader(),
        ).execute(
            str(pack_dir),
            dry_run=False,
        )


def test_load_semantic_pack_blocks_unknown_linked_metric_reference(tmp_path) -> None:
    pack_dir = tmp_path / "acme-pack"
    _write_pack(pack_dir, _metric_yaml())
    (pack_dir / "glossary").mkdir(parents=True, exist_ok=True)
    (pack_dir / "glossary" / "broken.yaml").write_text(
        "\n".join(
            [
                "term_id: term.ghost",
                "canonical_form: ghost",
                'definition: "Ghost KPI"',
                "linked_metric_ids:",
                "  - unknown_metric",
                "category: metric",
                "owner: growth_team",
            ]
        ),
        encoding="utf-8",
    )
    _write_verified_query(pack_dir)

    with pytest.raises(ValueError, match="unknown metric_id 'unknown_metric'"):
        LoadSemanticPackUseCase(
            _MetricRepo(),
            _GlossaryRepo(),
            _TrustRepo(),
            _VerifiedQueryRepo(),
            YamlMetricLoader(),
        ).execute(str(pack_dir))
