from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ds_agent.application.use_cases.list_run_artifacts_usecase import (
    ListRunArtifactsUseCase,
)
from ds_agent.domain.entities.runtime_state import RunState, RuntimeStatus
from ds_agent.domain.result_card import ResultCardSource, coerce_result_card
from ds_agent.infrastructure.artifact.exporters import supported_formats

NOW = datetime(2026, 4, 20, 9, 0, tzinfo=UTC)


class _RunLookup:
    def __init__(self, run: RunState | None) -> None:
        self._run = run

    def get_run(self, run_id: str) -> RunState | None:
        if self._run is None or self._run.run_id != run_id:
            return None
        return self._run


class _CardStore:
    def __init__(self, cards) -> None:
        self._cards = list(cards)
        self.calls: list[dict[str, object]] = []

    def list_cards_by_session(
        self,
        session_id: str,
        *,
        limit: int = 100,
        include_archived: bool = False,
    ):
        self.calls.append(
            {
                "session_id": session_id,
                "limit": limit,
                "include_archived": include_archived,
            }
        )
        return list(self._cards)


class _WorkspaceFiles:
    def __init__(self, files: list[dict[str, object]]) -> None:
        self._files = list(files)

    def list_files(self, project_id: str | None = None) -> list[dict[str, object]]:
        assert project_id is None
        return list(self._files)


def _build_card(
    *,
    card_id: str,
    run_id: str,
    title: str,
    pinned: bool = False,
) -> object:
    return coerce_result_card(
        "insight",
        {
            "title": title,
            "evidence": ["cohort analysis"],
            "trustStatus": "partial",
            "quickActions": ["export_report"],
        },
        card_id=card_id,
        result_id=f"result-{card_id}",
        created_at=NOW,
        source=ResultCardSource(messageId=f"msg-{card_id}", runId=run_id),
        pinned=pinned,
    )


def test_execute_returns_run_cards_workspace_files_and_export_candidates() -> None:
    run = RunState(
        run_id="run-1",
        session_id="session-1",
        surface="ws",
        message="Investigate retention",
        status=RuntimeStatus.SUCCEEDED,
        created_at=1_713_605_000.0,
        started_at=1_713_605_005.0,
        finished_at=1_713_605_050.0,
        task_id="task-1",
        result_preview="Retention improved",
        cost_usd=1.23,
    )
    store = _CardStore(
        [
            _build_card(card_id="RC-101", run_id="run-1", title="Pinned", pinned=True),
            _build_card(card_id="RC-102", run_id="run-1", title="Visible"),
            _build_card(card_id="RC-201", run_id="run-2", title="Other run"),
        ]
    )
    workspace_files = _WorkspaceFiles(
        [
            {
                "name": "report.md",
                "path": "report.md",
                "size": 120,
                "type": "md",
                "modifiedAt": 1_713_605_200_000,
            },
            {
                "name": "metrics.csv",
                "path": "metrics.csv",
                "size": 64,
                "type": "csv",
                "modifiedAt": 1_713_605_250_000,
            },
            {
                "name": "plot.png",
                "path": "plots/plot.png",
                "size": 512,
                "type": "png",
                "modifiedAt": 1_713_605_300_000,
            },
        ]
    )
    use_case = ListRunArtifactsUseCase(
        run_lookup=_RunLookup(run),
        card_store=store,
        workspace_files=workspace_files,
        export_formats_for_suffix=supported_formats,
    )

    result = use_case.execute(
        run_id="run-1",
        include_archived_cards=True,
        card_limit=10,
    )

    assert result["scope"] == {
        "cards": "run",
        "files": "workspace",
        "exportCandidates": "workspace",
    }
    assert result["run"] == {
        "runId": "run-1",
        "sessionId": "session-1",
        "surface": "ws",
        "message": "Investigate retention",
        "status": "succeeded",
        "createdAt": 1_713_605_000.0,
        "startedAt": 1_713_605_005.0,
        "finishedAt": 1_713_605_050.0,
        "taskId": "task-1",
        "error": None,
        "resultPreview": "Retention improved",
        "costUsd": 1.23,
    }
    assert [card["cardId"] for card in result["cards"]] == ["RC-101", "RC-102"]
    assert result["summary"] == {
        "cardCount": 2,
        "pinnedCardCount": 1,
        "fileCount": 3,
        "exportCandidateCount": 2,
        "cardTypeCounts": {"insight": 2},
    }
    assert result["files"] == workspace_files.list_files()
    assert result["exportCandidates"] == [
        {
            "name": "report.md",
            "path": "report.md",
            "type": "md",
            "formats": ["docx", "html", "pdf"],
        },
        {
            "name": "metrics.csv",
            "path": "metrics.csv",
            "type": "csv",
            "formats": ["html", "xlsx"],
        },
    ]
    assert store.calls == [
        {
            "session_id": "session-1",
            "limit": 500,
            "include_archived": True,
        }
    ]


def test_execute_raises_for_unknown_run() -> None:
    use_case = ListRunArtifactsUseCase(
        run_lookup=_RunLookup(None),
        card_store=_CardStore([]),
        workspace_files=_WorkspaceFiles([]),
        export_formats_for_suffix=supported_formats,
    )

    with pytest.raises(LookupError, match="Run not found: missing-run"):
        use_case.execute(run_id="missing-run")
