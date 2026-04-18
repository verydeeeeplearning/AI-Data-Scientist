"""Post-project learning orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from ds_agent.memory.code_registry import CodeRegistry
    from ds_agent.memory.domain_kb import DomainKB
    from ds_agent.memory.experiment_log import ExperimentLog
    from ds_agent.memory.unified_store import UnifiedMemoryStore

from ds_agent.domain.entities.memory import MemoryEntry, MemoryType
from ds_agent.self_improve.skill_extractor import SkillExtractor

logger = structlog.get_logger()


@dataclass
class ProjectOutcome:
    """Summary of a completed project."""

    project_id: str
    task_type: str
    success: bool
    primary_metric: str
    primary_metric_value: float
    models_tried: list[str] = field(default_factory=list)
    best_model: str | None = None
    domain: str | None = None
    key_findings: list[str] = field(default_factory=list)
    steps_taken: list[str] = field(default_factory=list)
    failure_reason: str | None = None
    duration_seconds: float = 0.0
    total_cost_usd: float = 0.0


class PostProjectLearner:
    """Orchestrates post-project learning activities.

    After a project completes:
    1. Log experiment to ExperimentLog
    2. Extract domain insights to DomainKB
    3. Extract reusable custom skill from successful workflows
    4. (Future) Extract code patterns to CodeRegistry
    """

    def __init__(
        self,
        experiment_log: ExperimentLog,
        code_registry: CodeRegistry,
        domain_kb: DomainKB,
        memory_store: UnifiedMemoryStore | None = None,
        skill_extractor: SkillExtractor | None = None,
        semantic_proposals: object | None = None,
    ) -> None:
        self._exp_log = experiment_log
        self._code_registry = code_registry
        self._domain_kb = domain_kb
        self._memory_store = memory_store
        self._skill_extractor = skill_extractor
        self._semantic_proposals = semantic_proposals

    def learn(self, outcome: ProjectOutcome) -> dict:
        """Run all learning activities for a completed project."""
        result: dict[str, str | bool | int] = {
            "project_id": outcome.project_id,
            "success": outcome.success,
            "experiments_logged": 0,
            "domain_insights_stored": 0,
            "patterns_extracted": 0,
            "retrospective_saved": 0,
            "custom_skills_extracted": 0,
        }

        # 1. Log experiment
        try:
            self._exp_log.log_experiment(
                project_id=outcome.project_id,
                model_type=outcome.best_model or "unknown",
                task_type=outcome.task_type,
                metrics={outcome.primary_metric: outcome.primary_metric_value},
                notes=(
                    f"Success: {outcome.success}. Models tried: {', '.join(outcome.models_tried)}"
                ),
            )
            result["experiments_logged"] = 1
        except Exception as e:
            logger.warning("experiment_log_failed", error=str(e))

        # 2. Store domain insights from key findings
        if outcome.key_findings and outcome.domain:
            for finding in outcome.key_findings:
                try:
                    self._domain_kb.store_insight(
                        domain=outcome.domain,
                        insight=finding,
                        category="project_finding",
                        confidence=0.9 if outcome.success else 0.5,
                        tags=[outcome.task_type],
                    )
                    self._submit_semantic_candidate(
                        finding,
                        outcome.domain,
                        [outcome.task_type],
                    )
                    result["domain_insights_stored"] = int(result["domain_insights_stored"]) + 1
                except Exception as e:
                    logger.warning("domain_kb_store_failed", error=str(e))

        # 3. Store failure lessons
        if not outcome.success and outcome.failure_reason:
            try:
                self._domain_kb.store_insight(
                    domain=outcome.domain or "general",
                    insight=f"Failure: {outcome.failure_reason}",
                    category="failure_lesson",
                    confidence=0.8,
                    tags=[outcome.task_type, "failure"],
                )
                self._submit_semantic_candidate(
                    f"Failure: {outcome.failure_reason}",
                    outcome.domain or "general",
                    [outcome.task_type, "failure"],
                )
                result["domain_insights_stored"] = int(result["domain_insights_stored"]) + 1
            except Exception as e:
                logger.warning("failure_lesson_store_failed", error=str(e))

        if self._memory_store is not None:
            try:
                self._memory_store.store(
                    MemoryEntry(
                        type=MemoryType.PROJECT,
                        key=f"{outcome.project_id}:retrospective",
                        content=self._build_retrospective(outcome),
                        tags=[
                            outcome.task_type,
                            outcome.domain or "general",
                            "success" if outcome.success else "failure",
                        ],
                        confidence=1.0 if outcome.success else 0.8,
                        source_session_id=outcome.project_id,
                    )
                )
                result["retrospective_saved"] = 1
            except Exception as e:
                logger.warning("retrospective_store_failed", error=str(e))

        if self._skill_extractor is not None:
            try:
                extracted = self._skill_extractor.extract(outcome)
                if extracted is not None:
                    result["custom_skills_extracted"] = 1
            except Exception as e:
                logger.warning("skill_extraction_failed", error=str(e))

        logger.info(
            "post_project_learning_complete",
            pid=outcome.project_id,
            experiments=result["experiments_logged"],
            insights=result["domain_insights_stored"],
            skills=result["custom_skills_extracted"],
        )
        return result

    def _submit_semantic_candidate(
        self,
        content: str,
        domain: str,
        tags: list[str],
    ) -> None:
        """Dual-write: create a semantic proposal alongside domain_kb."""
        if self._semantic_proposals is None:
            return
        try:
            import uuid
            from datetime import UTC, datetime

            from ds_agent.memory.semantic.domain.proposal import (
                SemanticProposal,
                SemanticProposalType,
            )

            proposal = SemanticProposal(
                proposal_id=f"SP-post-{uuid.uuid4().hex[:8]}",
                proposal_type=SemanticProposalType.NEGATIVE_KNOWLEDGE,
                summary=content[:200],
                target_id=f"domain:{domain}",
                payload={
                    "content": content,
                    "source_domain": domain,
                    "source_tags": tags,
                },
                evidence_refs=[],
                confidence=0.7,
                risk="low",
                proposed_by="agent",
                auto_apply_eligible=False,
                created_at=datetime.now(UTC),
            )
            self._semantic_proposals.save(proposal)  # type: ignore[attr-defined]
        except Exception:
            pass  # Dual-write failure is non-fatal

    @staticmethod
    def _build_retrospective(outcome: ProjectOutcome) -> str:
        parts = [
            f"Task type: {outcome.task_type}",
            f"Success: {outcome.success}",
            f"Primary metric: {outcome.primary_metric}={outcome.primary_metric_value}",
        ]
        if outcome.best_model:
            parts.append(f"Best model: {outcome.best_model}")
        if outcome.key_findings:
            parts.append("Findings: " + "; ".join(outcome.key_findings[:3]))
        if outcome.failure_reason:
            parts.append(f"Failure: {outcome.failure_reason}")
        return " | ".join(parts)
