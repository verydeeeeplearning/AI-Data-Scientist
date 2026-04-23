"""Pure unit tests for ``RerunFromStepUseCase``.

The use case is exercised against in-memory port fakes so no transport,
storage, or agent runtime is involved. We verify happy-path linkage,
input validation (parent + node id), the message-override fallback to the
parent's last message, and that the ``model`` argument is forwarded as-is.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from ds_agent.application.use_cases.rerun_from_step_usecase import (
    RerunFromStepInput,
    RerunFromStepUseCase,
)
from ds_agent.domain.entities.runtime_state import RunState, RuntimeStatus


@dataclass
class _FakeParentLookup:
    runs: dict[str, RunState] = field(default_factory=dict)

    def get(self, run_id: str) -> RunState | None:
        return self.runs.get(run_id)


@dataclass
class _StartCall:
    session_id: str
    message: str
    parent_run_id: str
    plan_node_id: str
    model: str | None


class _FakeStarter:
    def __init__(self) -> None:
        self.calls: list[_StartCall] = []

    async def start_rerun_from_step(
        self,
        *,
        session_id: str,
        message: str,
        parent_run_id: str,
        plan_node_id: str,
        model: str | None,
    ) -> RunState:
        self.calls.append(
            _StartCall(
                session_id=session_id,
                message=message,
                parent_run_id=parent_run_id,
                plan_node_id=plan_node_id,
                model=model,
            )
        )
        return RunState(
            run_id=f"rerun-{len(self.calls):04d}",
            session_id=session_id,
            surface="ws",
            message=message,
            status=RuntimeStatus.RUNNING,
            branched_from_run_id=parent_run_id,
            rerun_from_node_id=plan_node_id,
        )


def _make_parent(
    run_id: str = "parent-1",
    session_id: str = "sess-A",
    message: str = "explore churn drivers",
) -> RunState:
    return RunState(
        run_id=run_id,
        session_id=session_id,
        surface="ws",
        message=message,
        status=RuntimeStatus.SUCCEEDED,
    )


async def test_execute_reruns_from_node_with_explicit_message_override() -> None:
    parent = _make_parent()
    starter = _FakeStarter()
    use_case = RerunFromStepUseCase(
        parent_lookup=_FakeParentLookup(runs={parent.run_id: parent}),
        starter=starter,
    )

    result = await use_case.execute(
        RerunFromStepInput(
            parent_run_id=parent.run_id,
            plan_node_id="ds_workflow_plan/feature_engineering",
            message_override="redo with regularization",
            model="claude-opus-4-7",
        )
    )

    assert result.parent_run_id == parent.run_id
    assert result.plan_node_id == "ds_workflow_plan/feature_engineering"
    assert result.run.session_id == "sess-A"
    assert result.run.branched_from_run_id == parent.run_id
    assert result.run.rerun_from_node_id == "ds_workflow_plan/feature_engineering"

    assert len(starter.calls) == 1
    call = starter.calls[0]
    assert call.session_id == "sess-A"
    assert call.parent_run_id == parent.run_id
    assert call.plan_node_id == "ds_workflow_plan/feature_engineering"
    assert call.message == "redo with regularization"
    assert call.model == "claude-opus-4-7"


async def test_execute_rejects_unknown_parent_run() -> None:
    use_case = RerunFromStepUseCase(
        parent_lookup=_FakeParentLookup(),
        starter=_FakeStarter(),
    )

    with pytest.raises(ValueError, match="Unknown parent run: ghost"):
        await use_case.execute(
            RerunFromStepInput(parent_run_id="ghost", plan_node_id="step")
        )


async def test_execute_rejects_blank_plan_node_id() -> None:
    parent = _make_parent()
    use_case = RerunFromStepUseCase(
        parent_lookup=_FakeParentLookup(runs={parent.run_id: parent}),
        starter=_FakeStarter(),
    )

    with pytest.raises(ValueError, match="plan_node_id is required"):
        await use_case.execute(
            RerunFromStepInput(parent_run_id=parent.run_id, plan_node_id="   ")
        )


async def test_execute_rejects_blank_parent_run_id() -> None:
    use_case = RerunFromStepUseCase(
        parent_lookup=_FakeParentLookup(),
        starter=_FakeStarter(),
    )

    with pytest.raises(ValueError, match="parent_run_id is required"):
        await use_case.execute(
            RerunFromStepInput(parent_run_id="   ", plan_node_id="step")
        )


async def test_execute_falls_back_to_parent_message_when_override_missing() -> None:
    parent = _make_parent(message="parent prompt with details")
    starter = _FakeStarter()
    use_case = RerunFromStepUseCase(
        parent_lookup=_FakeParentLookup(runs={parent.run_id: parent}),
        starter=starter,
    )

    await use_case.execute(
        RerunFromStepInput(
            parent_run_id=parent.run_id,
            plan_node_id="ds_workflow_plan",
            message_override=None,
        )
    )

    assert starter.calls[0].message == "parent prompt with details"


async def test_execute_falls_back_to_parent_message_when_override_blank() -> None:
    """Whitespace-only override behaves the same as ``None``."""
    parent = _make_parent(message="parent prompt")
    starter = _FakeStarter()
    use_case = RerunFromStepUseCase(
        parent_lookup=_FakeParentLookup(runs={parent.run_id: parent}),
        starter=starter,
    )

    await use_case.execute(
        RerunFromStepInput(
            parent_run_id=parent.run_id,
            plan_node_id="ds_workflow_plan",
            message_override="   ",
        )
    )

    assert starter.calls[0].message == "parent prompt"


async def test_execute_passes_model_through_when_provided() -> None:
    parent = _make_parent()
    starter = _FakeStarter()
    use_case = RerunFromStepUseCase(
        parent_lookup=_FakeParentLookup(runs={parent.run_id: parent}),
        starter=starter,
    )

    await use_case.execute(
        RerunFromStepInput(
            parent_run_id=parent.run_id,
            plan_node_id="step",
            model="anthropic/claude-haiku",
        )
    )

    assert starter.calls[0].model == "anthropic/claude-haiku"
