"""Use case for loading semantic packs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from ds_agent.application.ports.task_contract_support import Clock, IdGenerator
from ds_agent.memory.semantic.application.dtos import (
    LoadSemanticPackResultDTO,
    SemanticPackArtifactDiffDTO,
    SemanticPackMetricDiffDTO,
)
from ds_agent.memory.semantic.application.ports import (
    GlossaryRepository,
    LoadedMetricPack,
    MetricPackLoader,
    MetricRepository,
    SemanticSnapshotRepository,
    TableTrustRepository,
    VerifiedQueryRepository,
)
from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.domain.trust import TableTrust
from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery

SemanticArtifact = Metric | GlossaryTerm | TableTrust | VerifiedQuery
ArtifactType = Literal["metric", "glossary", "table_trust", "verified_query"]


class LoadSemanticPackUseCase:
    """Load one semantic pack with dry-run diff support."""

    def __init__(
        self,
        metrics: MetricRepository,
        glossary: GlossaryRepository,
        trust: TableTrustRepository,
        verified_queries: VerifiedQueryRepository,
        loader: MetricPackLoader,
        snapshots: SemanticSnapshotRepository | None = None,
        clock: Clock | None = None,
        ids: IdGenerator | None = None,
    ) -> None:
        self._metrics = metrics
        self._glossary = glossary
        self._trust = trust
        self._verified_queries = verified_queries
        self._loader = loader
        self._snapshots = snapshots
        self._clock = clock
        self._ids = ids

    def execute(
        self,
        pack_dir: str,
        *,
        dry_run: bool = True,
        allow_definition_updates: bool = False,
    ) -> LoadSemanticPackResultDTO:
        loaded = self._loader.load_pack(pack_dir)
        self._validate_pack_references(loaded)

        metric_diffs: list[SemanticPackMetricDiffDTO] = []
        glossary_diffs: list[SemanticPackArtifactDiffDTO] = []
        trust_diffs: list[SemanticPackArtifactDiffDTO] = []
        verified_query_diffs: list[SemanticPackArtifactDiffDTO] = []
        artifact_diffs: list[SemanticPackArtifactDiffDTO] = []
        metrics_to_apply: list[Metric] = []
        glossary_to_apply: list[GlossaryTerm] = []
        trust_to_apply: list[TableTrust] = []
        verified_queries_to_apply: list[VerifiedQuery] = []
        conflicts: list[str] = []

        for metric in loaded.metrics:
            metric_diff = self._classify_metric(
                metric,
                allow_definition_updates=allow_definition_updates,
            )
            metric_diffs.append(metric_diff)
            artifact_diffs.append(
                SemanticPackArtifactDiffDTO(
                    artifact_type="metric",
                    artifact_id=metric.metric_id,
                    status=metric_diff.status,
                    reason=metric_diff.reason,
                )
            )
            if metric_diff.status in {"add", "update"}:
                metrics_to_apply.append(metric)
            if metric_diff.status == "conflict":
                conflicts.append(f"metric:{metric.metric_id}")

        for term in loaded.glossary_terms:
            glossary_diff = self._classify_glossary(
                term,
                allow_definition_updates=allow_definition_updates,
            )
            glossary_diffs.append(glossary_diff)
            artifact_diffs.append(glossary_diff)
            if glossary_diff.status in {"add", "update"}:
                glossary_to_apply.append(term)
            if glossary_diff.status == "conflict":
                conflicts.append(f"glossary:{term.term_id}")

        for table in loaded.table_trust:
            trust_diff = self._classify_table_trust(
                table,
                allow_definition_updates=allow_definition_updates,
            )
            trust_diffs.append(trust_diff)
            artifact_diffs.append(trust_diff)
            if trust_diff.status in {"add", "update"}:
                trust_to_apply.append(table)
            if trust_diff.status == "conflict":
                conflicts.append(f"table_trust:{table.fqtn}")

        for query in loaded.verified_queries:
            verified_query_diff = self._classify_verified_query(
                query,
                allow_definition_updates=allow_definition_updates,
            )
            verified_query_diffs.append(verified_query_diff)
            artifact_diffs.append(verified_query_diff)
            if verified_query_diff.status in {"add", "update"}:
                verified_queries_to_apply.append(query)
            if verified_query_diff.status == "conflict":
                conflicts.append(f"verified_query:{query.vq_id}")

        if not dry_run and conflicts:
            raise ValueError(
                "semantic pack apply blocked by conflicting artifact definitions: "
                + ", ".join(conflicts)
            )

        metadata = loaded.pack_metadata
        applied_metric_ids: list[str] = []
        applied_glossary_term_ids: list[str] = []
        applied_table_ids: list[str] = []
        applied_verified_query_ids: list[str] = []
        snapshot_id: str | None = None
        if not dry_run:
            if metrics_to_apply or glossary_to_apply or trust_to_apply or verified_queries_to_apply:
                snapshot_id = self._create_snapshot(
                    source_name=f"pack:{metadata.get('pack_id') or loaded.pack_dir.name}",
                    note=f"Before applying semantic pack {loaded.pack_dir}",
                )
            for metric in metrics_to_apply:
                self._metrics.save(metric)
                applied_metric_ids.append(metric.metric_id)
            for term in glossary_to_apply:
                self._glossary.save(term)
                applied_glossary_term_ids.append(term.term_id)
            for table in trust_to_apply:
                self._trust.save(table)
                applied_table_ids.append(table.fqtn)
            for query in verified_queries_to_apply:
                self._verified_queries.save(query)
                applied_verified_query_ids.append(query.vq_id)

        return LoadSemanticPackResultDTO(
            pack_dir=str(loaded.pack_dir),
            pack_id=str(metadata.get("pack_id")) if metadata.get("pack_id") is not None else None,
            display_name=(
                str(metadata.get("display_name"))
                if metadata.get("display_name") is not None
                else None
            ),
            owner=str(metadata.get("owner")) if metadata.get("owner") is not None else None,
            dry_run=dry_run,
            snapshot_id=snapshot_id,
            metric_diffs=metric_diffs,
            glossary_diffs=glossary_diffs,
            trust_diffs=trust_diffs,
            verified_query_diffs=verified_query_diffs,
            artifact_diffs=artifact_diffs,
            applied_metric_ids=applied_metric_ids,
            applied_glossary_term_ids=applied_glossary_term_ids,
            applied_table_ids=applied_table_ids,
            applied_verified_query_ids=applied_verified_query_ids,
        )

    def _validate_pack_references(self, loaded: LoadedMetricPack) -> None:
        metric_ids = {metric.metric_id for metric in loaded.metrics}
        verified_query_ids = {query.vq_id for query in loaded.verified_queries}

        for term in loaded.glossary_terms:
            for metric_id in term.linked_metric_ids:
                if metric_id not in metric_ids and self._metrics.get(metric_id) is None:
                    raise ValueError(
                        f"glossary term '{term.term_id}' references unknown metric_id '{metric_id}'"
                    )

        for metric in loaded.metrics:
            for vq_id in metric.verified_query_ids:
                if vq_id not in verified_query_ids and self._verified_queries.get(vq_id) is None:
                    raise ValueError(
                        "metric "
                        f"'{metric.metric_id}' references unknown verified_query_id '{vq_id}'"
                    )

        for query in loaded.verified_queries:
            if query.metric_id is None:
                continue
            if query.metric_id not in metric_ids and self._metrics.get(query.metric_id) is None:
                raise ValueError(
                    "verified query "
                    f"'{query.vq_id}' references unknown metric_id '{query.metric_id}'"
                )

    def _classify_metric(
        self,
        metric: Metric,
        *,
        allow_definition_updates: bool,
    ) -> SemanticPackMetricDiffDTO:
        existing = self._metrics.get(metric.metric_id)
        if existing is None:
            return SemanticPackMetricDiffDTO(
                metric_id=metric.metric_id,
                status="add",
                reason="new_metric",
            )

        incoming = metric.model_dump(mode="json")
        current = existing.model_dump(mode="json")
        if current == incoming:
            return SemanticPackMetricDiffDTO(metric_id=metric.metric_id, status="unchanged")

        changed_core_fields = [
            field
            for field in ["definition", "grain", "unit", "direction", "calculation"]
            if current.get(field) != incoming.get(field)
        ]
        if changed_core_fields and not allow_definition_updates:
            return SemanticPackMetricDiffDTO(
                metric_id=metric.metric_id,
                status="conflict",
                reason=f"core_fields_changed:{','.join(changed_core_fields)}",
            )

        return SemanticPackMetricDiffDTO(
            metric_id=metric.metric_id,
            status="update",
            reason="metadata_changed" if not changed_core_fields else "core_fields_updated",
        )

    def _classify_glossary(
        self,
        term: GlossaryTerm,
        *,
        allow_definition_updates: bool,
    ) -> SemanticPackArtifactDiffDTO:
        existing = self._glossary.get(term.term_id)
        return self._classify_artifact(
            artifact_type="glossary",
            artifact_id=term.term_id,
            existing=existing,
            incoming=term,
            core_fields=["canonical_form", "definition", "category", "linked_metric_ids"],
            allow_definition_updates=allow_definition_updates,
            add_reason="new_term",
        )

    def _classify_table_trust(
        self,
        table: TableTrust,
        *,
        allow_definition_updates: bool,
    ) -> SemanticPackArtifactDiffDTO:
        existing = self._trust.get(table.fqtn)
        return self._classify_artifact(
            artifact_type="table_trust",
            artifact_id=table.fqtn,
            existing=existing,
            incoming=table,
            core_fields=["grade", "refresh", "approved_joins", "columns", "grade_rationale"],
            allow_definition_updates=allow_definition_updates,
            add_reason="new_table_trust",
        )

    def _classify_verified_query(
        self,
        query: VerifiedQuery,
        *,
        allow_definition_updates: bool,
    ) -> SemanticPackArtifactDiffDTO:
        existing = self._verified_queries.get(query.vq_id)
        return self._classify_artifact(
            artifact_type="verified_query",
            artifact_id=query.vq_id,
            existing=existing,
            incoming=query,
            core_fields=["metric_id", "dialect", "sql_template", "parameters", "referenced_tables"],
            allow_definition_updates=allow_definition_updates,
            add_reason="new_verified_query",
        )

    def _classify_artifact(
        self,
        *,
        artifact_type: ArtifactType,
        artifact_id: str,
        existing: SemanticArtifact | None,
        incoming: SemanticArtifact,
        core_fields: list[str],
        allow_definition_updates: bool,
        add_reason: str,
    ) -> SemanticPackArtifactDiffDTO:
        if existing is None:
            return SemanticPackArtifactDiffDTO(
                artifact_type=artifact_type,
                artifact_id=artifact_id,
                status="add",
                reason=add_reason,
            )

        current_payload = existing.model_dump(mode="json")
        incoming_payload = incoming.model_dump(mode="json")
        if current_payload == incoming_payload:
            return SemanticPackArtifactDiffDTO(
                artifact_type=artifact_type,
                artifact_id=artifact_id,
                status="unchanged",
            )

        changed_core_fields = [
            field
            for field in core_fields
            if current_payload.get(field) != incoming_payload.get(field)
        ]
        if changed_core_fields and not allow_definition_updates:
            return SemanticPackArtifactDiffDTO(
                artifact_type=artifact_type,
                artifact_id=artifact_id,
                status="conflict",
                reason=f"core_fields_changed:{','.join(changed_core_fields)}",
            )

        return SemanticPackArtifactDiffDTO(
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            status="update",
            reason="metadata_changed" if not changed_core_fields else "core_fields_updated",
        )

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
