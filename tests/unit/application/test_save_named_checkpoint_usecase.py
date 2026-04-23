"""Pure unit tests for ``SaveNamedCheckpointUseCase``.

These tests use in-memory fakes that implement the use case ports defined
locally in the application layer, so the use case is exercised without any
file I/O or transcript-store dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from ds_agent.application.use_cases.save_named_checkpoint_usecase import (
    SaveNamedCheckpointInput,
    SaveNamedCheckpointUseCase,
)
from ds_agent.domain.entities.session_checkpoint import NamedCheckpoint


@dataclass
class _FakeStepProvider:
    """In-memory ``TranscriptStepProviderPort``."""

    steps_by_session: dict[str, int] = field(default_factory=dict)
    queries: list[str] = field(default_factory=list)

    def current_step(self, session_id: str) -> int:
        self.queries.append(session_id)
        return self.steps_by_session.get(session_id, 0)


@dataclass
class _FakeStore:
    """In-memory ``NamedCheckpointStorePort``."""

    saved: list[dict] = field(default_factory=list)
    next_id: int = 0

    def save_named(
        self,
        session_id: str,
        name: str,
        *,
        transcript_step: int,
        description: str | None = None,
    ) -> NamedCheckpoint:
        self.saved.append(
            {
                "session_id": session_id,
                "name": name,
                "transcript_step": transcript_step,
                "description": description,
            }
        )
        self.next_id += 1
        return NamedCheckpoint(
            id=f"ckpt_{self.next_id:04d}",
            session_id=session_id,
            name=name,
            created_at=1000.0 + self.next_id,
            transcript_step=transcript_step,
            description=description,
        )


def test_execute_persists_checkpoint_with_resolved_transcript_step() -> None:
    store = _FakeStore()
    steps = _FakeStepProvider(steps_by_session={"sess-1": 5})
    use_case = SaveNamedCheckpointUseCase(store=store, step_provider=steps)

    record = use_case.execute(
        SaveNamedCheckpointInput(
            session_id="sess-1",
            name="before fe",
            description="snapshot before feature engineering",
        )
    )

    assert record.session_id == "sess-1"
    assert record.name == "before fe"
    assert record.transcript_step == 5
    assert record.description == "snapshot before feature engineering"
    assert steps.queries == ["sess-1"]
    assert store.saved == [
        {
            "session_id": "sess-1",
            "name": "before fe",
            "transcript_step": 5,
            "description": "snapshot before feature engineering",
        }
    ]


def test_execute_normalizes_blank_description_to_none() -> None:
    store = _FakeStore()
    use_case = SaveNamedCheckpointUseCase(
        store=store,
        step_provider=_FakeStepProvider(steps_by_session={"sess-2": 0}),
    )

    record = use_case.execute(
        SaveNamedCheckpointInput(session_id="sess-2", name="ckpt", description="   ")
    )

    assert record.description is None
    assert store.saved[0]["description"] is None


def test_execute_rejects_blank_session_id() -> None:
    use_case = SaveNamedCheckpointUseCase(
        store=_FakeStore(),
        step_provider=_FakeStepProvider(),
    )

    with pytest.raises(ValueError, match="session_id is required"):
        use_case.execute(SaveNamedCheckpointInput(session_id="   ", name="ckpt"))


def test_execute_rejects_blank_name() -> None:
    use_case = SaveNamedCheckpointUseCase(
        store=_FakeStore(),
        step_provider=_FakeStepProvider(steps_by_session={"sess-3": 1}),
    )

    with pytest.raises(ValueError, match="name is required"):
        use_case.execute(SaveNamedCheckpointInput(session_id="sess-3", name="   "))


def test_execute_clamps_negative_transcript_step_to_zero() -> None:
    """Defensive: a faulty step provider must not push a negative step downstream."""

    class _NegativeProvider:
        def current_step(self, session_id: str) -> int:
            assert isinstance(session_id, str)
            return -7

    store = _FakeStore()
    use_case = SaveNamedCheckpointUseCase(store=store, step_provider=_NegativeProvider())

    record = use_case.execute(SaveNamedCheckpointInput(session_id="sess-4", name="zero"))

    assert record.transcript_step == 0
    assert store.saved[0]["transcript_step"] == 0
