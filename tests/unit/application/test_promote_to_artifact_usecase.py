"""Pure unit tests for ``PromoteToArtifactUseCase``.

The use case is exercised against an in-memory fake store. We verify the
happy path, audience whitelist enforcement, the persistence contract, and
that the returned ``PromotedArtifact`` is a frozen dataclass instance.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass, field

import pytest

from ds_agent.application.use_cases.promote_to_artifact_usecase import (
    PromoteToArtifactInput,
    PromoteToArtifactUseCase,
)
from ds_agent.domain.entities.run_lineage import PromotedArtifact


@dataclass
class _FakeStore:
    saved: list[dict[str, object]] = field(default_factory=list)
    next_id: int = 0

    def save_promoted_artifact(
        self,
        *,
        run_id: str,
        card_id: str,
        audience: str,
        title: str,
    ) -> PromotedArtifact:
        self.next_id += 1
        record = {
            "run_id": run_id,
            "card_id": card_id,
            "audience": audience,
            "title": title,
        }
        self.saved.append(record)
        # Cast at the boundary — the use case has already validated the
        # audience whitelist so the literal cast is safe in this fake.
        audience_literal = audience  # type: ignore[assignment]
        return PromotedArtifact(
            artifact_id=f"art_{self.next_id:04d}",
            run_id=run_id,
            card_id=card_id,
            audience=audience_literal,  # type: ignore[arg-type]
            title=title,
            created_at=1000.0 + self.next_id,
        )


def test_execute_persists_artifact_for_known_audience() -> None:
    store = _FakeStore()
    use_case = PromoteToArtifactUseCase(store=store)

    artifact = use_case.execute(
        PromoteToArtifactInput(
            run_id="run-1",
            card_id="card-7",
            audience="exec",
            title="Q2 churn brief",
        )
    )

    assert artifact.run_id == "run-1"
    assert artifact.card_id == "card-7"
    assert artifact.audience == "exec"
    assert artifact.title == "Q2 churn brief"
    assert artifact.artifact_id.startswith("art_")
    assert store.saved == [
        {
            "run_id": "run-1",
            "card_id": "card-7",
            "audience": "exec",
            "title": "Q2 churn brief",
        }
    ]


def test_execute_normalizes_audience_case_and_whitespace() -> None:
    store = _FakeStore()
    use_case = PromoteToArtifactUseCase(store=store)

    artifact = use_case.execute(
        PromoteToArtifactInput(
            run_id="run-2",
            card_id="card-1",
            audience="  ML  ",
        )
    )

    assert artifact.audience == "ml"
    assert store.saved[0]["audience"] == "ml"


def test_execute_rejects_unknown_audience() -> None:
    use_case = PromoteToArtifactUseCase(store=_FakeStore())

    with pytest.raises(ValueError, match="audience must be one of"):
        use_case.execute(
            PromoteToArtifactInput(
                run_id="run-3",
                card_id="card-2",
                audience="board",
            )
        )


def test_execute_rejects_blank_required_fields() -> None:
    use_case = PromoteToArtifactUseCase(store=_FakeStore())

    with pytest.raises(ValueError, match="run_id is required"):
        use_case.execute(
            PromoteToArtifactInput(run_id="   ", card_id="c", audience="ds")
        )

    with pytest.raises(ValueError, match="card_id is required"):
        use_case.execute(
            PromoteToArtifactInput(run_id="r", card_id="   ", audience="ds")
        )


def test_execute_falls_back_title_to_card_id_when_missing_or_blank() -> None:
    store = _FakeStore()
    use_case = PromoteToArtifactUseCase(store=store)

    artifact_none = use_case.execute(
        PromoteToArtifactInput(run_id="r", card_id="card-A", audience="ds")
    )
    artifact_blank = use_case.execute(
        PromoteToArtifactInput(
            run_id="r",
            card_id="card-B",
            audience="ds",
            title="   ",
        )
    )

    assert artifact_none.title == "card-A"
    assert artifact_blank.title == "card-B"


def test_returned_promoted_artifact_is_frozen() -> None:
    store = _FakeStore()
    use_case = PromoteToArtifactUseCase(store=store)

    artifact = use_case.execute(
        PromoteToArtifactInput(run_id="r", card_id="c", audience="ds")
    )

    with pytest.raises(FrozenInstanceError):
        artifact.title = "mutation should fail"  # type: ignore[misc]
