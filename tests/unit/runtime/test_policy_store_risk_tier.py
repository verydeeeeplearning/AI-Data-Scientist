"""Tests for `JsonPolicyStore` risk-tier matrix persistence.

Wave 3 PLAN_05: backend matrix persistence + history-backed impact
preview. The store now writes a single ``risk_tier_matrix.json`` plus an
append-only ``risk_tier_matrix_history.jsonl`` log so that operator
drafts can be reconstructed and the renderer can show "last saved by".
"""

from __future__ import annotations

import json

import pytest

from ds_agent.runtime.policy_store import JsonPolicyStore


class TestRiskTierMatrixPersistence:
    """Round-trip + history behaviour for the risk-tier matrix store."""

    def test_load_returns_empty_when_file_absent(self, tmp_path):
        store = JsonPolicyStore(base_dir=tmp_path)
        assert store.load_risk_tier_matrix() == {}
        assert store.risk_tier_matrix_history() == []

    def test_save_round_trip_persists_matrix(self, tmp_path):
        store = JsonPolicyStore(base_dir=tmp_path)
        snapshot = store.save_risk_tier_matrix(
            {"data_loader": {"supervised": "T1", "delegate": "T0"}},
            saved_by="op@example.com",
        )

        assert snapshot.matrix == {
            "data_loader": {"supervised": "T1", "delegate": "T0"}
        }
        assert snapshot.saved_by == "op@example.com"
        assert snapshot.saved_at > 0

        # Reload via fresh store instance to confirm disk persistence.
        reloaded = JsonPolicyStore(base_dir=tmp_path)
        assert reloaded.load_risk_tier_matrix() == {
            "data_loader": {"supervised": "T1", "delegate": "T0"}
        }

    def test_save_appends_history_jsonl(self, tmp_path):
        store = JsonPolicyStore(base_dir=tmp_path)
        store.save_risk_tier_matrix({"jira_create": {"autopilot": "T2"}})
        store.save_risk_tier_matrix({"jira_create": {"autopilot": "T3"}})
        store.save_risk_tier_matrix({"prod_deploy": {"delegate": "T3"}})

        history_path = tmp_path / "policy" / "risk_tier_matrix_history.jsonl"
        lines = [
            json.loads(line)
            for line in history_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(lines) == 3
        assert lines[0]["matrix"] == {"jira_create": {"autopilot": "T2"}}
        assert lines[2]["matrix"] == {"prod_deploy": {"delegate": "T3"}}

    def test_history_returns_newest_first(self, tmp_path):
        store = JsonPolicyStore(base_dir=tmp_path)
        store.save_risk_tier_matrix(
            {"data_loader": {"supervised": "T1"}}, saved_at=100.0
        )
        store.save_risk_tier_matrix(
            {"data_loader": {"supervised": "T2"}}, saved_at=200.0
        )
        store.save_risk_tier_matrix(
            {"data_loader": {"supervised": "T3"}}, saved_at=300.0
        )

        history = store.risk_tier_matrix_history()
        assert [snapshot.saved_at for snapshot in history] == [300.0, 200.0, 100.0]
        assert history[0].matrix == {"data_loader": {"supervised": "T3"}}

    def test_history_respects_limit(self, tmp_path):
        store = JsonPolicyStore(base_dir=tmp_path)
        for index in range(5):
            store.save_risk_tier_matrix(
                {"data_loader": {"supervised": f"T{index}"}},
                saved_at=float(index),
            )

        history = store.risk_tier_matrix_history(limit=2)
        assert len(history) == 2
        assert history[0].matrix == {"data_loader": {"supervised": "T4"}}
        assert history[1].matrix == {"data_loader": {"supervised": "T3"}}

    def test_save_validates_authority_level(self, tmp_path):
        store = JsonPolicyStore(base_dir=tmp_path)
        with pytest.raises(ValueError):
            store.save_risk_tier_matrix(
                {"data_loader": {"not-an-authority": "T0"}}
            )

    def test_save_with_empty_matrix_is_noop_round_trip(self, tmp_path):
        store = JsonPolicyStore(base_dir=tmp_path)
        snapshot = store.save_risk_tier_matrix({})
        assert snapshot.matrix == {}
        assert store.load_risk_tier_matrix() == {}
        # The history entry still records the empty save so the operator
        # has an audit trail for "they cleared the matrix".
        assert len(store.risk_tier_matrix_history()) == 1
