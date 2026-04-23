"""Build a compact evidence/export snapshot for one tracked run."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from typing import Protocol

from ds_agent.domain.entities.runtime_state import RunState
from ds_agent.domain.result_card import ResultCard


class RunLookup(Protocol):
    """Minimal run lookup contract."""

    def get_run(self, run_id: str) -> RunState | None: ...


class WorkspaceFileListing(Protocol):
    """Minimal workspace file listing contract."""

    def list_files(self, project_id: str | None = None) -> list[dict[str, object]]: ...


class SessionCardListingStore(Protocol):
    """Minimal card listing contract."""

    def list_cards_by_session(
        self,
        session_id: str,
        *,
        limit: int = 100,
        include_archived: bool = False,
    ) -> list[ResultCard]: ...


class ListRunArtifactsUseCase:
    """Return a backend-authoritative run/workspace artifact snapshot."""

    _MIN_CARD_SCAN_LIMIT = 500

    def __init__(
        self,
        *,
        run_lookup: RunLookup,
        card_store: SessionCardListingStore,
        workspace_files: WorkspaceFileListing,
        export_formats_for_suffix: Callable[[str], Iterable[object]],
    ) -> None:
        self._run_lookup = run_lookup
        self._card_store = card_store
        self._workspace_files = workspace_files
        self._export_formats_for_suffix = export_formats_for_suffix

    def execute(
        self,
        *,
        run_id: str,
        include_archived_cards: bool = False,
        card_limit: int = 100,
    ) -> dict[str, object]:
        if not run_id.strip():
            raise ValueError("run_id is required")
        if card_limit < 1:
            raise ValueError("card_limit must be >= 1")

        run = self._run_lookup.get_run(run_id)
        if run is None:
            raise LookupError(f"Run not found: {run_id}")

        files = list(self._workspace_files.list_files())
        cards = self._card_store.list_cards_by_session(
            run.session_id,
            limit=max(card_limit * 5, self._MIN_CARD_SCAN_LIMIT),
            include_archived=include_archived_cards,
        )
        run_cards = [card for card in cards if card.source.run_id == run_id][:card_limit]
        export_candidates = [
            candidate
            for file_entry in files
            if (candidate := self._build_export_candidate(file_entry)) is not None
        ]
        card_type_counts = dict(Counter(card.type for card in run_cards))

        return {
            "scope": {
                "cards": "run",
                "files": "workspace",
                "exportCandidates": "workspace",
            },
            "run": self._serialize_run(run),
            "summary": {
                "cardCount": len(run_cards),
                "pinnedCardCount": sum(1 for card in run_cards if card.pinned),
                "fileCount": len(files),
                "exportCandidateCount": len(export_candidates),
                "cardTypeCounts": card_type_counts,
            },
            "cards": [card.model_dump(mode="json", by_alias=True) for card in run_cards],
            "files": files,
            "exportCandidates": export_candidates,
        }

    def _build_export_candidate(
        self,
        file_entry: dict[str, object],
    ) -> dict[str, object] | None:
        suffix = _resolve_suffix(file_entry)
        formats = _normalize_export_formats(self._export_formats_for_suffix(suffix))
        if not formats:
            return None

        return {
            "name": str(file_entry.get("name", "")),
            "path": str(file_entry.get("path", "")),
            "type": str(file_entry.get("type", "")),
            "formats": formats,
        }

    @staticmethod
    def _serialize_run(run: RunState) -> dict[str, object]:
        return {
            "runId": run.run_id,
            "sessionId": run.session_id,
            "surface": run.surface,
            "message": run.message,
            "status": run.status.value,
            "createdAt": run.created_at,
            "startedAt": run.started_at,
            "finishedAt": run.finished_at,
            "taskId": run.task_id,
            "error": run.error,
            "resultPreview": run.result_preview,
            "costUsd": run.cost_usd,
        }


def _resolve_suffix(file_entry: dict[str, object]) -> str:
    file_type = file_entry.get("type")
    if isinstance(file_type, str) and file_type.strip():
        return f".{file_type.strip().lower().lstrip('.')}"
    name = file_entry.get("name")
    if isinstance(name, str) and "." in name:
        return "." + name.rsplit(".", 1)[-1].lower()
    return ""


def _normalize_export_formats(values: Iterable[object]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        candidate = getattr(value, "value", value)
        if isinstance(candidate, str) and candidate not in normalized:
            normalized.append(candidate)
    return normalized
