"""PricingTracker tests."""

from ds_agent.domain.entities.messages import Usage
from ds_agent.providers.pricing import PricingTracker


class TestPricingTracker:
    def test_calculate_cost_known_model(self):
        tracker = PricingTracker()
        usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
        cost = tracker.calculate_cost("claude-sonnet-4", usage)
        # claude-sonnet-4: input=$3/M, output=$15/M → $3 + $15 = $18
        assert abs(cost - 18.0) < 0.01

    def test_calculate_cost_with_prefix(self):
        tracker = PricingTracker()
        usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
        cost = tracker.calculate_cost("anthropic/claude-sonnet-4", usage)
        assert abs(cost - 18.0) < 0.01

    def test_calculate_cost_unknown_model_fallback(self):
        tracker = PricingTracker()
        usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
        cost = tracker.calculate_cost("some-unknown-model", usage)
        # Default: input=$1/M, output=$3/M → $1 + $3 = $4
        assert abs(cost - 4.0) < 0.01

    def test_track_cumulative_cost(self):
        tracker = PricingTracker()
        usage1 = Usage(input_tokens=500_000, output_tokens=100_000)
        usage2 = Usage(input_tokens=500_000, output_tokens=100_000)

        cost1 = tracker.track("claude-sonnet-4", usage1)
        cost2 = tracker.track("claude-sonnet-4", usage2)

        assert tracker.total_cost_usd == cost1 + cost2
        assert len(tracker.history) == 2

    def test_pricing_with_cache_discount(self):
        tracker = PricingTracker()
        usage = Usage(
            input_tokens=500_000,
            output_tokens=100_000,
            cache_read_tokens=500_000,
        )
        cost = tracker.calculate_cost("claude-sonnet-4", usage)
        # input: 500K * $3/M = $1.5
        # output: 100K * $15/M = $1.5
        # cache: 500K * $0.3/M = $0.15
        assert abs(cost - 3.15) < 0.01

    def test_get_summary(self):
        tracker = PricingTracker()
        tracker.track("claude-sonnet-4", Usage(input_tokens=100_000, output_tokens=50_000))
        tracker.track("gpt-4o", Usage(input_tokens=100_000, output_tokens=50_000))

        summary = tracker.get_summary()
        assert summary["call_count"] == 2
        assert "claude-sonnet-4" in summary["by_model"]
        assert "gpt-4o" in summary["by_model"]
        assert summary["total_cost_usd"] > 0

    def test_get_summary_includes_cache_savings_and_token_totals(self):
        tracker = PricingTracker()
        tracker.track(
            "claude-sonnet-4",
            Usage(
                input_tokens=100_000,
                output_tokens=50_000,
                cache_read_tokens=50_000,
                cache_write_tokens=10_000,
            ),
        )

        summary = tracker.get_summary()

        assert summary["input_tokens"] == 100_000
        assert summary["output_tokens"] == 50_000
        assert summary["cache_read_tokens"] == 50_000
        assert summary["cache_write_tokens"] == 10_000
        assert summary["cache_savings_usd"] > 0

    def test_versioned_model_matching(self):
        """claude-sonnet-4-20250514 should match claude-sonnet-4 pricing."""
        tracker = PricingTracker()
        usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
        cost = tracker.calculate_cost("anthropic/claude-sonnet-4-20250514", usage)
        assert abs(cost - 18.0) < 0.01

    def test_gpt54_pricing(self):
        tracker = PricingTracker()
        usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
        cost = tracker.calculate_cost("gpt-5.4", usage)
        # gpt-5.4: input=$2.5/M, output=$15/M → $2.5 + $15 = $17.5
        assert abs(cost - 17.5) < 0.01

    def test_chinese_model_pricing(self):
        tracker = PricingTracker()
        usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
        cost = tracker.calculate_cost("deepseek/deepseek-chat", usage)
        # $0.28 + $0.42 = $0.70
        assert abs(cost - 0.70) < 0.01

    def test_free_model_pricing(self):
        tracker = PricingTracker()
        usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
        cost = tracker.calculate_cost("qwen/qwen3.6-plus-preview", usage)
        assert cost == 0.0

    def test_claude_sonnet_46_pricing(self):
        tracker = PricingTracker()
        usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
        cost = tracker.calculate_cost("claude-sonnet-4-6", usage)
        # $3 + $15 = $18
        assert abs(cost - 18.0) < 0.01

    def test_minimax_pricing(self):
        tracker = PricingTracker()
        usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
        cost = tracker.calculate_cost("minimax/MiniMax-M2.5", usage)
        # $0.118 + $0.99 = $1.108
        assert abs(cost - 1.108) < 0.01
