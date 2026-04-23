from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from ds_agent.domain.result_card import ResultCardSource, coerce_result_card
from ds_agent.infrastructure.persistence.card_store import SqliteCardStore

NOW = datetime(2026, 4, 19, 11, 0, tzinfo=UTC)


def _store(tmp_path: Path) -> SqliteCardStore:
    return SqliteCardStore(tmp_path / "result_cards.db")


def _insight(card_id: str, result_id: str, message_id: str, run_id: str, title: str) -> object:
    return coerce_result_card(
        "insight",
        {
            "title": title,
            "evidence": ["cohort analysis"],
            "trustStatus": "partial",
            "quickActions": ["export_report"],
        },
        card_id=card_id,
        result_id=result_id,
        created_at=NOW,
        source=ResultCardSource(messageId=message_id, runId=run_id),
    )


def _experiment(card_id: str, result_id: str, message_id: str, run_id: str) -> object:
    return coerce_result_card(
        "experiment",
        {
            "runId": run_id,
            "modelLabel": "XGBoost",
            "dataVersion": "dataset-v4",
            "primaryMetric": {
                "name": "roc_auc",
                "value": 0.901,
                "deltaVsBaseline": 0.013,
            },
            "artifactRefs": [{"artifactId": "artifact-3", "ref": "artifact://chart-3"}],
        },
        card_id=card_id,
        result_id=result_id,
        created_at=NOW,
        source=ResultCardSource(messageId=message_id, runId=run_id),
    )


def test_save_and_list_cards_by_session(tmp_path: Path) -> None:
    store = _store(tmp_path)
    card_a = _insight("RC-100", "result-100", "msg-100", "run-a", "First")
    card_b = _insight("RC-101", "result-101", "msg-101", "run-a", "Second")

    store.save_card("session-a", card_a)
    store.save_card("session-a", card_b)

    cards = store.list_cards_by_session("session-a")
    assert [card.id for card in cards] == ["RC-101", "RC-100"]
    assert cards[0].title == "Second"


def test_get_card_round_trips_payload(tmp_path: Path) -> None:
    store = _store(tmp_path)
    card = _experiment("RC-200", "result-200", "msg-200", "run-b")
    store.save_card("session-b", card)

    loaded = store.get_card("RC-200")
    assert loaded is not None
    assert loaded.card_id == "RC-200"
    assert loaded.result_id == "result-200"
    assert loaded.source.run_id == "run-b"
    assert loaded.type == "experiment"
    assert loaded.primary_metric.name == "roc_auc"
    assert loaded.primary_metric.value == 0.901


def test_pin_card_persists_across_reload(tmp_path: Path) -> None:
    db_path = tmp_path / "result_cards.db"
    store = SqliteCardStore(db_path)
    card = _insight("RC-300", "result-300", "msg-300", "run-c", "Pinned")
    store.save_card("session-c", card)

    updated = store.pin_card("RC-300", pinned=True)
    assert updated.pinned is True

    reloaded = SqliteCardStore(db_path)
    loaded = reloaded.get_card("RC-300")
    assert loaded is not None
    assert loaded.pinned is True


def test_missing_card_returns_none(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.get_card("missing") is None


def test_store_persists_created_at_as_json_number(tmp_path: Path) -> None:
    db_path = tmp_path / "result_cards.db"
    store = SqliteCardStore(db_path)
    card = _insight("RC-400", "result-400", "msg-400", "run-d", "Timestamp")
    store.save_card("session-d", card)

    with sqlite3.connect(db_path) as conn:
        payload_json = conn.execute(
            "SELECT payload_json FROM result_cards WHERE card_id = ?",
            ("RC-400",),
        ).fetchone()[0]

    payload = json.loads(payload_json)
    assert payload["cardId"] == "RC-400"
    assert payload["resultId"] == "result-400"
    assert isinstance(payload["createdAt"], float)
