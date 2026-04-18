"""PostLearningPort adapter — bridges domain interface to infrastructure."""

from __future__ import annotations

import structlog

from ds_agent.application.services.cross_session_learner import CrossSessionLearner
from ds_agent.memory.code_registry import CodeRegistry
from ds_agent.memory.domain_kb import DomainKB
from ds_agent.memory.experiment_log import ExperimentLog
from ds_agent.memory.unified_store import UnifiedMemoryStore
from ds_agent.self_improve.outcome_builder import build_session_outcome
from ds_agent.self_improve.pattern_learner import PatternLearner
from ds_agent.self_improve.post_project import PostProjectLearner, ProjectOutcome
from ds_agent.self_improve.promotion_candidates import JsonPromotionCandidateStore
from ds_agent.self_improve.skill_extractor import SkillExtractor

logger = structlog.get_logger()


class PostLearningAdapter:
    """Implements PostLearningPort — orchestrates post-tool learning."""

    def __init__(self, *, workspace_dir: str | None = None) -> None:
        self._exp_log = ExperimentLog()
        self._code_registry = CodeRegistry()
        self._domain_kb = DomainKB()
        self._memory_store = UnifiedMemoryStore()
        candidate_store = JsonPromotionCandidateStore.for_workspace(workspace_dir)
        self._learner = PostProjectLearner(
            self._exp_log,
            self._code_registry,
            self._domain_kb,
            memory_store=self._memory_store,
            skill_extractor=SkillExtractor(
                custom_dir=candidate_store.path.parent / "pending_skills",
                candidate_store=candidate_store,
            ),
        )
        self._cross_session = CrossSessionLearner(self._memory_store)
        self._pattern_learner = PatternLearner()

    def learn_from_tool_result(
        self, session_id: str, tool_name: str, arguments: dict, result: str
    ) -> None:
        """Record learnings from a successful tool execution."""
        outcome = ProjectOutcome(
            project_id=session_id,
            task_type=tool_name,
            success=True,
            primary_metric="tool_completion",
            primary_metric_value=1.0,
            best_model=arguments.get("model_type", "unknown"),
            key_findings=[result[:200]] if len(result) > 20 else [],
        )
        self._learner.learn(outcome)
        self._cross_session.learn_from_outcome(outcome)

        patterns = self._pattern_learner.extract_patterns(result)
        for p in patterns:
            self._code_registry.store_pattern(
                name=p.get("name", "unknown"),
                code="",
                description=f"Auto-detected {p.get('type', 'pattern')}",
                task_type=p.get("task_type", "general"),
                tags=[p.get("type", "")],
            )

    def learn_from_session_outcome(self, session_id: str, outcome: dict[str, object]) -> None:
        """Record learnings from a completed or interrupted agent turn."""
        project_outcome = build_session_outcome(
            session_id=session_id,
            final_output=str(outcome.get("final_output", "")),
            goal_summary=_optional_str(outcome.get("goal_summary")),
            goal_status=str(outcome.get("goal_status", "in_progress")),
            blocked_reason=_optional_str(outcome.get("blocked_reason")),
            pending_questions=_string_list(outcome.get("pending_questions")),
            current_summary=str(outcome.get("current_summary", "")),
            next_step=str(outcome.get("next_step", "")),
            reflection=str(outcome.get("reflection", "")),
            model_name=str(outcome.get("model_name", "unknown")),
            total_cost_usd=_as_float(outcome.get("total_cost_usd")),
            duration_seconds=_as_float(outcome.get("duration_seconds")),
            iterations=_as_int(outcome.get("iterations")),
        )
        self._learner.learn(project_outcome)
        self._cross_session.learn_from_outcome(project_outcome)


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _as_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0
