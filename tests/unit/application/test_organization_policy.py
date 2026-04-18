"""Tests for organization policy enforcement."""

from __future__ import annotations

from ds_agent.application.services.organization_policy import OrgPolicyGate
from ds_agent.runtime.organization_store import JsonOrganizationStore


class TestOrgPolicyGate:
    def test_provider_allowlist_blocks_unapproved_provider(self, tmp_path) -> None:
        store = JsonOrganizationStore(base_dir=tmp_path)
        organization = store.update_settings(allowed_providers=["openai"])

        reason = OrgPolicyGate().check_provider_allowed("anthropic", organization)

        assert reason == "Provider 'anthropic' is not allowed by organization policy."

    def test_external_transfer_allows_local_provider_when_remote_models_disabled(
        self,
        tmp_path,
    ) -> None:
        store = JsonOrganizationStore(base_dir=tmp_path)
        organization = store.update_settings(external_data_transfer_allowed=False)

        assert OrgPolicyGate().check_external_data_transfer("ollama", organization) is None
        assert (
            OrgPolicyGate().check_external_data_transfer("anthropic", organization)
            == "External AI service data transfer is disabled by organization policy."
        )

    def test_budget_limit_uses_current_month_usage(self, tmp_path) -> None:
        store = JsonOrganizationStore(base_dir=tmp_path)
        organization = store.update_settings(max_budget_usd_per_user=2.0)
        store.record_usage(actor_id="analyst", provider="anthropic", cost_usd=2.0)

        reason = OrgPolicyGate().check_budget("analyst", organization, store)

        assert reason == "Monthly budget exceeded for 'analyst' (2.00 / 2.00 USD)."

    def test_tool_side_effect_policy_blocks_exports_and_web_search(self, tmp_path) -> None:
        store = JsonOrganizationStore(base_dir=tmp_path)
        organization = store.update_settings(
            export_allowed=False,
            external_data_transfer_allowed=False,
        )
        gate = OrgPolicyGate()

        assert gate.check_tool_allowed("generate_report", organization) == (
            "Artifact export is disabled by organization policy."
        )
        assert gate.check_tool_allowed("web_search", organization) == (
            "External data transfer is disabled by organization policy."
        )
