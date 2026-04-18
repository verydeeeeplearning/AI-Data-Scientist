from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

from ds_agent.memory.semantic.application.apply_semantic_proposal import (
    ApplySemanticProposalUseCase,
)
from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric, MetricGrain
from ds_agent.memory.semantic.domain.proposal import (
    SemanticProposal,
    SemanticProposalStatus,
    SemanticProposalType,
)
from ds_agent.memory.semantic.domain.verified_query import QueryDialect


class _ProposalRepo:
    def __init__(self, proposal: SemanticProposal) -> None:
        self.item = proposal

    def get(self, proposal_id: str) -> SemanticProposal | None:
        return self.item if self.item.proposal_id == proposal_id else None

    def list_pending(self, *, limit: int = 50) -> list[SemanticProposal]:
        return [self.item]

    def list_for_target(self, target_id: str) -> list[SemanticProposal]:
        return [self.item] if self.item.target_id == target_id else []

    def save(self, proposal: SemanticProposal) -> None:
        self.item = proposal

    def update(self, proposal: SemanticProposal) -> None:
        self.item = proposal


class _MetricRepo:
    def __init__(self) -> None:
        self.metric = Metric(
            metric_id="monthly_churn_rate",
            display_name="Monthly Churn Rate",
            owner="growth_team",
            definition="Customer churn rate",
            synonyms=["churn"],
            grain="monthly",
            unit="ratio",
            direction="lower_is_better",
            calculation={
                "numerator": {
                    "source": "prod.metric",
                    "filter": "x = 1",
                    "aggregation": "COUNT(*)",
                }
            },
        )

    def get(self, metric_id: str) -> Metric | None:
        return self.metric if self.metric.metric_id == metric_id else None

    def resolve(
        self,
        query: str,
        *,
        grain: MetricGrain | None = None,
        limit: int = 5,
    ) -> list[Metric]:
        return [self.metric]

    def save(self, metric: Metric) -> None:
        self.metric = metric


class _GlossaryRepo:
    def __init__(self) -> None:
        self.saved: GlossaryTerm | None = None

    def get(self, term_id: str) -> GlossaryTerm | None:
        if self.saved is None or self.saved.term_id != term_id:
            return None
        return self.saved

    def lookup(self, query: str, *, limit: int = 5) -> list[GlossaryTerm]:
        return [self.saved] if self.saved is not None else []

    def save(self, term: GlossaryTerm) -> None:
        self.saved = term


class _TrustRepo:
    def get(self, fqtn: str):
        return None

    def bulk_get(self, fqtns: Sequence[str]):
        return []

    def save(self, table) -> None:
        self.saved = table


class _VerifiedQueryRepo:
    def get(self, vq_id: str):
        return None

    def find_by_metric(self, metric_id: str, *, dialect: QueryDialect | None = None):
        return []

    def save(self, query) -> None:
        self.saved = query

    def append_audit(
        self,
        vq_id: str,
        *,
        verified_by: str,
        verification_evidence: str,
        verified_at: date,
    ) -> None:
        self.audit = (vq_id, verified_by, verification_evidence, verified_at)


class _OrgRepo:
    def list_calendar_events(self, *, as_of=None):
        return []

    def save_calendar_event(self, event) -> None:
        self.event = event

    def get_team(self, team: str):
        return None

    def save_team(self, ownership) -> None:
        self.team = ownership

    def list_negative_knowledge(self, topic: str):
        return []

    def save_negative_knowledge(self, entry) -> None:
        self.entry = entry

    def save_decision_log(self, entry) -> None:
        self.decision = entry


@dataclass
class _Clock:
    now_value: datetime = datetime(2026, 4, 16, tzinfo=UTC)

    def now(self) -> datetime:
        return self.now_value


def test_apply_semantic_proposal_applies_metric_alias() -> None:
    proposal = SemanticProposal(
        proposal_id="SP-1",
        proposal_type=SemanticProposalType.METRIC_ALIAS,
        status=SemanticProposalStatus.APPROVED,
        summary="Add alias",
        target_id="monthly_churn_rate",
        payload={
            "metric_id": "monthly_churn_rate",
            "alias": "customer churn",
        },
        created_at=datetime(2026, 4, 16, tzinfo=UTC),
        reviewed_by="reviewer@corp.example",
        reviewed_at=datetime(2026, 4, 16, tzinfo=UTC),
    )
    proposals = _ProposalRepo(proposal)
    metrics = _MetricRepo()

    result = ApplySemanticProposalUseCase(
        proposals,
        metrics,
        _GlossaryRepo(),
        _TrustRepo(),
        _VerifiedQueryRepo(),
        _OrgRepo(),
        _Clock(),
    ).execute("SP-1", reviewer="operator@corp.example")

    assert result.proposal.status is SemanticProposalStatus.APPLIED
    assert "customer churn" in metrics.metric.synonyms
