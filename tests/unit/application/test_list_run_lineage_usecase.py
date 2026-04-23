"""Pure unit tests for ``ListRunLineageUseCase``."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from ds_agent.application.use_cases.list_run_lineage_usecase import (
    ListRunLineageUseCase,
)
from ds_agent.domain.entities.runtime_state import RunState, RuntimeStatus


@dataclass
class _FakeRuns:
    runs: dict[str, RunState] = field(default_factory=dict)

    def get(self, run_id: str) -> RunState | None:
        return self.runs.get(run_id)

    def list(
        self,
        *,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[RunState]:
        values = list(self.runs.values())
        if session_id is not None:
            values = [run for run in values if run.session_id == session_id]
        values.sort(key=lambda item: item.created_at, reverse=True)
        return values[:limit]


def _make_run(
    run_id: str,
    *,
    session_id: str = "sess-A",
    created_at: float,
    parent_run_id: str | None = None,
    rerun_from_node_id: str | None = None,
) -> RunState:
    return RunState(
        run_id=run_id,
        session_id=session_id,
        surface="ws",
        message=f"message for {run_id}",
        status=RuntimeStatus.SUCCEEDED,
        created_at=created_at,
        started_at=created_at,
        branched_from_run_id=parent_run_id,
        rerun_from_node_id=rerun_from_node_id,
    )


def test_execute_returns_preorder_tree_from_true_root() -> None:
    root = _make_run("run-root", created_at=100.0)
    branch = _make_run("run-branch", created_at=110.0, parent_run_id=root.run_id)
    rerun = _make_run(
        "run-rerun",
        created_at=120.0,
        parent_run_id=branch.run_id,
        rerun_from_node_id="plan/feature_engineering",
    )
    sibling = _make_run("run-sibling", created_at=130.0, parent_run_id=root.run_id)
    use_case = ListRunLineageUseCase(
        _FakeRuns(
            runs={
                root.run_id: root,
                branch.run_id: branch,
                rerun.run_id: rerun,
                sibling.run_id: sibling,
            }
        )
    )

    result = use_case.execute(rerun.run_id)

    assert result.root_run_id == root.run_id
    assert result.seed_run_id == rerun.run_id
    assert [node.run.run_id for node in result.nodes] == [
        root.run_id,
        branch.run_id,
        rerun.run_id,
        sibling.run_id,
    ]
    assert [node.depth for node in result.nodes] == [0, 1, 2, 1]
    assert result.nodes[0].is_root is True
    assert result.nodes[2].is_seed is True
    assert result.nodes[2].run.rerun_from_node_id == "plan/feature_engineering"


def test_execute_ignores_runs_from_other_sessions() -> None:
    root = _make_run("run-root", created_at=100.0)
    same_session = _make_run("run-child", created_at=110.0, parent_run_id=root.run_id)
    foreign = _make_run(
        "run-foreign",
        session_id="sess-B",
        created_at=120.0,
        parent_run_id=root.run_id,
    )
    use_case = ListRunLineageUseCase(
        _FakeRuns(
            runs={
                root.run_id: root,
                same_session.run_id: same_session,
                foreign.run_id: foreign,
            }
        )
    )

    result = use_case.execute(root.run_id)

    assert [node.run.run_id for node in result.nodes] == [root.run_id, same_session.run_id]


def test_execute_rejects_blank_root_run_id() -> None:
    use_case = ListRunLineageUseCase(_FakeRuns())

    with pytest.raises(ValueError, match="root_run_id is required"):
        use_case.execute("   ")


def test_execute_rejects_unknown_run_id() -> None:
    use_case = ListRunLineageUseCase(_FakeRuns())

    with pytest.raises(ValueError, match="Unknown run: ghost"):
        use_case.execute("ghost")
