"""Composition root for verifier orchestration services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ds_agent.agent.confidence_scorer import ConfidenceScorer
from ds_agent.application.ports.task_contract_support import Clock
from ds_agent.application.services.verifier_orchestrator import VerifierOrchestrator
from ds_agent.application.services.verifier_shadow_comparator import LegacyHookShadowComparator
from ds_agent.domain.interfaces.llm_provider import LLMProvider
from ds_agent.domain.interfaces.verifier_ports import (
    LLMJudgePort,
    ShadowComparatorPort,
    ShadowComparisonRepository,
    VerdictRepository,
)
from ds_agent.infrastructure.persistence.shadow_comparison_repo import (
    SqliteShadowComparisonRepository,
)
from ds_agent.infrastructure.persistence.verdict_repo import SqliteVerdictRepository


class SystemClock(Clock):
    """Production clock for verifier orchestration."""

    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True)
class VerifierContainer:
    """Wired verifier subsystem for one workspace."""

    repo: VerdictRepository
    shadow_repo: ShadowComparisonRepository
    orchestrator: VerifierOrchestrator


def build_verifier_container(
    workspace_dir: str | None = None,
    *,
    repo: VerdictRepository | None = None,
    shadow_repo: ShadowComparisonRepository | None = None,
    llm_provider: LLMProvider | None = None,
    narrative_judge: LLMJudgePort | None = None,
    shadow_comparator: ShadowComparatorPort | None = None,
) -> VerifierContainer:
    """Build a fully wired verifier container."""

    from ds_agent.infrastructure.verifiers.data import DataVerifier
    from ds_agent.infrastructure.verifiers.llm_judge_adapter import LLMNarrativeJudge
    from ds_agent.infrastructure.verifiers.narrative import NarrativeVerifier
    from ds_agent.infrastructure.verifiers.policy import PolicyVerifier
    from ds_agent.infrastructure.verifiers.statistical import StatisticalVerifier

    resolved_repo = repo or SqliteVerdictRepository.for_workspace(workspace_dir)
    resolved_shadow_repo = shadow_repo or SqliteShadowComparisonRepository.for_workspace(
        workspace_dir
    )
    resolved_judge = narrative_judge
    if resolved_judge is None and llm_provider is not None:
        resolved_judge = LLMNarrativeJudge(llm_provider)
    resolved_shadow_comparator = shadow_comparator or LegacyHookShadowComparator()
    orchestrator = VerifierOrchestrator(
        statistical=StatisticalVerifier(),
        data=DataVerifier(),
        policy=PolicyVerifier(),
        narrative=NarrativeVerifier(judge=resolved_judge),
        repo=resolved_repo,
        scorer=ConfidenceScorer(),
        clock=SystemClock(),
        shadow_comparator=resolved_shadow_comparator,
        shadow_repo=resolved_shadow_repo,
    )
    return VerifierContainer(
        repo=resolved_repo,
        shadow_repo=resolved_shadow_repo,
        orchestrator=orchestrator,
    )
