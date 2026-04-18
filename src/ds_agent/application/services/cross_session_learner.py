"""Cross-session learning services for PLAN 17 Phase 6."""

from __future__ import annotations

from pathlib import Path

from ds_agent.domain.entities.improvement_insight import ImprovementInsight
from ds_agent.domain.entities.memory import MemoryEntry, MemoryType
from ds_agent.memory.unified_store import UnifiedMemoryStore
from ds_agent.self_improve.post_project import ProjectOutcome


class CrossSessionLearner:
    """Store and retrieve reusable project lessons."""

    def __init__(self, memory_store: UnifiedMemoryStore) -> None:
        self._memory_store = memory_store

    @classmethod
    def from_workspace(cls, workspace_dir: str | None) -> CrossSessionLearner:
        if workspace_dir:
            db_path = (
                Path(workspace_dir).expanduser().resolve()
                / "data"
                / "memory"
                / "cross_session.db"
            )
            return cls(memory_store=UnifiedMemoryStore(str(db_path)))
        return cls(memory_store=UnifiedMemoryStore())

    def learn_from_outcome(self, outcome: ProjectOutcome) -> int:
        """Persist useful success and failure insights."""
        stored = 0

        if outcome.success and outcome.best_model:
            stored += self._store_insight(
                ImprovementInsight(
                    category="success_pattern",
                    summary=(
                        f"{outcome.task_type} succeeded with {outcome.best_model} "
                        f"(metric {outcome.primary_metric}={outcome.primary_metric_value:.3f})."
                    ),
                    tags=[
                        outcome.task_type,
                        outcome.domain or "general",
                        "success",
                        outcome.best_model,
                    ],
                    confidence=1.0,
                    source_project_id=outcome.project_id,
                ),
                suffix="best-model",
            )

        for index, finding in enumerate(outcome.key_findings):
            stored += self._store_insight(
                ImprovementInsight(
                    category="success_pattern" if outcome.success else "failure_pattern",
                    summary=finding,
                    tags=[outcome.task_type, outcome.domain or "general", "finding"],
                    confidence=0.9 if outcome.success else 0.6,
                    source_project_id=outcome.project_id,
                ),
                suffix=f"finding-{index}",
            )

        if outcome.failure_reason:
            stored += self._store_insight(
                ImprovementInsight(
                    category="failure_pattern",
                    summary=f"Avoid: {outcome.failure_reason}",
                    tags=[outcome.task_type, outcome.domain or "general", "failure"],
                    confidence=0.85,
                    source_project_id=outcome.project_id,
                ),
                suffix="failure",
            )

        return stored

    def build_prompt_context(self, query: str, max_results: int = 3) -> str:
        """Build a concise prompt context from relevant prior projects."""
        entries = self._memory_store.search(
            query=query,
            memory_type=MemoryType.PROJECT,
            max_results=max_results,
        )
        return self._format_entries(entries)

    def recent_prompt_context(self, max_results: int = 3) -> str:
        """Return recent project insights independent of a query."""
        entries = self._memory_store.list_by_type(MemoryType.PROJECT, limit=max_results)
        return self._format_entries(entries)

    def _store_insight(self, insight: ImprovementInsight, *, suffix: str) -> int:
        key = f"{insight.source_project_id}:{insight.category}:{suffix}"
        self._memory_store.store(insight.to_memory_entry(key))
        return 1

    @staticmethod
    def _format_entries(entries: list[MemoryEntry]) -> str:
        if not entries:
            return ""
        lines = []
        for entry in entries:
            prefix = "Avoid" if "failure" in entry.tags else "Reuse"
            lines.append(f"- {prefix}: {entry.content}")
        return "\n".join(lines)
