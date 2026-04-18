"""Use case for applying reviewed semantic proposals."""

from __future__ import annotations

from ds_agent.application.ports.task_contract_support import Clock
from ds_agent.memory.semantic.application.dtos import ApplyProposalResultDTO
from ds_agent.memory.semantic.application.ports import (
    GlossaryRepository,
    MetricRepository,
    OrgContextRepository,
    SemanticProposalRepository,
    TableTrustRepository,
    VerifiedQueryRepository,
)
from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.domain.org_context import NegativeKnowledge
from ds_agent.memory.semantic.domain.proposal import SemanticProposalStatus, SemanticProposalType
from ds_agent.memory.semantic.domain.trust import TableTrust
from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery


class ApplySemanticProposalUseCase:
    """Materialize approved or auto-applicable proposals into canonical storage."""

    def __init__(
        self,
        proposals: SemanticProposalRepository,
        metrics: MetricRepository,
        glossary: GlossaryRepository,
        trust: TableTrustRepository,
        verified_queries: VerifiedQueryRepository,
        org_context: OrgContextRepository,
        clock: Clock,
    ) -> None:
        self._proposals = proposals
        self._metrics = metrics
        self._glossary = glossary
        self._trust = trust
        self._verified_queries = verified_queries
        self._org_context = org_context
        self._clock = clock

    def execute(self, proposal_id: str, *, reviewer: str) -> ApplyProposalResultDTO:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"proposal not found: {proposal_id}")
        if (
            proposal.status != SemanticProposalStatus.APPROVED
            and not proposal.auto_apply_eligible
        ):
            raise ValueError("proposal must be approved or auto-apply eligible before apply")

        applied_target: str | None = None
        match proposal.proposal_type:
            case SemanticProposalType.NEGATIVE_KNOWLEDGE:
                entry = NegativeKnowledge.model_validate(proposal.payload)
                self._org_context.save_negative_knowledge(entry)
                applied_target = entry.nk_id
            case SemanticProposalType.VERIFIED_QUERY:
                query = VerifiedQuery.model_validate(proposal.payload)
                self._verified_queries.save(query)
                applied_target = query.vq_id
            case SemanticProposalType.GLOSSARY_TERM:
                term = GlossaryTerm.model_validate(proposal.payload)
                self._glossary.save(term)
                applied_target = term.term_id
            case SemanticProposalType.TABLE_TRUST_PATCH:
                table = TableTrust.model_validate(proposal.payload)
                self._trust.save(table)
                applied_target = table.fqtn
            case SemanticProposalType.METRIC_ALIAS:
                metric_id = str(proposal.payload["metric_id"])
                alias = str(proposal.payload["alias"])
                metric = self._metrics.get(metric_id)
                if metric is None:
                    raise ValueError(f"metric not found: {metric_id}")
                synonyms = [*metric.synonyms, alias]
                updated_metric = Metric.model_validate(
                    metric.model_copy(update={"synonyms": synonyms}).model_dump(mode="python")
                )
                self._metrics.save(updated_metric)
                applied_target = updated_metric.metric_id
            case SemanticProposalType.METRIC_REVIEW_REQUEST:
                raise ValueError(
                    "metric_review_request proposals require human workflow, "
                    "not auto-apply"
                )

        applied = proposal.transition_to(
            SemanticProposalStatus.APPLIED,
            reviewed_by=reviewer,
            reviewed_at=self._clock.now(),
        )
        self._proposals.update(applied)
        return ApplyProposalResultDTO(
            proposal=applied,
            applied_target=applied_target,
        )
