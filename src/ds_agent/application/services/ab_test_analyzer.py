"""A/B test analysis services for PLAN 17 Phase 5."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from scipy import stats  # type: ignore[import-untyped]

from ds_agent.domain.value_objects.experiment import (
    EarlyStopDecision,
    ExperimentResult,
    SampleSize,
    SRMResult,
)


class ABTestAnalyzer:
    """Design and analyze experiments with pragmatic statistical defaults."""

    def power_analysis(
        self,
        effect_size: float,
        alpha: float = 0.05,
        power: float = 0.8,
        test_type: str = "proportion",
    ) -> SampleSize:
        """Estimate sample size per group."""
        z_alpha = float(stats.norm.ppf(1 - alpha / 2))
        z_beta = float(stats.norm.ppf(power))
        variance = 0.25 if test_type == "proportion" else 1.0
        n_per_group = math.ceil(2 * variance * ((z_alpha + z_beta) / effect_size) ** 2)
        return SampleSize(
            effect_size=effect_size,
            alpha=alpha,
            power=power,
            n_per_group=n_per_group,
            total_n=n_per_group * 2,
        )

    def srm_check(
        self,
        control_n: int,
        treatment_n: int,
        expected_ratio: tuple[float, float] = (0.5, 0.5),
    ) -> SRMResult:
        """Chi-squared SRM check."""
        total = control_n + treatment_n
        expected = (total * expected_ratio[0], total * expected_ratio[1])
        observed = np.asarray([control_n, treatment_n], dtype=float)
        expected_arr = np.asarray(expected, dtype=float)
        chi2_stat = float(np.sum((observed - expected_arr) ** 2 / expected_arr))
        p_value = float(stats.chi2.sf(chi2_stat, df=1))
        return SRMResult(
            p_value=p_value,
            is_valid=p_value >= 0.05,
            expected_counts=expected,
            observed_counts=(control_n, treatment_n),
        )

    def analyze(
        self,
        control_data: Sequence[float],
        treatment_data: Sequence[float],
        metric_type: str = "continuous",
    ) -> ExperimentResult:
        """Analyze treatment vs control outcomes."""
        control = np.asarray(control_data, dtype=float)
        treatment = np.asarray(treatment_data, dtype=float)
        control_mean = float(control.mean())
        treatment_mean = float(treatment.mean())

        if metric_type in {"binary", "proportion", "conversion"}:
            successes = np.asarray(
                [
                    [float(control.sum()), float(control.size - control.sum())],
                    [float(treatment.sum()), float(treatment.size - treatment.sum())],
                ]
            )
            _chi2, p_value, _dof, _expected = stats.chi2_contingency(successes, correction=False)
            diff = treatment_mean - control_mean
            pooled = (control.sum() + treatment.sum()) / (control.size + treatment.size)
            se = math.sqrt(
                max(
                    pooled * (1 - pooled) * (1 / control.size + 1 / treatment.size),
                    1e-12,
                )
            )
            ci_low = diff - 1.96 * se
            ci_high = diff + 1.96 * se
            effect_size = diff
        else:
            t_stat = stats.ttest_ind(treatment, control, equal_var=False)
            p_value = float(t_stat.pvalue)
            diff = treatment_mean - control_mean
            pooled_std = math.sqrt(
                max(
                    (
                        ((control.size - 1) * float(control.var(ddof=1)))
                        + ((treatment.size - 1) * float(treatment.var(ddof=1)))
                    )
                    / max(control.size + treatment.size - 2, 1),
                    1e-12,
                )
            )
            effect_size = diff / pooled_std
            se = math.sqrt(
                max(
                    float(control.var(ddof=1)) / control.size
                    + float(treatment.var(ddof=1)) / treatment.size,
                    1e-12,
                )
            )
            ci_low = diff - 1.96 * se
            ci_high = diff + 1.96 * se

        is_significant = p_value < 0.05
        winner = "treatment" if is_significant and treatment_mean > control_mean else "control"
        if not is_significant:
            winner = "inconclusive"
        return ExperimentResult(
            metric_type=metric_type,
            control_mean=control_mean,
            treatment_mean=treatment_mean,
            effect_size=float(effect_size),
            p_value=float(p_value),
            ci_low=float(ci_low),
            ci_high=float(ci_high),
            is_significant=is_significant,
            winner=winner,
        )

    def sequential_test(
        self,
        p_value: float,
        look: int = 1,
        max_looks: int = 3,
        alpha: float = 0.05,
        alpha_spending: str = "obrien_fleming",
    ) -> EarlyStopDecision:
        """Simple sequential testing with conservative alpha spending."""
        if alpha_spending == "obrien_fleming":
            adjusted_alpha = alpha / math.sqrt(max(max_looks / max(look, 1), 1.0))
        else:
            adjusted_alpha = alpha / max(max_looks, 1)
        should_stop = p_value < adjusted_alpha
        reason = (
            f"p-value {p_value:.4f} crossed the sequential boundary {adjusted_alpha:.4f}"
            if should_stop
            else f"p-value {p_value:.4f} did not cross the sequential boundary {adjusted_alpha:.4f}"
        )
        return EarlyStopDecision(
            should_stop=should_stop,
            adjusted_alpha=adjusted_alpha,
            reason=reason,
        )
