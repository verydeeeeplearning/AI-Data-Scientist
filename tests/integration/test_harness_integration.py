"""Integration tests — error translator with sandbox, confidence decay over time."""

import time

from ds_agent.memory.domain_kb import DomainKB
from ds_agent.tools.ds_error_translator import translate_error

# ---------------------------------------------------------------------------
# Error Translator Integration
# ---------------------------------------------------------------------------


class TestErrorTranslatorIntegration:
    """Test error translator handles real-world error formats."""

    def test_full_traceback_string_to_float(self):
        """Real traceback format with multiple lines."""
        traceback = (
            "Traceback (most recent call last):\n"
            '  File "train.py", line 42, in <module>\n'
            "    model.fit(X_train, y_train)\n"
            '  File "sklearn/linear_model/_logistic.py", line 1162, in fit\n'
            "    X, y = self._validate_data(X, y)\n"
            "ValueError: could not convert string to float: 'Male'"
        )
        result = translate_error(traceback)
        assert "Diagnosis" in result
        assert "Categorical" in result or "categorical" in result
        assert "LabelEncoder" in result

    def test_full_traceback_nan(self):
        traceback = (
            "Traceback (most recent call last):\n"
            "  File ...\n"
            "ValueError: Input contains NaN, infinity or a value too large for dtype('float64')."
        )
        result = translate_error(traceback)
        assert "Impute" in result or "impute" in result.lower()
        assert "SimpleImputer" in result

    def test_short_error(self):
        """Short error message still translates."""
        result = translate_error("ValueError: could not convert string to float: 'yes'")
        assert "Diagnosis" in result

    def test_completely_unknown_error(self):
        """Unknown error returns last 5 lines."""
        error = "\n".join(f"line {i}" for i in range(10))
        result = translate_error(error)
        assert "line 9" in result
        assert "line 5" in result

    def test_empty_error(self):
        result = translate_error("")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Confidence Decay Integration
# ---------------------------------------------------------------------------


class TestConfidenceDecayIntegration:
    def test_recent_insight_keeps_high_confidence(self, tmp_path):
        """An insight stored just now should have near-original confidence."""
        kb = DomainKB(data_dir=str(tmp_path / "kb"))
        kb.store_insight("finance", "LightGBM works well for tabular", confidence=0.9)

        insights = kb.get_insights(domain="finance")
        assert len(insights) == 1
        eff = insights[0]["effective_confidence"]
        # Recent → barely decayed
        assert eff > 0.85

    def test_old_insight_has_lower_confidence(self, tmp_path):
        """An insight from 6 months ago should have decayed confidence."""
        kb = DomainKB(data_dir=str(tmp_path / "kb"))
        kb.store_insight("finance", "Old model trick", confidence=0.9)

        # Manually set timestamp to 6 months ago
        domain = kb._profiles["finance"]
        domain["insights"][0]["timestamp"] = time.time() - (180 * 24 * 3600)
        kb._save()

        # Reload
        kb2 = DomainKB(data_dir=str(tmp_path / "kb"))
        insights = kb2.get_insights(domain="finance")
        eff = insights[0]["effective_confidence"]
        # 0.9 * 0.95^6 ≈ 0.66
        assert eff < 0.75
        assert eff > 0.55

    def test_very_old_insight_filtered_in_hints(self, tmp_path):
        """An insight from 2+ years ago should be below 0.3 and filtered out."""
        kb = DomainKB(data_dir=str(tmp_path / "kb"))
        kb.store_insight("finance", "Ancient wisdom", confidence=0.5)

        # Set timestamp to 30 months ago
        domain = kb._profiles["finance"]
        domain["insights"][0]["timestamp"] = time.time() - (900 * 24 * 3600)
        kb._save()

        kb2 = DomainKB(data_dir=str(tmp_path / "kb"))
        hints = kb2.get_memory_hints(domain="finance")
        # 0.5 * 0.95^30 ≈ 0.11 → below 0.3 threshold → filtered
        assert hints == ""

    def test_insights_sorted_by_effective_confidence(self, tmp_path):
        """Newer insights should rank higher than older ones."""
        kb = DomainKB(data_dir=str(tmp_path / "kb"))

        # Store old insight (high raw confidence)
        kb.store_insight("ml", "Old: use SVM", confidence=0.9)
        domain = kb._profiles["ml"]
        domain["insights"][0]["timestamp"] = time.time() - (365 * 24 * 3600)

        # Store recent insight (lower raw confidence)
        kb.store_insight("ml", "New: use LightGBM", confidence=0.7)
        kb._save()

        kb2 = DomainKB(data_dir=str(tmp_path / "kb"))
        insights = kb2.get_insights(domain="ml")

        # Recent insight (0.7 * ~1.0) should rank above old (0.9 * 0.95^12 ≈ 0.49)
        assert "LightGBM" in insights[0]["content"]
        assert "SVM" in insights[1]["content"]

    def test_memory_hints_respects_max_tokens(self, tmp_path):
        """Hints should not exceed max_tokens budget."""
        kb = DomainKB(data_dir=str(tmp_path / "kb"))
        for i in range(20):
            kb.store_insight("ml", f"Insight number {i} with some padding text", confidence=0.9)

        hints = kb.get_memory_hints(domain="ml", max_tokens=50)
        # 50 tokens ≈ 200 chars
        assert len(hints) < 300
