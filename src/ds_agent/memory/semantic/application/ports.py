"""Repository and adapter ports for semantic memory."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric, MetricGrain
from ds_agent.memory.semantic.domain.org_context import (
    CalendarEvent,
    DecisionLogEntry,
    NegativeKnowledge,
    TeamOwnership,
)
from ds_agent.memory.semantic.domain.proposal import SemanticProposal
from ds_agent.memory.semantic.domain.trust import TableTrust, TrustGrade
from ds_agent.memory.semantic.domain.verified_query import QueryDialect, VerifiedQuery


@runtime_checkable
class MetricRepository(Protocol):
    """Storage contract for semantic metric definitions."""

    def get(self, metric_id: str) -> Metric | None: ...

    def resolve(
        self,
        query: str,
        *,
        grain: MetricGrain | None = None,
        limit: int = 5,
    ) -> list[Metric]: ...

    def save(self, metric: Metric) -> None: ...


@runtime_checkable
class GlossaryRepository(Protocol):
    """Storage contract for glossary terms."""

    def get(self, term_id: str) -> GlossaryTerm | None: ...

    def lookup(self, query: str, *, limit: int = 5) -> list[GlossaryTerm]: ...

    def save(self, term: GlossaryTerm) -> None: ...


@runtime_checkable
class TableTrustRepository(Protocol):
    """Storage contract for data trust metadata."""

    def get(self, fqtn: str) -> TableTrust | None: ...

    def bulk_get(self, fqtns: Sequence[str]) -> list[TableTrust]: ...

    def save(self, table: TableTrust) -> None: ...


@runtime_checkable
class VerifiedQueryRepository(Protocol):
    """Storage contract for verified SQL templates."""

    def get(self, vq_id: str) -> VerifiedQuery | None: ...

    def find_by_metric(
        self,
        metric_id: str,
        *,
        dialect: QueryDialect | None = None,
    ) -> list[VerifiedQuery]: ...

    def save(self, query: VerifiedQuery) -> None: ...

    def append_audit(
        self,
        vq_id: str,
        *,
        verified_by: str,
        verification_evidence: str,
        verified_at: date,
    ) -> None: ...


@runtime_checkable
class OrgContextRepository(Protocol):
    """Storage contract for calendar, ownership, and negative knowledge."""

    def list_calendar_events(self, *, as_of: date | None = None) -> list[CalendarEvent]: ...

    def save_calendar_event(self, event: CalendarEvent) -> None: ...

    def get_team(self, team: str) -> TeamOwnership | None: ...

    def save_team(self, ownership: TeamOwnership) -> None: ...

    def list_negative_knowledge(self, topic: str) -> list[NegativeKnowledge]: ...

    def save_negative_knowledge(self, entry: NegativeKnowledge) -> None: ...

    def save_decision_log(self, entry: DecisionLogEntry) -> None: ...


@runtime_checkable
class SemanticProposalRepository(Protocol):
    """Storage contract for semantic write-back proposals."""

    def get(self, proposal_id: str) -> SemanticProposal | None: ...

    def list_pending(self, *, limit: int = 50) -> list[SemanticProposal]: ...

    def list_for_target(self, target_id: str) -> list[SemanticProposal]: ...

    def save(self, proposal: SemanticProposal) -> None: ...

    def update(self, proposal: SemanticProposal) -> None: ...


class SemanticSnapshotSummary(BaseModel):
    """Persisted semantic snapshot summary."""

    model_config = ConfigDict(frozen=True)

    snapshot_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    created_at: datetime
    note: str | None = None
    table_counts: dict[str, int] = Field(default_factory=dict)

    @property
    def total_rows(self) -> int:
        return sum(self.table_counts.values())


@runtime_checkable
class SemanticSnapshotRepository(Protocol):
    """Storage contract for semantic snapshot / rollback support."""

    def create(
        self,
        *,
        snapshot_id: str,
        source_name: str,
        created_at: datetime,
        note: str | None = None,
    ) -> SemanticSnapshotSummary: ...

    def get(self, snapshot_id: str) -> SemanticSnapshotSummary | None: ...

    def list(self, *, limit: int = 20) -> list[SemanticSnapshotSummary]: ...

    def restore(self, snapshot_id: str) -> SemanticSnapshotSummary | None: ...


@runtime_checkable
class ExternalSemanticSource(Protocol):
    """Adapter port for external semantic systems such as dbt or Looker."""

    name: str

    def fetch_metrics(self, since: datetime | None) -> list[Metric]: ...

    def fetch_glossary_terms(self, since: datetime | None) -> list[GlossaryTerm]: ...

    def fetch_tables(self, since: datetime | None) -> list[TableTrust]: ...

    def fetch_verified_queries(self, since: datetime | None) -> list[VerifiedQuery]: ...


class SemanticSyncPolicy(BaseModel):
    """Policy controlling merge behavior for external syncs."""

    model_config = ConfigDict(frozen=True)

    source_name: str = Field(min_length=1)
    overwrite: bool = False
    id_namespace: str | None = None
    allowed_grades: list[TrustGrade] = Field(
        default_factory=lambda: [TrustGrade.GOLD, TrustGrade.SILVER]
    )


@dataclass(frozen=True)
class LoadedMetricPack:
    """One loaded metric pack with metadata and typed artifacts."""

    pack_dir: Path
    pack_metadata: dict[str, Any]
    metrics: list[Metric]
    glossary_terms: list[GlossaryTerm]
    table_trust: list[TableTrust]
    verified_queries: list[VerifiedQuery]


@runtime_checkable
class MetricPackLoader(Protocol):
    """Port for loading semantic metric packs from a directory."""

    def load_pack(self, pack_dir: str | Path) -> LoadedMetricPack: ...
