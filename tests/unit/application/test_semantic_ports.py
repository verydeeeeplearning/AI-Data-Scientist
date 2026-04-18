from __future__ import annotations

from datetime import UTC, date, datetime

from ds_agent.memory.semantic.application.ports import (
    ExternalSemanticSource,
    GlossaryRepository,
    MetricRepository,
    OrgContextRepository,
    SemanticProposalRepository,
    SemanticSyncPolicy,
    TableTrustRepository,
    VerifiedQueryRepository,
)
from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.domain.org_context import (
    CalendarEvent,
    DecisionLogEntry,
    NegativeKnowledge,
    TeamOwnership,
)
from ds_agent.memory.semantic.domain.proposal import SemanticProposal, SemanticProposalType
from ds_agent.memory.semantic.domain.trust import RefreshSLA, TableTrust, TrustGrade
from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery


def _metric() -> Metric:
    return Metric(
        metric_id="monthly_churn_rate",
        display_name="월간 이탈률",
        owner="growth_team",
        definition="당월 해지자 / 전월 말 활성 구독자",
        grain="monthly",
        unit="ratio",
        direction="lower_is_better",
        calculation={
            "numerator": {
                "source": "prod.growth.subscription",
                "filter": "event_type = 'cancel'",
                "aggregation": "COUNT(DISTINCT user_id)",
            }
        },
    )


def _glossary() -> GlossaryTerm:
    return GlossaryTerm(
        term_id="term.mau",
        canonical_form="MAU",
        definition="월간 활성 유저",
        category="metric",
    )


def _table() -> TableTrust:
    return TableTrust(
        fqtn="prod.growth.subscription",
        grade=TrustGrade.SILVER,
        owner="growth_team",
        description="subscription fact",
        refresh=RefreshSLA(cadence="daily", max_staleness_minutes=1440),
        grade_rationale="audited monthly",
        last_audited=date(2026, 4, 1),
    )


def _verified_query() -> VerifiedQuery:
    return VerifiedQuery(
        vq_id="vq_churn_001",
        metric_id="monthly_churn_rate",
        dialect="postgres",
        description="Monthly churn",
        sql_template="SELECT {{start_date}}",
        parameters=[{"name": "start_date", "type": "date", "description": "inclusive start"}],
        referenced_tables=["prod.growth.subscription"],
        verified_by="reviewer",
        last_verified=date(2026, 4, 15),
        verification_evidence="Dashboard parity",
    )


class _MetricRepo:
    def get(self, metric_id: str) -> Metric | None:
        return _metric()

    def resolve(self, query: str, *, grain: str | None = None, limit: int = 5) -> list[Metric]:
        return [_metric()]

    def save(self, metric: Metric) -> None:
        self.saved = metric


class _GlossaryRepo:
    def get(self, term_id: str) -> GlossaryTerm | None:
        return _glossary()

    def lookup(self, query: str, *, limit: int = 5) -> list[GlossaryTerm]:
        return [_glossary()]

    def save(self, term: GlossaryTerm) -> None:
        self.saved = term


class _TableRepo:
    def get(self, fqtn: str) -> TableTrust | None:
        return _table()

    def bulk_get(self, fqtns: list[str]) -> list[TableTrust]:
        return [_table()]

    def save(self, table: TableTrust) -> None:
        self.saved = table


class _VerifiedQueryRepo:
    def get(self, vq_id: str) -> VerifiedQuery | None:
        return _verified_query()

    def find_by_metric(self, metric_id: str, *, dialect: str | None = None) -> list[VerifiedQuery]:
        return [_verified_query()]

    def save(self, query: VerifiedQuery) -> None:
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


class _OrgContextRepo:
    def list_calendar_events(self, *, as_of: date | None = None) -> list[CalendarEvent]:
        return [
            CalendarEvent(
                event_id="freeze.q2",
                type="freeze",
                name="Quarter close",
                start_date=date(2026, 4, 10),
                end_date=date(2026, 4, 12),
                description="No schema changes",
            )
        ]

    def save_calendar_event(self, event: CalendarEvent) -> None:
        self.event = event

    def get_team(self, team: str) -> TeamOwnership | None:
        return TeamOwnership(team=team, contact="owner@corp.example")

    def save_team(self, ownership: TeamOwnership) -> None:
        self.team = ownership

    def list_negative_knowledge(self, topic: str) -> list[NegativeKnowledge]:
        return [
            NegativeKnowledge(
                nk_id="nk-1",
                topic=topic,
                wrong_approach="promo users 포함",
                why_wrong="biases result",
                correct_approach="promo users 제외",
                recorded_at=datetime(2026, 4, 16, tzinfo=UTC),
                recorded_by="human",
            )
        ]

    def save_negative_knowledge(self, entry: NegativeKnowledge) -> None:
        self.nk = entry

    def save_decision_log(self, entry: DecisionLogEntry) -> None:
        self.decision = entry


class _ProposalRepo:
    def get(self, proposal_id: str) -> SemanticProposal | None:
        return SemanticProposal(
            proposal_id=proposal_id,
            proposal_type=SemanticProposalType.GLOSSARY_TERM,
            summary="Add MAU alias",
            created_at=datetime(2026, 4, 16, tzinfo=UTC),
        )

    def list_pending(self, *, limit: int = 50) -> list[SemanticProposal]:
        proposal = self.get("proposal-1")
        assert proposal is not None
        return [proposal]

    def list_for_target(self, target_id: str) -> list[SemanticProposal]:
        return self.list_pending()

    def save(self, proposal: SemanticProposal) -> None:
        self.saved = proposal

    def update(self, proposal: SemanticProposal) -> None:
        self.updated = proposal


class _ExternalSource:
    name = "dbt"

    def fetch_metrics(self, since: datetime | None) -> list[Metric]:
        return [_metric()]

    def fetch_glossary_terms(self, since: datetime | None) -> list[GlossaryTerm]:
        return [_glossary()]

    def fetch_tables(self, since: datetime | None) -> list[TableTrust]:
        return [_table()]

    def fetch_verified_queries(self, since: datetime | None) -> list[VerifiedQuery]:
        return [_verified_query()]


def test_semantic_ports_are_runtime_checkable() -> None:
    assert isinstance(_MetricRepo(), MetricRepository)
    assert isinstance(_GlossaryRepo(), GlossaryRepository)
    assert isinstance(_TableRepo(), TableTrustRepository)
    assert isinstance(_VerifiedQueryRepo(), VerifiedQueryRepository)
    assert isinstance(_OrgContextRepo(), OrgContextRepository)
    assert isinstance(_ProposalRepo(), SemanticProposalRepository)
    assert isinstance(_ExternalSource(), ExternalSemanticSource)


def test_semantic_sync_policy_defaults_to_gold_and_silver() -> None:
    policy = SemanticSyncPolicy(source_name="dbt")

    assert policy.allowed_grades == [TrustGrade.GOLD, TrustGrade.SILVER]
