from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ds_agent.domain.entities.post_deploy import PostDeployMonitorState
from ds_agent.infrastructure.persistence.deploy_monitor_state_store import (
    SqliteDeployMonitorStateStore,
)


def _state(observed_at: datetime, **overrides: object) -> PostDeployMonitorState:
    payload: dict[str, object] = {
        "state_id": f"state-{observed_at.hour}",
        "model_id": "m_churn_lightgbm",
        "model_version": 5,
        "alias": "champion",
        "window": "24h",
        "observed_at": observed_at,
        "drift": {
            "overall_status": "warning",
            "max_psi": 0.24,
            "max_ks": 0.5,
            "top_drifting_features": ["f_user_activity_30d"],
            "metrics": [
                {
                    "feature_name": "f_user_activity_30d",
                    "metric_type": "PSI",
                    "value": 0.24,
                    "threshold": 0.2,
                    "level": "warning",
                }
            ],
        },
        "metrics": [
            {
                "metric": "f1_macro",
                "baseline_value": 0.8,
                "current_value": 0.76,
                "delta": -0.04,
                "direction": "worse",
                "status": "warning",
            }
        ],
        "service_level": {
            "latency_p95_ms": 120.0,
            "latency_budget_ms": 100,
            "qps": 42.0,
            "throughput_budget_qps": 40,
            "status": "warning",
        },
        "remediation": {
            "decision": "monitor",
            "severity": "medium",
            "rationale": "Watch the next batch.",
            "should_alert": False,
            "recommended_steps": ["Monitor the next few batches."],
        },
        "overall_status": "warning",
        "alerts": ["Latency budget exceeded."],
        "trigger_mode": "manual_only",
        "trigger_payload": {"trigger": "monitor", "model_id": "m_churn_lightgbm"},
    }
    payload.update(overrides)
    return PostDeployMonitorState.model_validate(payload)


def test_sqlite_deploy_monitor_state_store_round_trips_and_filters_by_window(tmp_path) -> None:
    store = SqliteDeployMonitorStateStore(tmp_path / "deploy_monitor.db")
    older = _state(datetime(2026, 4, 15, 0, tzinfo=UTC))
    newer = _state(
        datetime(2026, 4, 16, 0, tzinfo=UTC),
        state_id="state-new",
        overall_status="alert",
        alerts=["Performance dropped materially."],
    )

    store.save(older)
    store.save(newer)

    latest = store.latest("m_churn_lightgbm")
    assert latest is not None
    assert latest.state_id == "state-new"

    recent = store.list_states(
        model_id="m_churn_lightgbm",
        since=datetime(2026, 4, 15, 12, tzinfo=UTC),
    )
    assert [state.state_id for state in recent] == ["state-new"]

    horizon = datetime(2026, 4, 16, 0, tzinfo=UTC) - timedelta(days=2)
    all_states = store.list_states(model_id="m_churn_lightgbm", since=horizon)
    assert [state.state_id for state in all_states] == ["state-new", "state-0"]
