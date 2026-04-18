"""Tests for the file-backed organization store."""

from __future__ import annotations

import pytest

from ds_agent.domain.entities.organization import OrgRole
from ds_agent.runtime.organization_store import JsonOrganizationStore


class TestJsonOrganizationStore:
    def test_update_settings_can_clear_budget_caps(self, tmp_path) -> None:
        store = JsonOrganizationStore(base_dir=tmp_path)

        store.update_settings(max_budget_usd_per_user=25.0, max_budget_usd_per_org=100.0)
        updated = store.update_settings(max_budget_usd_per_user=None, max_budget_usd_per_org=None)

        assert updated.settings.max_budget_usd_per_user is None
        assert updated.settings.max_budget_usd_per_org is None

    def test_update_member_role_keeps_one_admin(self, tmp_path) -> None:
        store = JsonOrganizationStore(base_dir=tmp_path)

        with pytest.raises(ValueError, match="At least one admin must remain"):
            store.update_member_role("local-user", OrgRole.VIEWER)

    def test_record_usage_summary_groups_by_actor_and_provider(self, tmp_path) -> None:
        store = JsonOrganizationStore(base_dir=tmp_path)

        store.record_usage(actor_id="alice", provider="anthropic", cost_usd=1.25, recorded_at=10.0)
        store.record_usage(actor_id="alice", provider="anthropic", cost_usd=0.75, recorded_at=20.0)
        store.record_usage(actor_id="bob", provider="openai", cost_usd=2.5, recorded_at=30.0)

        summary = store.get_usage_summary()

        assert summary["totalCostUsd"] == pytest.approx(4.5)
        assert summary["totalRunCount"] == 3
        per_user = {item["actorId"]: item for item in summary["perUser"]}
        assert per_user["alice"]["costUsd"] == pytest.approx(2.0)
        assert per_user["alice"]["providers"]["anthropic"] == pytest.approx(2.0)
        assert per_user["bob"]["providers"]["openai"] == pytest.approx(2.5)

    def test_record_usage_persists_model_token_and_cache_savings_fields(self, tmp_path) -> None:
        store = JsonOrganizationStore(base_dir=tmp_path)

        store.record_usage(
            actor_id="alice",
            provider="anthropic",
            model="anthropic/claude-sonnet-4-6",
            cost_usd=1.25,
            input_tokens=1000,
            output_tokens=500,
            cache_read_tokens=200,
            cache_write_tokens=50,
            reasoning_tokens=25,
            cache_savings_usd=0.12,
            recorded_at=10.0,
        )

        record = store.list_usage_records()[0]
        summary = store.get_usage_summary()

        assert record.model == "anthropic/claude-sonnet-4-6"
        assert record.input_tokens == 1000
        assert record.cache_savings_usd == pytest.approx(0.12)
        assert summary["totalCacheSavingsUsd"] == pytest.approx(0.12)
