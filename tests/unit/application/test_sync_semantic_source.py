from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.memory.semantic.application.ports import SemanticSyncPolicy
from ds_agent.memory.semantic.application.sync_semantic_source import (
    SyncSemanticSourceUseCase,
)
from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.domain.trust import TableTrust
from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery


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


class _GlossaryRepo:
    def __init__(self, existing: list[GlossaryTerm] | None = None) -> None:
        self._items = {term.term_id: term for term in (existing or [])}
        self.saved: list[GlossaryTerm] = []

    def get(self, term_id: str) -> GlossaryTerm | None:
        return self._items.get(term_id)

    def lookup(self, query: str, *, limit: int = 5) -> list[GlossaryTerm]:
        del query
        return list(self._items.values())[:limit]

    def save(self, term: GlossaryTerm) -> None:
        self._items[term.term_id] = term
        self.saved.append(term)


class _VerifiedQueryRepo:
    def __init__(self, existing: list[VerifiedQuery] | None = None) -> None:
        self._items = {query.vq_id: query for query in (existing or [])}
        self.saved: list[VerifiedQuery] = []

    def get(self, vq_id: str) -> VerifiedQuery | None:
        return self._items.get(vq_id)

    def find_by_metric(self, metric_id: str, *, dialect=None) -> list[VerifiedQuery]:
        return [query for query in self._items.values() if query.metric_id == metric_id]

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
    ):
        raise NotImplementedError


class _ExternalSource:
    name = "dbt_metricflow"

    def __init__(
        self,
        *,
        metrics: list[Metric] | None = None,
        glossary: list[GlossaryTerm] | None = None,
        tables: list[TableTrust] | None = None,
        queries: list[VerifiedQuery] | None = None,
    ) -> None:
        self._metrics = metrics or []
        self._glossary = glossary or []
        self._tables = tables or []
        self._queries = queries or []

    def fetch_metrics(self, since: datetime | None) -> list[Metric]:
        del since
        return list(self._metrics)

    def fetch_glossary_terms(self, since: datetime | None) -> list[GlossaryTerm]:
        del since
        return list(self._glossary)

    def fetch_tables(self, since: datetime | None) -> list[TableTrust]:
        del since
        return list(self._tables)

    def fetch_verified_queries(self, since: datetime | None) -> list[VerifiedQuery]:
        del since
        return list(self._queries)


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
        return datetime(2026, 4, 16, 12, 30, tzinfo=UTC)


class _FixedIds:
    def new_task_id(self, now: datetime) -> str:
        return f"task-{int(now.timestamp())}"

    def new_artifact_id(self, prefix: str) -> str:
        return f"{prefix}-sync"


def _metric(metric_id: str, *, definition: str = "Monthly churn metric") -> Metric:
    return Metric.model_validate(
        {
            "metric_id": metric_id,
            "display_name": metric_id.replace("_", " ").title(),
            "owner": "growth_team",
            "definition": definition,
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
            "verified_query_ids": ["vq-monthly-churn"],
        }
    )


def _glossary(
    term_id: str = "term.monthly_churn_rate",
    *,
    linked_metric_ids: list[str] | None = None,
    definition: str = "Monthly churn definition",
) -> GlossaryTerm:
    return GlossaryTerm.model_validate(
        {
            "term_id": term_id,
            "canonical_form": "monthly churn rate",
            "definition": definition,
            "synonyms": ["churn"],
            "linked_metric_ids": linked_metric_ids or ["monthly_churn_rate"],
            "category": "metric",
            "owner": "growth_team",
        }
    )


def _table(fqtn: str, *, grade: str = "silver", rationale: str = "Auto-seeded") -> TableTrust:
    return TableTrust.model_validate(
        {
            "fqtn": fqtn,
            "grade": grade,
            "owner": "growth_team",
            "description": "Subscription fact table",
            "refresh": {"cadence": "daily", "max_staleness_minutes": 1440},
            "columns": [],
            "approved_joins": [],
            "grade_rationale": rationale,
            "last_audited": "2026-04-16",
        }
    )


def _query(
    vq_id: str,
    *,
    metric_id: str = "monthly_churn_rate",
    evidence: str = "Dashboard parity",
) -> VerifiedQuery:
    return VerifiedQuery.model_validate(
        {
            "vq_id": vq_id,
            "metric_id": metric_id,
            "dialect": "postgres",
            "description": "Verified query",
            "sql_template": "SELECT 0.05 AS monthly_churn_rate",
            "parameters": [],
            "referenced_tables": ["prod.growth.subscription"],
            "verified_by": "reviewer@corp.example",
            "last_verified": "2026-04-15",
            "verification_evidence": evidence,
        }
    )


def test_sync_semantic_source_dry_run_namespaces_metrics_and_queries() -> None:
    metrics = _MetricRepo()
    glossary = _GlossaryRepo()
    trust = _TrustRepo()
    queries = _VerifiedQueryRepo()
    use_case = SyncSemanticSourceUseCase(metrics, glossary, trust, queries)

    result = use_case.execute(
        _ExternalSource(
            metrics=[_metric("monthly_churn_rate")],
            glossary=[_glossary()],
            tables=[_table("prod.growth.subscription", grade="gold")],
            queries=[_query("vq-monthly-churn")],
        ),
        policy=SemanticSyncPolicy(
            source_name="dbt_metricflow",
            id_namespace="dbt:",
        ),
        dry_run=True,
    )

    assert result.metric_diffs[0].artifact_id == "dbt:monthly_churn_rate"
    assert result.glossary_diffs[0].artifact_id == "term.monthly_churn_rate"
    assert result.trust_diffs[0].artifact_id == "prod.growth.subscription"
    assert result.verified_query_diffs[0].artifact_id == "dbt:vq-monthly-churn"
    assert result.applied_metric_ids == []
    assert metrics.saved == []


