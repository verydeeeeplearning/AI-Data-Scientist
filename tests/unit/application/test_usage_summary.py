from __future__ import annotations

from ds_agent.application.services.usage_summary import UsageSummaryService
from ds_agent.runtime.organization_store import JsonOrganizationStore


class TestUsageSummaryService:
    def test_summary_splits_month_day_session_and_cache_savings(self, tmp_path) -> None:
        store = JsonOrganizationStore(base_dir=tmp_path)
        service = UsageSummaryService(store)

        store.record_usage(
            actor_id="local-user",
            provider="anthropic",
            model="anthropic/claude-sonnet-4-6",
            cost_usd=2.5,
            session_id="session-1",
            run_id="run-1",
            cache_savings_usd=0.4,
            recorded_at=1_744_627_200.0,
        )
        store.record_usage(
            actor_id="local-user",
            provider="openai",
            model="openai/gpt-5.4",
            cost_usd=1.0,
            session_id="session-2",
            run_id="run-2",
            cache_savings_usd=0.0,
            recorded_at=1_744_630_800.0,
        )

        summary = service.get_summary(
            actor_id="local-user",
            monthly_budget_usd=10.0,
            current_session_id="session-1",
            now=1_744_630_800.0,
        )

        assert summary.monthly_cost_usd == 3.5
        assert summary.today_cost_usd == 3.5
        assert summary.session_cost_usd == 2.5
        assert summary.cache_savings_usd == 0.4
        assert summary.month_run_count == 2
        assert summary.warning_level == "ok"
        assert summary.by_model[0]["model"] == "anthropic/claude-sonnet-4-6"

    def test_summary_warns_and_blocks_when_budget_reached(self, tmp_path) -> None:
        store = JsonOrganizationStore(base_dir=tmp_path)
        service = UsageSummaryService(store)

        store.record_usage(
            actor_id="local-user",
            provider="anthropic",
            cost_usd=8.5,
            recorded_at=1_744_630_800.0,
        )

        warning_summary = service.get_summary(
            actor_id="local-user",
            monthly_budget_usd=10.0,
            now=1_744_630_800.0,
        )
        assert warning_summary.warning_level == "warning"
        assert warning_summary.limit_exceeded is False

        store.record_usage(
            actor_id="local-user",
            provider="anthropic",
            cost_usd=1.5,
            recorded_at=1_744_631_000.0,
        )

        exhausted_summary = service.get_summary(
            actor_id="local-user",
            monthly_budget_usd=10.0,
            now=1_744_631_000.0,
        )
        assert exhausted_summary.warning_level == "exhausted"
        assert exhausted_summary.limit_exceeded is True

    def test_summary_uses_configured_warning_threshold(self, tmp_path) -> None:
        store = JsonOrganizationStore(base_dir=tmp_path)
        service = UsageSummaryService(store)

        store.record_usage(
            actor_id="local-user",
            provider="anthropic",
            cost_usd=7.5,
            recorded_at=1_744_630_800.0,
        )

        below_threshold = service.get_summary(
            actor_id="local-user",
            monthly_budget_usd=10.0,
            warning_threshold_pct=90.0,
            now=1_744_630_800.0,
        )
        assert below_threshold.warning_level == "ok"
        assert below_threshold.warning_threshold_pct == 90.0

        at_threshold = service.get_summary(
            actor_id="local-user",
            monthly_budget_usd=10.0,
            warning_threshold_pct=75.0,
            now=1_744_630_800.0,
        )
        assert at_threshold.warning_level == "warning"
        assert at_threshold.warning_threshold_pct == 75.0
