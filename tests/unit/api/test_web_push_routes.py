"""Web push HTTP route contract tests (Wave 4 PLAN_06b infrastructure close)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ds_agent.api.app import create_app
from ds_agent.api.ws_handler import AppState
from ds_agent.config.schema import AgentConfig, DSAgentConfig


def _client(tmp_path: Path) -> TestClient:
    app = create_app()
    config = DSAgentConfig(
        agent=AgentConfig(workspace_dir=str(tmp_path / "workspace")),
    )
    app.state.app_state = AppState(config=config)
    return TestClient(app)


def test_get_public_key_returns_none_when_unset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DS_AGENT_VAPID_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("DS_AGENT_VAPID_PUBLIC_KEY", raising=False)
    client = _client(tmp_path)

    response = client.get("/api/web-push/public-key")
    assert response.status_code == 200
    assert response.json() == {"publicKey": None}


def test_get_public_key_returns_value_when_state_has_one(tmp_path: Path) -> None:
    client = _client(tmp_path)
    # Inject a public key directly to avoid env coupling.
    client.app.state.app_state._vapid_public_key = "BFakePublicKey"

    response = client.get("/api/web-push/public-key")
    assert response.status_code == 200
    assert response.json() == {"publicKey": "BFakePublicKey"}


def test_get_subject_prefers_config_over_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DS_AGENT_VAPID_SUBJECT", "mailto:env@example.com")
    client = _client(tmp_path)
    client.app.state.app_state.web_push_subject_store.save("mailto:config@example.com")

    response = client.get("/api/web-push/subject")
    assert response.status_code == 200
    assert response.json() == {
        "subject": "mailto:config@example.com",
        "source": "config",
    }


def test_post_subject_persists_and_overrides_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DS_AGENT_VAPID_SUBJECT", "mailto:env@example.com")
    client = _client(tmp_path)

    response = client.post(
        "/api/web-push/subject",
        json={"subject": "https://example.com/contact"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "ok": True,
        "subject": "https://example.com/contact",
        "source": "config",
    }

    follow_up = client.get("/api/web-push/subject")
    assert follow_up.status_code == 200
    assert follow_up.json() == {
        "subject": "https://example.com/contact",
        "source": "config",
    }


def test_register_subscription_stores_record(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/web-push/subscriptions",
        json={
            "operatorId": "op-77",
            "endpoint": "https://push.example/abc",
            "p256dh": "p256-fake",
            "auth": "auth-fake",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["endpoint"] == "https://push.example/abc"
    assert body["operatorId"] == "op-77"

    store = client.app.state.app_state.web_push_subscription_store
    items = store.list_for("op-77")
    assert len(items) == 1
    assert items[0].endpoint == "https://push.example/abc"


def test_register_subscription_accepts_ipc_field_aliases(tmp_path: Path) -> None:
    """The Electron IPC sends ``p256dhKey`` / ``authKey`` (camelCase)."""
    client = _client(tmp_path)

    response = client.post(
        "/api/web-push/subscriptions",
        json={
            "endpoint": "https://push.example/xyz",
            "p256dhKey": "p256-fake",
            "authKey": "auth-fake",
        },
    )
    assert response.status_code == 200
    body = response.json()
    # No operatorId in body → falls back to the sole-user default.
    assert body["operatorId"] == "local-user"


def test_register_subscription_invalid_body_returns_400(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/web-push/subscriptions",
        json={"operatorId": "op-1", "endpoint": "https://push.example/abc"},
    )
    assert response.status_code == 400
    assert "p256dh" in response.json()["detail"].lower()


def test_unregister_subscription_removes_record(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post(
        "/api/web-push/subscriptions",
        json={
            "operatorId": "op-9",
            "endpoint": "https://push.example/zz",
            "p256dh": "k",
            "auth": "a",
        },
    )

    response = client.post(
        "/api/web-push/subscriptions/unregister",
        json={"operatorId": "op-9", "endpoint": "https://push.example/zz"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["removed"] is True

    store = client.app.state.app_state.web_push_subscription_store
    assert store.list_for("op-9") == []


def test_get_metrics_returns_windowed_summary(tmp_path: Path) -> None:
    client = _client(tmp_path)
    metrics_store = client.app.state.app_state.web_push_metrics_store
    metrics_store.record_delivery("op-1", "https://push.example/a", True)
    metrics_store.record_delivery("op-1", "https://push.example/b", False)
    metrics_store.record_prune("op-1", "https://push.example/b", "http_410")
    metrics_store.record_delivery("op-2", "https://push.example/c", True)

    response = client.get(
        "/api/web-push/metrics",
        params={"operatorId": "op-1", "windowHours": 24},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["operatorId"] == "op-1"
    assert body["windowHours"] == 24
    assert body["deliveredCount"] == 1
    assert body["failedCount"] == 1
    assert body["prunedCount"] == 1
    assert body["uniqueEndpoints"] == 2
    assert "T" in body["since"]
