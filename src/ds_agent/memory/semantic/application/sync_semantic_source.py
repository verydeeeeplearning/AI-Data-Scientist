"""Use case for synchronizing external semantic sources."""

from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.application.ports.task_contract_support import Clock, IdGenerator
from ds_agent.memory.semantic.application.dtos import (
    SemanticSyncArtifactDiffDTO,
    SyncSemanticSourceResultDTO,
)
from ds_agent.memory.semantic.application.ports import (
    ExternalSemanticSource,
    GlossaryRepository,
    MetricRepository,
    SemanticSnapshotRepository,
    SemanticSyncPolicy,
    TableTrustRepository,
    VerifiedQueryRepository,
)
from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.domain.trust import TableTrust
from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery


class SyncSemanticSourceUseCase:
    """Merge one external semantic source into canonical semantic storage."""

    def __init__(
        self,
        metrics: MetricRepository,
        glossary: GlossaryRepository,
        trust: TableTrustRepository,
        verified_queries: VerifiedQueryRepository,
        snapshots: SemanticSnapshotRepository | None = None,
        clock: Clock | None = None,
        ids: IdGenerator | None = None,
    ) -> None:
        self._metrics = metrics
        self._glossary = glossary
        self._trust = trust
        self._verified_queries = verified_queries
        self._snapshots = snapshots
        self._clock = clock
        self._ids = ids

    def execute(
        self,
        source: ExternalSemanticSource,
        *,
        policy: SemanticSyncPolicy,
        since: datetime | None = None,
        dry_run: bool = True,
    ) -> SyncSemanticSourceResultDTO:
        synced_metrics = [
            self._apply_metric_namespace(metric, policy.id_namespace)
            for metric in source.fetch_metrics(since)
        ]
        synced_glossary = [
            self._apply_glossary_namespace(term, policy.id_namespace)
            for term in source.fetch_glossary_terms(since)
        ]
        synced_tables = list(source.fetch_tables(since))
        synced_queries = [
            self._apply_verified_query_namespace(query, policy.id_namespace)
            for query in source.fetch_verified_queries(since)
        ]
        metric_ids = {metric.metric_id for metric in synced_metrics}

        metric_diffs: list[SemanticSyncArtifactDiffDTO] = []
        glossary_diffs: list[SemanticSyncArtifactDiffDTO] = []
        trust_diffs: list[SemanticSyncArtifactDiffDTO] = []
        verified_query_diffs: list[SemanticSyncArtifactDiffDTO] = []
        metrics_to_apply: list[Metric] = []
        glossary_to_apply: list[GlossaryTerm] = []
        tables_to_apply: list[TableTrust] = []
        queries_to_apply: list[VerifiedQuery] = []

        for metric in synced_metrics:
            diff = self._classify_metric(metric, overwrite=policy.overwrite)
            metric_diffs.append(diff)
            if diff.status in {"add", "update"}:
                metrics_to_apply.append(metric)

        for term in synced_glossary:
            unresolved_metric_ids = [
                metric_id
                for metric_id in term.linked_metric_ids
                if self._metrics.get(metric_id) is None and metric_id not in metric_ids
            ]
            if unresolved_metric_ids:
                glossary_diffs.append(
                    SemanticSyncArtifactDiffDTO(
                        artifact_type="glossary",
                        artifact_id=term.term_id,
                        status="skipped",
                        reason="unknown_metric:" + ",".join(unresolved_metric_ids),
                    )
                )
                continue

            diff = self._classify_glossary(term, overwrite=policy.overwrite)
            glossary_diffs.append(diff)
            if diff.status in {"add", "update"}:
                glossary_to_apply.append(term)

        for table in synced_tables:
            diff = self._classify_table(
                table,
                overwrite=policy.overwrite,
                policy=policy,
            )
            trust_diffs.append(diff)
            if diff.status in {"add", "update"}:
                tables_to_apply.append(table)

        for query in synced_queries:
            if query.metric_id is not None and query.metric_id not in metric_ids:
                existing_metric = self._metrics.get(query.metric_id)
                if existing_metric is None:
                    verified_query_diffs.append(
                        SemanticSyncArtifactDiffDTO(
                            artifact_type="verified_query",
                            artifact_id=query.vq_id,
                            status="skipped",
                            reason=f"unknown_metric:{query.metric_id}",
                        )
                    )
                    continue

            diff = self._classify_verified_query(query, overwrite=policy.overwrite)
            verified_query_diffs.append(diff)
            if diff.status in {"add", "update"}:
                queries_to_apply.append(query)

        applied_metric_ids: list[str] = []
        applied_glossary_term_ids: list[str] = []
        applied_table_ids: list[str] = []
        applied_verified_query_ids: list[str] = []
        snapshot_id: str | None = None
        if not dry_run:
            if metrics_to_apply or glossary_to_apply or tables_to_apply or queries_to_apply:
                snapshot_id = self._create_snapshot(
                    source_name=f"sync:{policy.source_name or source.name}",
                    note=f"Before syncing semantic source {policy.source_name or source.name}",
                )
            for metric in metrics_to_apply:
                self._metrics.save(metric)
                applied_metric_ids.append(metric.metric_id)
            for term in glossary_to_apply:
                self._glossary.save(term)
                applied_glossary_term_ids.append(term.term_id)
            for table in tables_to_apply:
                self._trust.save(table)
                applied_table_ids.append(table.fqtn)
            for query in queries_to_apply:
                self._verified_queries.save(query)
                applied_verified_query_ids.append(query.vq_id)

        return SyncSemanticSourceResultDTO(
            source_name=policy.source_name or source.name,
            dry_run=dry_run,
            since=since,
            overwrite=policy.overwrite,
            id_namespace=policy.id_namespace,
            snapshot_id=snapshot_id,
            allowed_grades=[grade.value for grade in policy.allowed_grades],
            metric_diffs=metric_diffs,
            glossary_diffs=glossary_diffs,
            trust_diffs=trust_diffs,
            verified_query_diffs=verified_query_diffs,
            applied_metric_ids=applied_metric_ids,
            applied_glossary_term_ids=applied_glossary_term_ids,
            applied_table_ids=applied_table_ids,
            applied_verified_query_ids=applied_verified_query_ids,
        )

    def _classify_metric(
        self,
        metric: Metric,
        *,
        overwrite: bool,
    ) -> SemanticSyncArtifactDiffDTO:
        existing = self._metrics.get(metric.metric_id)
        if existing is None:
            return SemanticSyncArtifactDiffDTO(
                artifact_type="metric",
                artifact_id=metric.metric_id,
                status="add",
                reason="new_metric",
            )
        if existing.model_dump(mode="json") == metric.model_dump(mode="json"):
            return SemanticSyncArtifactDiffDTO(
                artifact_type="metric",
                artifact_id=metric.metric_id,
                status="unchanged",
            )
        if not overwrite:
            return SemanticSyncArtifactDiffDTO(
                artifact_type="metric",
                artifact_id=metric.metric_id,
                status="skipped",
                reason="existing_metric_preserved",
            )
        return SemanticSyncArtifactDiffDTO(
            artifact_type="metric",
            artifact_id=metric.metric_id,
            status="update",
            reason="overwrite_enabled",
        )

    def _classify_glossary(
        self,
        term: GlossaryTerm,
        *,
        overwrite: bool,
    ) -> SemanticSyncArtifactDiffDTO:
        existing = self._glossary.get(term.term_id)
        if existing is None:
            return SemanticSyncArtifactDiffDTO(
                artifact_type="glossary",
                artifact_id=term.term_id,
                status="add",
                reason="new_glossary_term",
            )
        if existing.model_dump(mode="json") == term.model_dump(mode="json"):
            return SemanticSyncArtifactDiffDTO(
                artifact_type="glossary",
                artifact_id=term.term_id,
                status="unchanged",
            )
        if not overwrite:
            return SemanticSyncArtifactDiffDTO(
                artifact_type="glossary",
                artifact_id=term.term_id,
                status="skipped",
                reason="existing_glossary_term_preserved",
            )
        return SemanticSyncArtifactDiffDTO(
            artifact_type="glossary",
            artifact_id=term.term_id,
            status="update",
            reason="overwrite_enabled",
        )

    def _classify_table(
        self,
        table: TableTrust,
        *,
        overwrite: bool,
        policy: SemanticSyncPolicy,
    ) -> SemanticSyncArtifactDiffDTO:
        if table.grade not in policy.allowed_grades:
            return SemanticSyncArtifactDiffDTO(
                artifact_type="table_trust",
                artifact_id=table.fqtn,
                status="skipped",
                reason=f"filtered_grade:{table.grade.value}",
            )

        existing = self._trust.get(table.fqtn)
        if existing is None:
            return SemanticSyncArtifactDiffDTO(
                artifact_type="table_trust",
                artifact_id=table.fqtn,
                status="add",
                reason="new_table_trust",
            )
        if existing.model_dump(mode="json") == table.model_dump(mode="json"):
            return SemanticSyncArtifactDiffDTO(
                artifact_type="table_trust",
                artifact_id=table.fqtn,
                status="unchanged",
            )
        if not overwrite:
            return SemanticSyncArtifactDiffDTO(
                artifact_type="table_trust",
                artifact_id=table.fqtn,
                status="skipped",
                reason="existing_table_trust_preserved",
            )
        return SemanticSyncArtifactDiffDTO(
            artifact_type="table_trust",
            artifact_id=table.fqtn,
            status="update",
            reason="overwrite_enabled",
        )

    def _classify_verified_query(
        self,
        query: VerifiedQuery,
        *,
        overwrite: bool,
    ) -> SemanticSyncArtifactDiffDTO:
        existing = self._verified_queries.get(query.vq_id)
        if existing is None:
            return SemanticSyncArtifactDiffDTO(
                artifact_type="verified_query",
                artifact_id=query.vq_id,
                status="add",
                reason="new_verified_query",
            )
        if existing.model_dump(mode="json") == query.model_dump(mode="json"):
            return SemanticSyncArtifactDiffDTO(
                artifact_type="verified_query",
                artifact_id=query.vq_id,
                status="unchanged",
            )
        if not overwrite:
            return SemanticSyncArtifactDiffDTO(
                artifact_type="verified_query",
                artifact_id=query.vq_id,
                status="skipped",
                reason="existing_verified_query_preserved",
            )
        return SemanticSyncArtifactDiffDTO(
            artifact_type="verified_query",
            artifact_id=query.vq_id,
            status="update",
            reason="overwrite_enabled",
        )

    def _apply_metric_namespace(self, metric: Metric, namespace: str | None) -> Metric:
        if not namespace:
            return metric
        return metric.model_copy(
            update={
                "metric_id": self._namespaced(metric.metric_id, namespace),
                "related_metrics": [
                    self._namespaced(metric_id, namespace) for metric_id in metric.related_metrics
                ],
                "verified_query_ids": [
                    self._namespaced(vq_id, namespace) for vq_id in metric.verified_query_ids
                ],
            }
        )

    def _apply_verified_query_namespace(
        self,
        query: VerifiedQuery,
        namespace: str | None,
    ) -> VerifiedQuery:
        if not namespace:
            return query
        update: dict[str, object] = {
            "vq_id": self._namespaced(query.vq_id, namespace),
        }
        if query.metric_id is not None:
            update["metric_id"] = self._namespaced(query.metric_id, namespace)
        return query.model_copy(update=update)

    def _apply_glossary_namespace(
        self,
        term: GlossaryTerm,
        namespace: str | None,
    ) -> GlossaryTerm:
        if not namespace:
            return term
        return term.model_copy(
            update={
                "linked_metric_ids": [
                    self._namespaced(metric_id, namespace) for metric_id in term.linked_metric_ids
                ]
            }
        )

    @staticmethod
    def _namespaced(value: str, namespace: str) -> str:
        return value if value.startswith(namespace) else f"{namespace}{value}"

    def _create_snapshot(
        self,
        *,
        source_name: str,
        note: str | None,
    ) -> str | None:
        if self._snapshots is None:
            return None
        now = self._clock.now() if self._clock is not None else datetime.now(UTC)
        snapshot_id = (
            self._ids.new_artifact_id("semantic_snapshot")
            if self._ids is not None
            else f"semantic_snapshot-{int(now.timestamp())}"
        )
        self._snapshots.create(
            snapshot_id=snapshot_id,
            source_name=source_name,
            created_at=now,
            note=note,
        )
        return snapshot_id
