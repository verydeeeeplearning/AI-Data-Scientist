"""Pure unit tests for ``BranchRunUseCase``.

The use case talks only to its three port interfaces. The fakes here
implement those ports in-memory so the test exercises validation,
parent-resolution, optional checkpoint resolution, and the contract that
the started run is anchored to the parent's session.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import pytest

from ds_agent.application.use_cases.branch_run_usecase import (
    BranchRunInput,
    BranchRunUseCase,
)
from ds_agent.domain.entities.runtime_state import RunState, RuntimeStatus
from ds_agent.domain.entities.session_checkpoint import NamedCheckpoint


@dataclass
class _FakeParentLookup:
    runs: dict[str, RunState] = field(default_factory=dict)

    def get(self, run_id: str) -> RunState | None:
        return self.runs.get(run_id)


@dataclass
class _FakeCheckpointLookup:
    checkpoints: dict[str, NamedCheckpoint] = field(default_factory=dict)

    def get_named(self, checkpoint_id: str) -> NamedCheckpoint | None:
        return self.checkpoints.get(checkpoint_id)


@dataclass
class _StartCall:
    session_id: str
    message: str
    parent_run_id: str
    resume_from_checkpoint: bool
    model: str | None


class _FakeStarter:
    def __init__(self) -> None:
        self.calls: list[_StartCall] = []

    async def start_branched_run(
        self,
        *,
        session_id: str,
        message: str,
        parent_run_id: str,
        resume_from_checkpoint: bool,
        model: str | None,
    ) -> RunState:
        self.calls.append(
            _StartCall(
                session_id=session_id,
                message=message,
                parent_run_id=parent_run_id,
                resume_from_checkpoint=resume_from_checkpoint,
                model=model,
            )
        )
        return RunState(
            run_id=f"branch-{len(self.calls):04d}",
            session_id=session_id,
            surface="ws",
            message=message,
            status=RuntimeStatus.RUNNING,
            branched_from_run_id=parent_run_id,
        )


def _make_parent(run_id: str = "parent-1", session_id: str = "sess-A") -> RunState:
    return RunState(
        run_id=run_id,
        session_id=session_id,
        surface="ws",
        message="parent message",
        status=RuntimeStatus.SUCCEEDED,
    )


async def test_execute_branches_run_inheriting_parent_session() -> None:
    parent = _make_parent()
    parents = _FakeParentLookup(runs={parent.run_id: parent})
    starter = _FakeStarter()
    use_case = BranchRunUseCase(
        parent_lookup=parents,
        checkpoint_lookup=_FakeCheckpointLookup(),
        starter=starter,
    )

    result = await use_case.execute(
        BranchRunInput(
            parent_run_id=parent.run_id,
            message="explore alternative model",
            model="claude-opus-4-7",
        )
    )

    assert result.parent_run_id == parent.run_id
    assert result.checkpoint is None
    assert result.run.session_id == "sess-A"
    assert result.run.branched_from_run_id == parent.run_id

    assert len(starter.calls) == 1
    call = starter.calls[0]
    assert call.session_id == "sess-A"
    assert call.parent_run_id == parent.run_id
    assert call.resume_from_checkpoint is False
    assert call.model == "claude-opus-4-7"
    assert call.message == "explore alternative model"


async def test_execute_with_checkpoint_id_resolves_and_requests_resume() -> None:
    parent = _make_parent()
    checkpoint = NamedCheckpoint(
        id="ckpt_001",
        session_id=parent.session_id,
        name="snapshot before fe",
        created_at=time.time(),
        transcript_step=4,
    )
    starter = _FakeStarter()
    use_case = BranchRunUseCase(
        parent_lookup=_FakeParentLookup(runs={parent.run_id: parent}),
        checkpoint_lookup=_FakeCheckpointLookup(
            checkpoints={checkpoint.id: checkpoint}
        ),
        starter=starter,
    )

    result = await use_case.execute(
        BranchRunInput(
            parent_run_id=parent.run_id,
            message="branch from snapshot",
            checkpoint_id=checkpoint.id,
        )
    )

    assert result.checkpoint is checkpoint
    assert starter.calls[0].resume_from_checkpoint is True


async def test_execute_rejects_blank_parent_run_id() -> None:
    use_case = BranchRunUseCase(
        parent_lookup=_FakeParentLookup(),
        checkpoint_lookup=_FakeCheckpointLookup(),
        starter=_FakeStarter(),
    )

    with pytest.raises(ValueError, match="parent_run_id is required"):
        await use_case.execute(BranchRunInput(parent_run_id="   ", message="hello"))


async def test_execute_rejects_blank_message() -> None:
    parent = _make_parent()
    use_case = BranchRunUseCase(
        parent_lookup=_FakeParentLookup(runs={parent.run_id: parent}),
        checkpoint_lookup=_FakeCheckpointLookup(),
        starter=_FakeStarter(),
    )

    with pytest.raises(ValueError, match="message is required"):
        await use_case.execute(
            BranchRunInput(parent_run_id=parent.run_id, message="   ")
        )


async def test_execute_rejects_unknown_parent_run() -> None:
    use_case = BranchRunUseCase(
        parent_lookup=_FakeParentLookup(),
        checkpoint_lookup=_FakeCheckpointLookup(),
        starter=_FakeStarter(),
    )

    with pytest.raises(ValueError, match="Unknown parent run: ghost"):
        await use_case.execute(BranchRunInput(parent_run_id="ghost", message="hi"))


async def test_execute_rejects_checkpoint_from_other_session() -> None:
    parent = _make_parent(session_id="sess-A")
    foreign_ckpt = NamedCheckpoint(
        id="ckpt_X",
        session_id="sess-OTHER",
        name="leaked",
        created_at=0.0,
        transcript_step=1,
    )
    use_case = BranchRunUseCase(
        parent_lookup=_FakeParentLookup(runs={parent.run_id: parent}),
        checkpoint_lookup=_FakeCheckpointLookup(
            checkpoints={foreign_ckpt.id: foreign_ckpt}
        ),
        starter=_FakeStarter(),
    )

    with pytest.raises(ValueError, match="checkpoint does not belong"):
        await use_case.execute(
            BranchRunInput(
                parent_run_id=parent.run_id,
                message="branch",
                checkpoint_id=foreign_ckpt.id,
            )
        )


async def test_execute_rejects_unknown_checkpoint_id() -> None:
    parent = _make_parent()
    use_case = BranchRunUseCase(
        parent_lookup=_FakeParentLookup(runs={parent.run_id: parent}),
        checkpoint_lookup=_FakeCheckpointLookup(),
        starter=_FakeStarter(),
    )

    with pytest.raises(ValueError, match="Unknown checkpoint: missing"):
        await use_case.execute(
            BranchRunInput(
                parent_run_id=parent.run_id,
                message="branch",
                checkpoint_id="missing",
            )
        )
