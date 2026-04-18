"""DTOs for semantic-memory use cases."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.domain.proposal import SemanticProposal
from ds_agent.memory.semantic.domain.trust import TableTrust
from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery


class MetricMatchDTO(BaseModel):
    """A ranked metric match candidate."""

    metric: Metric
    score: float = Field(ge=0.0)
    match_kind: Literal["exact", "synonym", "fuzzy"]


class ResolveMetricResultDTO(BaseModel):
    """Ranked metric resolution result."""

    query: str
    kind: Literal["exact", "synonym", "fuzzy", "no_match"]
    matches: list[MetricMatchDTO] = Field(default_factory=list)

    @property
    def best_match(self) -> MetricMatchDTO | None:
        return self.matches[0] if self.matches else None


class VerifiedQueryResultDTO(BaseModel):
    """Resolved verified query and rendered SQL output."""

    query: VerifiedQuery | None = None
    rendered_sql: str | None = None
    bound_parameters: dict[str, str] = Field(default_factory=dict)


class TableTrustDecisionDTO(BaseModel):
    """Aggregate trust decision for one or more tables."""

    action: Literal["allow", "caveat", "confirm", "block"]
    tables: list[TableTrust] = Field(default_factory=list)
    missing_tables: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ProposalSubmissionResultDTO(BaseModel):
    """Result of creating or reusing a semantic proposal."""

    proposal: SemanticProposal
    created: bool
    deduplicated: bool = False


class LookupTermResultDTO(BaseModel):
    """Glossary lookup result."""

    query: str
    matches: list[GlossaryTerm] = Field(default_factory=list)


class ApplyProposalResultDTO(BaseModel):
    """Result of materializing a proposal into canonical semantic storage."""

    proposal: SemanticProposal
    applied_target: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticPackMetricDiffDTO(BaseModel):
    """One metric-level diff discovered during semantic pack loading."""

    metric_id: str
    status: Literal["add", "update", "unchanged", "conflict"]
    reason: str | None = None


class SemanticPackArtifactDiffDTO(BaseModel):
    """One non-metric semantic artifact diff discovered during pack loading."""

    artifact_type: Literal["metric", "glossary", "table_trust", "verified_query"]
    artifact_id: str
    status: Literal["add", "update", "unchanged", "conflict"]
    reason: str | None = None


class LoadSemanticPackResultDTO(BaseModel):
    """Result of loading or dry-running one semantic metric pack."""

    pack_dir: str
    pack_id: str | None = None
    display_name: str | None = None
    owner: str | None = None
    dry_run: bool
    snapshot_id: str | None = None
    metric_diffs: list[SemanticPackMetricDiffDTO] = Field(default_factory=list)
    glossary_diffs: list[SemanticPackArtifactDiffDTO] = Field(default_factory=list)
    trust_diffs: list[SemanticPackArtifactDiffDTO] = Field(default_factory=list)
    verified_query_diffs: list[SemanticPackArtifactDiffDTO] = Field(default_factory=list)
    artifact_diffs: list[SemanticPackArtifactDiffDTO] = Field(default_factory=list)
    applied_metric_ids: list[str] = Field(default_factory=list)
    applied_glossary_term_ids: list[str] = Field(default_factory=list)
    applied_table_ids: list[str] = Field(default_factory=list)
    applied_verified_query_ids: list[str] = Field(default_factory=list)


class SemanticSyncArtifactDiffDTO(BaseModel):
    """One external-sync diff for a semantic artifact."""

    artifact_type: Literal["metric", "glossary", "table_trust", "verified_query"]
    artifact_id: str
    status: Literal["add", "update", "unchanged", "skipped"]
    reason: str | None = None


class SyncSemanticSourceResultDTO(BaseModel):
    """Result of synchronizing one external semantic source."""

    source_name: str
    dry_run: bool
    since: datetime | None = None
    overwrite: bool
    id_namespace: str | None = None
    snapshot_id: str | None = None
    allowed_grades: list[str] = Field(default_factory=list)
    metric_diffs: list[SemanticSyncArtifactDiffDTO] = Field(default_factory=list)
    glossary_diffs: list[SemanticSyncArtifactDiffDTO] = Field(default_factory=list)
    trust_diffs: list[SemanticSyncArtifactDiffDTO] = Field(default_factory=list)
    verified_query_diffs: list[SemanticSyncArtifactDiffDTO] = Field(default_factory=list)
    applied_metric_ids: list[str] = Field(default_factory=list)
    applied_glossary_term_ids: list[str] = Field(default_factory=list)
    applied_table_ids: list[str] = Field(default_factory=list)
    applied_verified_query_ids: list[str] = Field(default_factory=list)


class SemanticSnapshotSummaryDTO(BaseModel):
    """Summary for one persisted semantic snapshot."""

    snapshot_id: str
    source_name: str
    created_at: datetime
    note: str | None = None
    table_counts: dict[str, int] = Field(default_factory=dict)
    total_rows: int = 0


class RestoreSemanticSnapshotResultDTO(BaseModel):
    """Result of restoring one semantic snapshot."""

    snapshot: SemanticSnapshotSummaryDTO
    restored_tables: list[str] = Field(default_factory=list)
    restored_rows: int = 0
