"""Agent-backed orchestrator for live offline evaluation runs."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from typing import Any

from ds_agent.agent.callbacks import NullCallbacks
from ds_agent.agent.factory import create_agent
from ds_agent.domain.interfaces.llm_provider import LLMProvider
from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.infrastructure.ingestion.session_trace_reader import SessionTraceReader
from ds_agent.runtime.approval_store import JsonApprovalStore
from ds_agent.runtime.checkpoint_store import JsonCheckpointStore
from ds_agent.runtime.goal_store import JsonGoalStore
from ds_agent.runtime.organization_store import JsonOrganizationStore
from ds_agent.runtime.run_registry import RunRegistry
from ds_agent.runtime.runtime_event_log import RuntimeEventLog
from ds_agent.runtime.session_registry import RuntimeSessionRegistry
from ds_agent.runtime.task_ledger import TaskLedger
from ds_agent.runtime.transcript_store import JsonTranscriptStore
from ds_agent.runtime.working_memory import JsonWorkingMemoryStore
from ds_agent.skills.hub import SkillHub

_TASK_EVENT_MESSAGES = {
    "task.started": "Evaluation task started.",
    "task.completed": "Evaluation task completed.",
    "task.failed": "Evaluation task failed.",
    "task.cancelled": "Evaluation task cancelled.",
}

_TASK_EVENT_SEVERITY = {
    "task.started": "info",
    "task.completed": "success",
    "task.failed": "error",
    "task.cancelled": "warning",
}


class _EvalCallbacks(NullCallbacks):
    """Persist lifecycle events emitted by an evaluation agent run."""

    def __init__(
        self,
        *,
        runtime_event_log: RuntimeEventLog,
        session_id: str,
        run_id: str,
        surface: str,
    ) -> None:
        self._runtime_event_log = runtime_event_log
        self._session_id = session_id
        self._run_id = run_id
        self._surface = surface

    def emit_event(self, event: str, payload: dict) -> None:
        if event not in _TASK_EVENT_MESSAGES:
            return
        self._runtime_event_log.record(
            category="task",
            kind=event,
            severity=_TASK_EVENT_SEVERITY[event],
            message=_TASK_EVENT_MESSAGES[event],
            session_id=str(payload.get("sessionId") or self._session_id),
            run_id=str(payload.get("runId") or self._run_id),
            surface=str(payload.get("surface") or self._surface),
            source="agent",
            metadata=dict(payload),
        )


class AgentEvalOrchestrator:
    """Execute a gold task with a real agent and rebuild it into an EvalRun."""

    def __init__(
        self,
        *,
        workspace_dir: str,
        provider_factory: Callable[[str], LLMProvider],
        model_name: str,
        run_mode: str = "offline",
        max_iterations: int = 8,
        max_cost_usd: float = 10.0,
        budget_factor: float = 1.0,
        session_registry: RuntimeSessionRegistry | None = None,
        run_registry: RunRegistry | None = None,
        runtime_event_log: RuntimeEventLog | None = None,
        organization_store: JsonOrganizationStore | None = None,
        transcript_store: JsonTranscriptStore | None = None,
        checkpoint_store: JsonCheckpointStore | None = None,
        goal_store: JsonGoalStore | None = None,
        working_memory_store: JsonWorkingMemoryStore | None = None,
        approval_store: JsonApprovalStore | None = None,
        task_ledger: TaskLedger | None = None,
        skill_hub: SkillHub | None = None,
        run_metadata: dict[str, Any] | None = None,
    ) -> None:
        self._workspace_dir = workspace_dir
        self._provider_factory = provider_factory
        self._model_name = model_name
        self._run_mode = run_mode
        self._max_iterations = max_iterations
        self._max_cost_usd = max_cost_usd
        self._budget_factor = budget_factor

        self._session_registry = session_registry or RuntimeSessionRegistry(workspace_dir)
        self._run_registry = run_registry or RunRegistry(self._session_registry, workspace_dir)
        self._runtime_event_log = runtime_event_log or RuntimeEventLog(workspace_dir)
        self._organization_store = organization_store or JsonOrganizationStore(workspace_dir)
        self._transcript_store = transcript_store or JsonTranscriptStore(workspace_dir)
        self._checkpoint_store = checkpoint_store or JsonCheckpointStore(workspace_dir)
        self._goal_store = goal_store or JsonGoalStore(workspace_dir)
        self._working_memory_store = working_memory_store or JsonWorkingMemoryStore(workspace_dir)
        self._approval_store = approval_store or JsonApprovalStore(workspace_dir)
        self._task_ledger = task_ledger or TaskLedger(workspace_dir)
        self._skill_hub = skill_hub
        self._run_metadata = dict(run_metadata or {})

    def run_task(self, task: GoldTask) -> EvalRun:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._run_task_async(task))
        raise RuntimeError(
            "AgentEvalOrchestrator.run_task() cannot run inside an active event loop."
        )

    async def _run_task_async(self, task: GoldTask) -> EvalRun:
        session_id = f"eval-{task.id}-{uuid.uuid4().hex[:8]}"
        surface = f"eval_{self._run_mode}"
        prompt = _render_task_prompt(task)

        self._session_registry.ensure(session_id, surface)
        run = self._run_registry.create(session_id, surface, prompt)

        callbacks = _EvalCallbacks(
            runtime_event_log=self._runtime_event_log,
            session_id=session_id,
            run_id=run.run_id,
            surface=surface,
        )
        provider = self._provider_factory(self._model_name)
        max_cost_usd = self._max_cost_usd
        if task.input.budget_usd > 0:
            max_cost_usd = task.input.budget_usd
        max_cost_usd *= self._budget_factor
        agent = create_agent(
            provider=provider,
            callbacks=callbacks,
            max_iterations=self._max_iterations,
            max_cost_usd=max_cost_usd,
            mode="auto",
            model_name=self._model_name,
            workspace_dir=self._workspace_dir,
            session_id=session_id,
            transcript_store=self._transcript_store,
            checkpoint_store=self._checkpoint_store,
            goal_store=self._goal_store,
            working_memory_store=self._working_memory_store,
            approval_store=self._approval_store,
            skill_hub=self._skill_hub,
        )
        agent.set_runtime_context(run_id=run.run_id, surface=surface)

        async def _execute() -> str:
            return await agent.run(prompt, execution_mode="evaluation")

        agent_task = asyncio.create_task(_execute(), name=f"eval:{run.run_id}")
        task_state = self._task_ledger.register(run.run_id, agent_task)
        self._run_registry.attach_task(run.run_id, task_state.task_id)
        self._session_registry.bind_run(session_id, run.run_id, surface)

        try:
            result = await agent_task
        except Exception as exc:
            await asyncio.sleep(0)
            self._run_registry.mark_failed(run.run_id, str(exc))
            raise
        await asyncio.sleep(0)
        cost = _extract_total_cost(agent)
        self._run_registry.mark_succeeded(run.run_id, result=result, cost_usd=cost)
        self._organization_store.record_usage(
            actor_id="local-user",
            provider=_provider_name_from_model(self._model_name),
            cost_usd=cost,
            model=self._model_name,
            session_id=session_id,
            run_id=run.run_id,
        )
        trace_reader = SessionTraceReader(
            transcript_store=self._transcript_store,
            approval_store=self._approval_store,
            checkpoint_store=self._checkpoint_store,
            goal_store=self._goal_store,
            runtime_event_log=self._runtime_event_log,
            organization_store=self._organization_store,
            run_registry=self._run_registry,
            session_registry=self._session_registry,
            task_ledger=self._task_ledger,
        )
        eval_run = trace_reader.read_session(
            session_id=session_id,
            task_id=task.id,
            run_id=run.run_id,
        )
        metadata = dict(eval_run.metadata)
        metadata.update(
            {
                "source": "agent_eval_orchestrator",
                "executionBridge": "agent",
                "requestedMode": self._run_mode,
                "model": self._model_name,
                "budgetFactor": self._budget_factor,
            }
        )
        metadata.update(self._run_metadata)
        return eval_run.model_copy(
            update={
                "mode": self._run_mode,
                "task_id": task.id,
                "metadata": metadata,
            }
        )


def _extract_total_cost(agent: object) -> float:
    budget = getattr(agent, "_budget", None)
    state = getattr(budget, "state", None)
    total_cost = getattr(state, "total_cost_usd", 0.0)
    return float(total_cost or 0.0)


def _provider_name_from_model(model_name: str) -> str:
    provider, _, _ = model_name.partition("/")
    return provider or "unknown"


def _render_task_prompt(task: GoldTask) -> str:
    lines = [task.prompt.strip()]
    if task.input.datasets:
        lines.append("")
        lines.append("Datasets:")
        for dataset in task.input.datasets:
            lines.append(f"- {dataset.name}: {dataset.source}")
    constraints: list[str] = []
    if task.input.snapshot_date is not None:
        constraints.append(f"snapshot_date={task.input.snapshot_date.isoformat()}")
    if task.input.budget_usd > 0:
        constraints.append(f"budget_usd={task.input.budget_usd:.2f}")
    if task.input.time_budget_min > 0:
        constraints.append(f"time_budget_min={task.input.time_budget_min}")
    if constraints:
        lines.append("")
        lines.append("Constraints:")
        lines.extend(f"- {item}" for item in constraints)
    if task.expected_deliverables:
        lines.append("")
        lines.append("Expected deliverables:")
        for deliverable in task.expected_deliverables:
            required_parts = ", ".join(deliverable.must_contain)
            summary = deliverable.type
            if required_parts:
                summary = f"{summary} (must contain: {required_parts})"
            lines.append(f"- {summary}")
    metric_validation = task.validation_points.metric_selection
    if metric_validation and metric_validation.acceptable_primary:
        lines.append("")
        lines.append(
            "Primary metric guidance: "
            + ", ".join(metric_validation.acceptable_primary)
        )
    return "\n".join(lines)
