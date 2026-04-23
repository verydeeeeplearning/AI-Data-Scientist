from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from ds_agent.api.app import create_app
from ds_agent.api.ws_handler import AppState
from ds_agent.config.schema import AgentConfig, DSAgentConfig
from ds_agent.domain.result_card import ResultCardSource, clone_result_card, coerce_result_card
from ds_agent.infrastructure.persistence.card_store import SqliteCardStore

NOW = datetime(2026, 4, 20, 9, 0, tzinfo=UTC)


def _client(tmp_path) -> TestClient:
    app = create_app()
    config = DSAgentConfig(
        agent=AgentConfig(workspace_dir=str(tmp_path / "workspace")),
    )
    app.state.app_state = AppState(config=config)
    return TestClient(app)


def _seed_insight_card(
    client: TestClient,
    *,
    session_id: str,
    card_id: str,
    result_id: str,
    title: str,
    archived: bool = False,
) -> None:
    workspace_dir = client.app.state.app_state.config.agent.workspace_dir
    store = SqliteCardStore.for_workspace(workspace_dir)
    card = coerce_result_card(
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
        source=ResultCardSource(messageId=f"msg-{card_id}", runId="run-1"),
        archived=archived,
    )
    persisted = clone_result_card(card, archived=archived)
    store.save_card(session_id, persisted)


def test_create_app_mounts_card_routes(tmp_path) -> None:
    client = _client(tmp_path)

    paths = {getattr(route, "path", "") for route in client.app.routes}

    assert "/api/cards/session/{session_id}" in paths
    assert "/api/cards/{card_id}" in paths
    assert "/api/cards/{card_id}/pin" in paths


def test_list_cards_by_session_returns_alias_preserving_payloads(tmp_path) -> None:
    client = _client(tmp_path)
    _seed_insight_card(
        client,
        session_id="session-a",
        card_id="RC-100",
        result_id="result-100",
        title="First",
    )
    _seed_insight_card(
        client,
        session_id="session-a",
        card_id="RC-101",
        result_id="result-101",
        title="Second",
    )
    _seed_insight_card(
        client,
        session_id="session-a",
        card_id="RC-102",
        result_id="result-102",
        title="Archived",
        archived=True,
    )
    _seed_insight_card(
        client,
        session_id="session-b",
        card_id="RC-200",
        result_id="result-200",
        title="Other session",
    )

    response = client.get("/api/cards/session/session-a")

    assert response.status_code == 200
    payload = response.json()["cards"]
    assert [card["cardId"] for card in payload] == ["RC-101", "RC-100"]
    assert [card["resultId"] for card in payload] == ["result-101", "result-100"]
    assert payload[0]["createdAt"] == NOW.timestamp()
    assert payload[0]["source"] == {
        "messageId": "msg-RC-101",
        "runId": "run-1",
        "toolCallId": None,
    }
    assert "id" not in payload[0]


def test_list_cards_by_session_can_include_archived_cards(tmp_path) -> None:
    client = _client(tmp_path)
    _seed_insight_card(
        client,
        session_id="session-archived",
        card_id="RC-300",
        result_id="result-300",
        title="Visible",
    )
    _seed_insight_card(
        client,
        session_id="session-archived",
        card_id="RC-301",
        result_id="result-301",
        title="Archived",
        archived=True,
    )

    response = client.get(
        "/api/cards/session/session-archived",
        params={"includeArchived": True},
    )

    assert response.status_code == 200
    payload = response.json()["cards"]
    assert [card["cardId"] for card in payload] == ["RC-301", "RC-300"]
    assert payload[0]["archived"] is True


def test_get_card_returns_alias_preserving_payload(tmp_path) -> None:
    client = _client(tmp_path)
    _seed_insight_card(
        client,
        session_id="session-one",
        card_id="RC-401",
        result_id="result-401",
        title="Retention lift",
    )

    response = client.get("/api/cards/RC-401")

    assert response.status_code == 200
    payload = response.json()["card"]
    assert payload["cardId"] == "RC-401"
    assert payload["resultId"] == "result-401"
    assert payload["title"] == "Retention lift"
    assert payload["trustStatus"] == "partial"
    assert payload["quickActions"] == ["export_report"]
    assert "id" not in payload


def test_get_card_returns_404_for_unknown_card(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/cards/missing-card")

    assert response.status_code == 404
    assert response.json() == {"detail": "Card not found: missing-card"}


def test_pin_card_updates_persisted_state(tmp_path) -> None:
    client = _client(tmp_path)
    _seed_insight_card(
        client,
        session_id="session-pin",
        card_id="RC-500",
        result_id="result-500",
        title="Pin me",
    )

    response = client.post("/api/cards/RC-500/pin", json={"pinned": True})

    assert response.status_code == 200
    payload = response.json()["card"]
    assert payload["cardId"] == "RC-500"
    assert payload["pinned"] is True

    follow_up = client.get("/api/cards/RC-500")
    assert follow_up.status_code == 200
    assert follow_up.json()["card"]["pinned"] is True


def test_pin_card_can_unpin_existing_card(tmp_path) -> None:
    client = _client(tmp_path)
    _seed_insight_card(
        client,
        session_id="session-unpin",
        card_id="RC-501",
        result_id="result-501",
        title="Unpin me",
    )
    client.post("/api/cards/RC-501/pin", json={"pinned": True})

    response = client.post("/api/cards/RC-501/pin", json={"pinned": False})

    assert response.status_code == 200
    assert response.json()["card"]["pinned"] is False


def test_pin_card_returns_404_for_unknown_card(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.post("/api/cards/missing/pin", json={"pinned": True})

    assert response.status_code == 404
    assert response.json() == {"detail": "Card not found: missing"}
