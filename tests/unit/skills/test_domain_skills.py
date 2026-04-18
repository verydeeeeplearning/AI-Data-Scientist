"""Domain skill pack tests for PLAN 17 Phase 5."""

from __future__ import annotations

from ds_agent.skills.domain_pack_loader import DomainPackLoader


class TestDomainSkillPacks:
    def test_finance_pack_loads_expected_skill(self):
        loader = DomainPackLoader()

        hub = loader.build_skill_hub(["finance"])
        skill = hub.view_skill("financial-ts-modeling")

        assert skill is not None
        assert "walk-forward" in skill["content"].lower()

    def test_finance_guardrail_warns_on_random_split(self):
        loader = DomainPackLoader()

        warnings = loader.validate_guardrails(
            domain_pack="finance",
            code="train_test_split(X, y, test_size=0.2, shuffle=True)",
            task_hint="time series return forecasting",
        )

        assert any("walk-forward" in warning.lower() for warning in warnings)
