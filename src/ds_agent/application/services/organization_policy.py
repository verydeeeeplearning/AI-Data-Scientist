"""Organization policy gate for team and enterprise controls."""

from __future__ import annotations

from ds_agent.domain.entities.organization import Organization
from ds_agent.providers.router import parse_model_string
from ds_agent.runtime.organization_store import JsonOrganizationStore


class OrgPolicyGate:
    """Evaluate organization policies outside the agent reasoning loop."""

    EXPORT_TOOLS = frozenset(
        {
            "generate_report",
            "generate_deployment",
            "notebook_generate",
            "slide_generate",
            "dashboard_spec",
        }
    )
    EXTERNAL_TRANSFER_TOOLS = frozenset({"web_search"})
    LOCAL_PROVIDERS = frozenset({"ollama", "vllm", "sglang"})

    def check_run_allowed(
        self,
        *,
        model_name: str,
        actor_id: str,
        organization: Organization,
        usage_store: JsonOrganizationStore,
    ) -> str | None:
        """Return a human-readable violation reason or None."""
        provider, _ = parse_model_string(model_name)
        violation = self.check_provider_allowed(provider, organization)
        if violation is not None:
            return violation

        violation = self.check_external_data_transfer(provider, organization)
        if violation is not None:
            return violation

        violation = self.check_budget(actor_id, organization, usage_store)
        if violation is not None:
            return violation

        return None

    @staticmethod
    def check_provider_allowed(provider: str, organization: Organization) -> str | None:
        """Validate provider allowlist policy."""
        allowed = organization.settings.allowed_providers
        if not allowed:
            return None
        if provider in allowed:
            return None
        return f"Provider '{provider}' is not allowed by organization policy."

    def check_external_data_transfer(self, provider: str, organization: Organization) -> str | None:
        """Block remote providers when external transfer is disabled."""
        if organization.settings.external_data_transfer_allowed:
            return None
        if provider in self.LOCAL_PROVIDERS:
            return None
        return "External AI service data transfer is disabled by organization policy."

    @staticmethod
    def check_budget(
        actor_id: str,
        organization: Organization,
        usage_store: JsonOrganizationStore,
    ) -> str | None:
        """Validate current month org and per-user budget caps."""
        per_user_limit = organization.settings.max_budget_usd_per_user
        if per_user_limit is not None:
            user_cost = usage_store.current_month_cost_for_actor(actor_id)
            if user_cost >= per_user_limit:
                return (
                    f"Monthly budget exceeded for '{actor_id}' "
                    f"({user_cost:.2f} / {per_user_limit:.2f} USD)."
                )

        org_limit = organization.settings.max_budget_usd_per_org
        if org_limit is not None:
            org_cost = usage_store.current_month_cost_for_org()
            if org_cost >= org_limit:
                return (
                    "Organization monthly budget exceeded "
                    f"({org_cost:.2f} / {org_limit:.2f} USD)."
                )
        return None

    def check_tool_allowed(self, tool_name: str, organization: Organization) -> str | None:
        """Validate tool side effects against org policy."""
        if tool_name in self.EXPORT_TOOLS and not organization.settings.export_allowed:
            return "Artifact export is disabled by organization policy."
        if (
            tool_name in self.EXTERNAL_TRANSFER_TOOLS
            and not organization.settings.external_data_transfer_allowed
        ):
            return "External data transfer is disabled by organization policy."
        return None