def test_sync_semantic_source_skips_existing_and_filters_disallowed_grades() -> None:
    metrics = _MetricRepo(existing=[_metric("monthly_churn_rate", definition="Existing metric")])
    glossary = _GlossaryRepo(existing=[_glossary(definition="Existing glossary")])
    trust = _TrustRepo(existing=[_table("prod.growth.subscription")])
    queries = _VerifiedQueryRepo(existing=[_query("vq-monthly-churn")])
    use_case = SyncSemanticSourceUseCase(metrics, glossary, trust, queries)

    result = use_case.execute(
        _ExternalSource(
            metrics=[_metric("monthly_churn_rate")],
            glossary=[_glossary(definition="New glossary")],
            tables=[_table("prod.growth.subscription", grade="bronze")],
            queries=[_query("vq-monthly-churn")],
        ),
        policy=SemanticSyncPolicy(source_name="postgres"),
        dry_run=False,
    )

    assert result.metric_diffs[0].status == "skipped"
    assert result.metric_diffs[0].reason == "existing_metric_preserved"
    assert result.glossary_diffs[0].status == "skipped"
    assert result.glossary_diffs[0].reason == "existing_glossary_term_preserved"
    assert result.trust_diffs[0].status == "skipped"
    assert result.trust_diffs[0].reason == "filtered_grade:bronze"
    assert result.verified_query_diffs[0].status == "unchanged"
    assert result.applied_metric_ids == []
    assert result.applied_glossary_term_ids == []
    assert result.applied_table_ids == []


def test_sync_semantic_source_apply_updates_existing_records_when_overwrite_enabled() -> None:
    metrics = _MetricRepo(existing=[_metric("monthly_churn_rate", definition="Old definition")])
    glossary = _GlossaryRepo(existing=[_glossary(definition="Old glossary")])
    trust = _TrustRepo(
        existing=[_table("prod.growth.subscription", rationale="Old rationale")]
    )
    queries = _VerifiedQueryRepo(existing=[_query("vq-monthly-churn", evidence="Old evidence")])
    use_case = SyncSemanticSourceUseCase(metrics, glossary, trust, queries)

    result = use_case.execute(
        _ExternalSource(
            metrics=[_metric("monthly_churn_rate", definition="New definition")],
            glossary=[_glossary(definition="New glossary")],
            tables=[_table("prod.growth.subscription", rationale="New rationale")],
            queries=[_query("vq-monthly-churn", evidence="New evidence")],
        ),
        policy=SemanticSyncPolicy(
            source_name="postgres",
            overwrite=True,
        ),
        since=datetime(2026, 4, 1, tzinfo=UTC),
        dry_run=False,
    )

    assert result.metric_diffs[0].status == "update"
    assert result.glossary_diffs[0].status == "update"
    assert result.trust_diffs[0].status == "update"
    assert result.verified_query_diffs[0].status == "update"
    assert result.applied_metric_ids == ["monthly_churn_rate"]
    assert result.applied_glossary_term_ids == ["term.monthly_churn_rate"]
    assert result.applied_table_ids == ["prod.growth.subscription"]
    assert result.applied_verified_query_ids == ["vq-monthly-churn"]
    assert metrics.saved[0].definition == "New definition"
    assert glossary.saved[0].definition == "New glossary"
    assert trust.saved[0].grade_rationale == "New rationale"
    assert queries.saved[0].verification_evidence == "New evidence"


def test_sync_semantic_source_apply_creates_snapshot_before_write() -> None:
    metrics = _MetricRepo()
    glossary = _GlossaryRepo()
    trust = _TrustRepo()
    queries = _VerifiedQueryRepo()
    snapshots = _SnapshotRepo()
    use_case = SyncSemanticSourceUseCase(
        metrics,
        glossary,
        trust,
        queries,
        snapshots,
        _FixedClock(),
        _FixedIds(),
    )

    result = use_case.execute(
        _ExternalSource(
            metrics=[_metric("monthly_churn_rate")],
            glossary=[_glossary()],
            tables=[_table("prod.growth.subscription", grade="gold")],
            queries=[_query("vq-monthly-churn")],
        ),
        policy=SemanticSyncPolicy(source_name="postgres"),
        dry_run=False,
    )

    assert result.snapshot_id == "semantic_snapshot-sync"
    assert snapshots.created[0]["source_name"] == "sync:postgres"


def test_sync_semantic_source_skips_glossary_when_linked_metric_is_unknown() -> None:
    use_case = SyncSemanticSourceUseCase(
        _MetricRepo(),
        _GlossaryRepo(),
        _TrustRepo(),
        _VerifiedQueryRepo(),
    )

    result = use_case.execute(
        _ExternalSource(glossary=[_glossary(linked_metric_ids=["missing_metric"])]),
        policy=SemanticSyncPolicy(source_name="looker"),
        dry_run=False,
    )

    assert result.glossary_diffs[0].status == "skipped"
    assert result.glossary_diffs[0].reason == "unknown_metric:missing_metric"
