from __future__ import annotations

from pathlib import Path

import pytest

from ds_agent.runtime.web_push_subject_store import (
    JsonWebPushSubjectStore,
    WebPushSubjectError,
)


def _store(tmp_path: Path) -> JsonWebPushSubjectStore:
    return JsonWebPushSubjectStore(workspace_dir=str(tmp_path / "workspace"))


def test_load_returns_none_when_empty(tmp_path: Path) -> None:
    store = _store(tmp_path)

    assert store.load() is None


def test_save_round_trip_persists_subject(tmp_path: Path) -> None:
    store = _store(tmp_path)

    saved = store.save('  mailto:admin@example.com  ')

    assert saved == 'mailto:admin@example.com'
    assert store.load() == 'mailto:admin@example.com'


def test_save_rejects_invalid_subject(tmp_path: Path) -> None:
    store = _store(tmp_path)

    with pytest.raises(WebPushSubjectError):
        store.save('ftp://example.com')


def test_restart_survival_reads_existing_subject(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save('https://example.com/contact')

    new_store = _store(tmp_path)
    assert new_store.load() == 'https://example.com/contact'
