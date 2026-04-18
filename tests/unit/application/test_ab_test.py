"""A/B testing analysis tests for PLAN 17 Phase 5."""

from __future__ import annotations

from ds_agent.application.services.ab_test_analyzer import ABTestAnalyzer


class TestABTestAnalyzer:
    def test_power_analysis_returns_reasonable_sample_size(self):
        analyzer = ABTestAnalyzer()

        result = analyzer.power_analysis(effect_size=0.05, alpha=0.05, power=0.8)

        assert 1200 <= result.n_per_group <= 2000
        assert result.total_n == result.n_per_group * 2

    def test_srm_check_flags_allocation_mismatch(self):
        analyzer = ABTestAnalyzer()

        result = analyzer.srm_check(control_n=4800, treatment_n=5200, expected_ratio=(0.5, 0.5))

        assert result.p_value < 0.05
        assert result.is_valid is False

    def test_analyze_continuous_experiment(self):
        analyzer = ABTestAnalyzer()

        control = [1.0] * 50 + [1.1] * 50
        treatment = [1.4] * 50 + [1.5] * 50

        result = analyzer.analyze(control, treatment, metric_type="continuous")

        assert result.is_significant is True
        assert result.winner == "treatment"
        assert result.effect_size > 0

    def test_sequential_test_allows_early_stop(self):
        analyzer = ABTestAnalyzer()

        decision = analyzer.sequential_test(p_value=0.001, look=1, max_looks=5)

        assert decision.should_stop is True
        assert decision.adjusted_alpha < 0.05
