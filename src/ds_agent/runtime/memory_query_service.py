"""Runtime service that backs memory tools with real persistent storage.

Semantic memory is the canonical source for domain knowledge.
DomainKB is retained as a legacy fallback for workspaces that have not
yet promoted their insights via ``scripts/promote_domain_kb.py``.
"""

from __future__ import annotations

import contextlib
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from ds_agent.memory.code_registry import CodeRegistry
from ds_agent.memory.domain_kb import DomainKB
from ds_agent.memory.experiment_log import ExperimentLog
from ds_agent.memory.project_store import ProjectStore

if TYPE_CHECKING:
    from ds_agent.memory.semantic.application.ports import (
        MetricRepository,
        SemanticProposalRepository,
    )


class MemoryQueryService:
    """Query and store memory across experiments, code patterns, domain KB, and projects.

    When a semantic memory MetricRepository is available, domain_knowledge
    searches query semantic memory first and fall back to the legacy
    DomainKB only if the semantic layer returns no results.
    """

    def __init__(
        self,
        experiment_log: ExperimentLog,
        code_registry: CodeRegistry,
        domain_kb: DomainKB,
        project_store: ProjectStore,
        *,
        semantic_metrics: MetricRepository | None = None,
        semantic_proposals: SemanticProposalRepository | None = None,
    ) -> None:
        self._experiment_log = experiment_log
        self._code_registry = code_registry
        self._domain_kb = domain_kb
        self._project_store = project_store
        self._semantic_metrics = semantic_metrics
        self._semantic_proposals = semantic_proposals

    @classmethod
    def from_workspace(cls, workspace_dir: str | None = None) -> MemoryQueryService:
        """Build a memory service for the current active workspace."""
        project_store = (
            ProjectStore(str(Path(workspace_dir).expanduser().resolve() / "projects"))
            if workspace_dir
            else ProjectStore()
        )

        semantic_metrics: MetricRepository | None = None
        semantic_proposals: SemanticProposalRepository | None = None
        with contextlib.suppress(Exception):
            from ds_agent.memory.semantic.infrastructure import (
                SemanticSqliteDatabase,
                SqliteMetricRepository,
                SqliteSemanticProposalRepository,
            )

            resolved_ws = str(Path(workspace_dir).expanduser().resolve()) if workspace_dir else "."
            db = SemanticSqliteDatabase(resolved_ws)
            semantic_metrics = SqliteMetricRepository(db)
            semantic_proposals = SqliteSemanticProposalRepository(db)

        return cls(
            experiment_log=ExperimentLog(),
            code_registry=CodeRegistry(),
            domain_kb=DomainKB(),
            project_store=project_store,
            semantic_metrics=semantic_metrics,
            semantic_proposals=semantic_proposals,
        )

    def search(self, query: str, memory_type: str = "all", max_results: int = 5) -> list[dict]:
        """Search configured memory stores and return normalized results."""
        normalized_query = query.strip().lower()
        results: list[dict] = []

        if memory_type in {"all", "experiments"}:
            for record in self._experiment_log.get_experiments(limit=max(max_results * 5, 20)):
                searchable_parts = [
                    str(record.get("project_id", "")),
                    str(record.get("model_type", "")),
                    str(record.get("task_type", "")),
                    str(record.get("notes", "")),
                    " ".join(str(v) for v in record.get("features", [])),
                ]
                if normalized_query and normalized_query not in " ".join(searchable_parts).lower():
                    continue
                results.append(
                    {
                        "type": "experiment",
                        "id": record.get("id"),
                        "title": record.get("notes") or record.get("task_type") or "experiment",
                        "summary": record.get("notes") or "",
                        "metadata": {
                            "project_id": record.get("project_id"),
                            "model_type": record.get("model_type"),
                            "task_type": record.get("task_type"),
                            "metrics": record.get("metrics", {}),
                        },
                    }
                )

        if memory_type in {"all", "code_patterns"}:
            for pattern in self._code_registry.search_patterns(query=query, limit=max_results * 5):
                results.append(
                    {
                        "type": "code_pattern",
                        "id": pattern.get("name"),
                        "title": pattern.get("name"),
                        "summary": pattern.get("description", ""),
                        "metadata": {
                            "tags": pattern.get("tags", []),
                            "task_type": pattern.get("task_type"),
                            "use_count": pattern.get("use_count", 0),
                        },
                    }
                )

        if memory_type in {"all", "domain_knowledge"}:
            # Semantic memory is canonical; DomainKB is legacy fallback.
            semantic_results = self._search_semantic_domain(normalized_query, max_results)
            results.extend(semantic_results)

            if not semantic_results:
                for insight in self._domain_kb.get_insights(limit=max(max_results * 5, 20)):
                    searchable_parts = [
                        str(insight.get("domain", "")),
                        str(insight.get("content", "")),
                        str(insight.get("category", "")),
                        " ".join(str(v) for v in insight.get("tags", [])),
                    ]
                    if (
                        normalized_query
                        and normalized_query not in " ".join(searchable_parts).lower()
                    ):
                        continue
                    results.append(
                        {
                            "type": "domain_knowledge",
                            "id": insight.get("timestamp"),
                            "title": insight.get("domain", "general"),
                            "summary": insight.get("content", ""),
                            "metadata": {
                                "source": "domain_kb_legacy",
                                "category": insight.get("category"),
                                "confidence": insight.get("confidence"),
                                "effective_confidence": insight.get("effective_confidence"),
                                "tags": insight.get("tags", []),
                            },
                        }
                    )

        if memory_type in {"all", "projects"}:
            for project in self._project_store.list_projects():
                searchable_parts = [
                    str(project.get("id", "")),
                    str(project.get("name", "")),
                    str(project.get("description", "")),
                    str(project.get("task_type", "")),
                ]
                if normalized_query and normalized_query not in " ".join(searchable_parts).lower():
                    continue
                results.append(
                    {
                        "type": "project",
                        "id": project.get("id"),
                        "title": project.get("name", "project"),
                        "summary": project.get("description", ""),
                        "metadata": {
                            "task_type": project.get("task_type"),
                            "artifact_count": len(project.get("artifacts", [])),
                        },
                    }
                )

        return results[:max_results]

    def store(
        self,
        content: str,
        memory_type: str,
        tags: list[str] | None = None,
    ) -> dict[str, object]:
        """Store memory content in the appropriate backing store."""
        normalized_tags = tags or []

        if memory_type == "experiment":
            exp_id = self._experiment_log.log_experiment(
                project_id="manual-memory",
                model_type="memory-note",
                task_type="memory-note",
                metrics={},
                features=normalized_tags,
                notes=content,
            )
            return {"stored": True, "type": memory_type, "id": exp_id, "tags": normalized_tags}

        if memory_type == "code_pattern":
            pattern_name = (
                normalized_tags[0] if normalized_tags else f"pattern-{uuid.uuid4().hex[:8]}"
            )
            stored_name = self._code_registry.store_pattern(
                name=pattern_name,
                code=content,
                description=content[:200],
                tags=normalized_tags,
                task_type="memory-note",
            )
            return {"stored": True, "type": memory_type, "id": stored_name, "tags": normalized_tags}

        if memory_type == "domain_knowledge":
            domain = normalized_tags[0] if normalized_tags else "general"
            # Legacy path (retained for coexistence)
            self._domain_kb.store_insight(
                domain=domain,
                insight=content,
                category="manual",
                tags=normalized_tags,
            )
            # Dual-write: also create a semantic proposal candidate
            self._submit_semantic_candidate(content, domain, normalized_tags)
            return {"stored": True, "type": memory_type, "id": domain, "tags": normalized_tags}

        raise ValueError(f"Unsupported memory_type: {memory_type}")

    # ------------------------------------------------------------------
    # Semantic memory helpers
    # ------------------------------------------------------------------

    def _search_semantic_domain(
        self,
        query: str,
        max_results: int,
    ) -> list[dict]:
        """Search semantic metric repository for domain knowledge."""
        if self._semantic_metrics is None:
            return []
        try:
            metrics = self._semantic_metrics.resolve(query, limit=max_results)
        except Exception:
            return []
        results: list[dict] = []
        for metric in metrics:
            results.append(
                {
                    "type": "domain_knowledge",
                    "id": metric.metric_id,
                    "title": metric.display_name,
                    "summary": metric.definition,
                    "metadata": {
                        "source": "semantic_memory",
                        "owner": metric.owner,
                        "grain": metric.grain,
                        "synonyms": metric.synonyms,
                    },
                }
            )
        return results

    def _submit_semantic_candidate(
        self,
        content: str,
        domain: str,
        tags: list[str],
    ) -> None:
        """Dual-write: create a semantic proposal when storing domain knowledge."""
        if self._semantic_proposals is None:
            return
        try:
            from datetime import UTC, datetime

            from ds_agent.memory.semantic.domain.proposal import (
                SemanticProposal,
                SemanticProposalType,
            )

            proposal = SemanticProposal(
                proposal_id=f"SP-auto-{uuid.uuid4().hex[:8]}",
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
            self._semantic_proposals.save(proposal)
        except Exception:
            pass  # Dual-write failure is non-fatal
