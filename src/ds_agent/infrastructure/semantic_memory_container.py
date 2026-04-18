"""Composition root for semantic-memory services."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ds_agent.application.ports.task_contract_support import Clock, IdGenerator
from ds_agent.infrastructure.semantic_memory_paths import resolve_semantic_db_path
from ds_agent.memory.semantic.application.apply_semantic_proposal import (
    ApplySemanticProposalUseCase,
)
from ds_agent.memory.semantic.application.check_table_trust import CheckTableTrustUseCase
from ds_agent.memory.semantic.application.find_verified_query import (
    FindVerifiedQueryUseCase,
)
from ds_agent.memory.semantic.application.list_semantic_snapshots import (
    ListSemanticSnapshotsUseCase,
)
from ds_agent.memory.semantic.application.load_semantic_pack import (
    LoadSemanticPackUseCase,
)
from ds_agent.memory.semantic.application.lookup_term import LookupTermUseCase
from ds_agent.memory.semantic.application.record_negative_knowledge import (
    RecordNegativeKnowledgeUseCase,
)
from ds_agent.memory.semantic.application.resolve_metric import ResolveMetricUseCase
from ds_agent.memory.semantic.application.restore_semantic_snapshot import (
    RestoreSemanticSnapshotUseCase,
)
from ds_agent.memory.semantic.application.review_semantic_proposal import (
    ReviewSemanticProposalUseCase,
)
from ds_agent.memory.semantic.application.submit_semantic_proposal import (
    SubmitSemanticProposalUseCase,
)
from ds_agent.memory.semantic.application.sync_semantic_source import (
    SyncSemanticSourceUseCase,
)
from ds_agent.memory.semantic.infrastructure import (
    SemanticSqliteDatabase,
    SqliteGlossaryRepository,
    SqliteMetricRepository,
    SqliteOrgContextRepository,
    SqliteSemanticProposalRepository,
    SqliteSemanticSnapshotRepository,
    SqliteTableTrustRepository,
    SqliteVerifiedQueryRepository,
    YamlMetricLoader,
)


class SystemClock(Clock):
    """Production clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class TimestampArtifactIdGenerator(IdGenerator):
    """Artifact ID generator compatible with task-contract support port."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counter = 0

    def new_task_id(self, now: datetime) -> str:
        with self._lock:
            self._counter += 1
            return f"TC-{now.year}-{int(now.timestamp())}{self._counter:03d}"

    def new_artifact_id(self, prefix: str) -> str:
        with self._lock:
            self._counter += 1
            return f"{prefix}-{time.time_ns() + self._counter}"


@dataclass(frozen=True)
class SemanticMemoryContainer:
    """Wired semantic-memory repositories and use cases."""

    db: SemanticSqliteDatabase
    clock: Clock
    ids: IdGenerator
    metrics: SqliteMetricRepository
    glossary: SqliteGlossaryRepository
    trust: SqliteTableTrustRepository
    verified_queries: SqliteVerifiedQueryRepository
    org_context: SqliteOrgContextRepository
    proposals: SqliteSemanticProposalRepository
    snapshots: SqliteSemanticSnapshotRepository
    resolve_metric: ResolveMetricUseCase
    lookup_term: LookupTermUseCase
    check_table_trust: CheckTableTrustUseCase
    find_verified_query: FindVerifiedQueryUseCase
    submit_semantic_proposal: SubmitSemanticProposalUseCase
    review_semantic_proposal: ReviewSemanticProposalUseCase
    apply_semantic_proposal: ApplySemanticProposalUseCase
    record_negative_knowledge: RecordNegativeKnowledgeUseCase
    load_semantic_pack: LoadSemanticPackUseCase
    sync_semantic_source: SyncSemanticSourceUseCase
    list_semantic_snapshots: ListSemanticSnapshotsUseCase
    restore_semantic_snapshot: RestoreSemanticSnapshotUseCase


def build_semantic_memory_container(
    workspace_dir: str | None = None,
    *,
    db_path: str | None = None,
) -> SemanticMemoryContainer:
    """Build the semantic-memory container for one workspace."""

    resolved_path = Path(db_path) if db_path is not None else _default_db_path(workspace_dir)
    db = SemanticSqliteDatabase(resolved_path)
    clock = SystemClock()
    ids = TimestampArtifactIdGenerator()
    metrics = SqliteMetricRepository(db)
    glossary = SqliteGlossaryRepository(db)
    trust = SqliteTableTrustRepository(db)
    verified_queries = SqliteVerifiedQueryRepository(db)
    org_context = SqliteOrgContextRepository(db)
    proposals = SqliteSemanticProposalRepository(db)
    snapshots = SqliteSemanticSnapshotRepository(db)
    submit = SubmitSemanticProposalUseCase(proposals, clock, ids)
    metric_loader = YamlMetricLoader()
    return SemanticMemoryContainer(
        db=db,
        clock=clock,
        ids=ids,
        metrics=metrics,
        glossary=glossary,
        trust=trust,
        verified_queries=verified_queries,
        org_context=org_context,
        proposals=proposals,
        snapshots=snapshots,
        resolve_metric=ResolveMetricUseCase(metrics),
        lookup_term=LookupTermUseCase(glossary),
        check_table_trust=CheckTableTrustUseCase(trust),
        find_verified_query=FindVerifiedQueryUseCase(verified_queries),
        submit_semantic_proposal=submit,
        review_semantic_proposal=ReviewSemanticProposalUseCase(proposals, clock),
        apply_semantic_proposal=ApplySemanticProposalUseCase(
            proposals,
            metrics,
            glossary,
            trust,
            verified_queries,
            org_context,
            clock,
        ),
        record_negative_knowledge=RecordNegativeKnowledgeUseCase(submit, clock),
        load_semantic_pack=LoadSemanticPackUseCase(
            metrics,
            glossary,
            trust,
            verified_queries,
            metric_loader,
            snapshots,
            clock,
            ids,
        ),
        sync_semantic_source=SyncSemanticSourceUseCase(
            metrics,
            glossary,
            trust,
            verified_queries,
            snapshots,
            clock,
            ids,
        ),
        list_semantic_snapshots=ListSemanticSnapshotsUseCase(snapshots),
        restore_semantic_snapshot=RestoreSemanticSnapshotUseCase(snapshots),
    )


def _default_db_path(workspace_dir: str | None) -> Path:
    return resolve_semantic_db_path(workspace_dir)
