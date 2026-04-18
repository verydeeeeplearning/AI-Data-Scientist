"""Drift analysis tests for PLAN 17 Phase 5."""

from __future__ import annotations

import math

import pandas as pd

from ds_agent.application.services.drift_analyzer import DriftAnalyzer


class TestDriftAnalyzer:
    def test_calculates_known_psi(self):
        analyzer = DriftAnalyzer()

        psi = analyzer.calculate_psi([0.3, 0.3, 0.4], [0.2, 0.3, 0.5])

        assert math.isclose(psi, 0.06286, rel_tol=0.01)

    def test_calculates_kl_divergence(self):
        analyzer = DriftAnalyzer()

        kl = analyzer.calculate_kl_divergence([0.3, 0.3, 0.4], [0.2, 0.3, 0.5])

        assert math.isclose(kl, 0.03238, rel_tol=0.01)

    def test_marks_danger_when_psi_exceeds_threshold(self):
        analyzer = DriftAnalyzer()

        report = analyzer.analyze(
            pd.DataFrame({"stable": [1, 2, 3, 4, 5], "shifted": [0, 0, 0, 0, 0]}),
            pd.DataFrame({"stable": [1, 2, 3, 4, 5], "shifted": [10, 10, 10, 10, 10]}),
        )

        shifted_psi = next(
            metric
            for metric in report.metrics
            if metric.feature_name == "shifted" and metric.metric_type == "PSI"
        )
        assert shifted_psi.level == "danger"
        assert report.overall_status == "danger"

    def test_identifies_top_drifting_features(self):
        analyzer = DriftAnalyzer()

        reference = pd.DataFrame(
            {
                "a": list(range(10)),
                "b": [1] * 10,
                "c": [0, 1] * 5,
            }
        )
        current = pd.DataFrame(
            {
                "a": list(range(10)),
                "b": [100] * 10,
                "c": [0] * 5 + [1] * 5,
            }
        )

        report = analyzer.analyze(reference, current)

        assert report.top_drifting_features[0] == "b"
        assert set(report.top_drifting_features).issubset({"a", "b", "c"})
