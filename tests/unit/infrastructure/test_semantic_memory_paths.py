from __future__ import annotations

from ds_agent.infrastructure.semantic_memory_paths import resolve_semantic_db_path
from ds_agent.runtime.transcript_store import get_runtime_storage_root


def test_resolve_semantic_db_path_prefers_runtime_canonical_path(tmp_path) -> None:
    resolved = resolve_semantic_db_path(tmp_path)

    assert resolved == get_runtime_storage_root(str(tmp_path)) / "semantic" / "semantic_memory.db"


def test_resolve_semantic_db_path_falls_back_to_workspace_legacy_path(tmp_path) -> None:
    legacy_path = tmp_path / "semantic" / "semantic_memory.db"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text("legacy", encoding="utf-8")

    resolved = resolve_semantic_db_path(tmp_path)

    assert resolved == legacy_path


def test_resolve_semantic_db_path_falls_back_to_decision_os_legacy_path(tmp_path) -> None:
    legacy_path = tmp_path / "data" / "memory" / "semantic" / "semantic_memory.db"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text("legacy", encoding="utf-8")

    resolved = resolve_semantic_db_path(tmp_path)

    assert resolved == legacy_path


def test_resolve_semantic_db_path_prefers_canonical_over_legacy(tmp_path) -> None:
    legacy_path = tmp_path / "semantic" / "semantic_memory.db"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text("legacy", encoding="utf-8")
    canonical_path = get_runtime_storage_root(str(tmp_path)) / "semantic" / "semantic_memory.db"
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_path.write_text("canonical", encoding="utf-8")

    resolved = resolve_semantic_db_path(tmp_path)

    assert resolved == canonical_path
