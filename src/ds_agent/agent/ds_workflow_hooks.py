"""DS workflow hooks — automated verification for data science best practices.

Implements harness engineering principle: "enforce via code (hooks), not just docs."
Each hook monitors tool execution and emits events for the frontend UI.
"""

from __future__ import annotations

import re

import structlog

from ds_agent.agent.hooks import (
    HookContext,
    PostToolUseResult,
    PreToolUseResult,
    ToolHook,
)
from ds_agent.application.services.ab_test_analyzer import ABTestAnalyzer
from ds_agent.application.services.drift_analyzer import DriftAnalyzer

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOOL_TO_STAGE: dict[str, str] = {
    "data_loader": "data_loading",
    "data_profiler": "profiling",
    "run_eda": "eda",
    "feature_engineer": "feature_eng",
    "train_model": "modeling",
    "evaluate_model": "evaluation",
    "generate_report": "reporting",
}

DS_WORKFLOW_STAGES: list[str] = [
    "scoping",
    "data_loading",
    "profiling",
    "eda",
    "feature_eng",
    "modeling",
    "evaluation",
    "reporting",
]


# ---------------------------------------------------------------------------
# 1. WorkflowTrackerHook — tracks DS pipeline stage progression
# ---------------------------------------------------------------------------


class WorkflowTrackerHook(ToolHook):
    """Tracks which DS workflow stages have been executed."""

    name = "workflow_tracker"
    priority = 5

    def __init__(self) -> None:
        self._stages: dict[str, str] = {s: "pending" for s in DS_WORKFLOW_STAGES}

    @property
    def stages(self) -> dict[str, str]:
        return dict(self._stages)

    async def pre_tool_use(
        self, tool_name: str, arguments: dict, context: HookContext
    ) -> PreToolUseResult:
        stage = TOOL_TO_STAGE.get(tool_name)
        if stage and self._stages.get(stage) == "pending":
            self._stages[stage] = "running"
            context.emit(
                "workflow.step",
                {"stage": stage, "status": "running", "stages": self._stages},
            )
        return PreToolUseResult()

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        stage = TOOL_TO_STAGE.get(tool_name)
        if stage:
            self._stages[stage] = "error" if is_error else "done"
            context.emit(
                "workflow.step",
                {"stage": stage, "status": self._stages[stage], "stages": self._stages},
            )
        return PostToolUseResult()

    def get_completeness(self) -> dict:
        done = sum(1 for s in self._stages.values() if s == "done")
        total = len(self._stages)
        return {
            "completed": done,
            "total": total,
            "pct": round(done / total * 100) if total else 0,
            "missing": [s for s, v in self._stages.items() if v == "pending"],
        }

    def reset(self) -> None:
        self._stages = {s: "pending" for s in DS_WORKFLOW_STAGES}


# ---------------------------------------------------------------------------
# 2. LeakageDetectionHook — detects data leakage patterns in FE code
# ---------------------------------------------------------------------------

_LEAKAGE_PATTERNS: list[tuple[str, str]] = [
    (
        r"\.fit_transform\(.*(?:X_test|test|val)",
        "fit_transform applied to test/val data — fit on train only, then transform test",
    ),
    (
        r"\.fit\(.*(?:X_test|test|val)",
        "fit() called on test/val data — fit on train only",
    ),
    (
        r"(?:StandardScaler|MinMaxScaler|RobustScaler|LabelEncoder|OneHotEncoder)"
        r".*\.fit\((?!.*train)",
        "Scaler/encoder fit may include non-train data — verify fit uses train only",
    ),
]


class LeakageDetectionHook(ToolHook):
    """Scans feature engineering code for data leakage patterns."""

    name = "leakage_detection"
    priority = 30

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if tool_name != "feature_engineer" or is_error:
            return PostToolUseResult()

        code = arguments.get("code", "")
        warnings = self._scan(code)

        if warnings:
            context.emit(
                "harness.warning",
                {
                    "type": "leakage",
                    "severity": "high",
                    "message": "Data leakage pattern detected",
                    "details": warnings,
                },
            )
            warning_text = "\n\n---\n**Leakage Detection**:\n" + "\n".join(
                f"- {w}" for w in warnings
            )
            return PostToolUseResult(modified_result=result + warning_text)

        return PostToolUseResult(modified_result=result + "\n\n---\n**Leakage check**: passed")

    @staticmethod
    def _scan(code: str) -> list[str]:
        warnings: list[str] = []
        for pattern, message in _LEAKAGE_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                warnings.append(message)
        return warnings


# ---------------------------------------------------------------------------
# 3. BaselineGuardHook — warns if no baseline before model training
# ---------------------------------------------------------------------------


class BaselineGuardHook(ToolHook):
    """Warns when train_model is called without a baseline being established."""

    name = "baseline_guard"
    priority = 25

    def __init__(self) -> None:
        self._baseline_established = False

    @property
    def baseline_established(self) -> bool:
        return self._baseline_established

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if tool_name in ("train_model", "execute_code") and not is_error:
            code = arguments.get("code", "")
            if _has_baseline_keywords(code):
                self._baseline_established = True
        return PostToolUseResult()

    async def pre_tool_use(
        self, tool_name: str, arguments: dict, context: HookContext
    ) -> PreToolUseResult:
        if tool_name == "train_model" and not self._baseline_established:
            context.emit(
                "harness.warning",
                {
                    "type": "baseline_missing",
                    "severity": "medium",
                    "message": "No baseline established before model training",
                    "suggestion": (
                        "Train a DummyClassifier/DummyRegressor first "
                        "to establish a baseline for comparison"
                    ),
                },
            )
        return PreToolUseResult()

    def reset(self) -> None:
        self._baseline_established = False


def _has_baseline_keywords(code: str) -> bool:
    lower = code.lower()
    return any(
        kw in lower
        for kw in [
            "dummyclassifier",
            "dummyregressor",
            "baseline",
            "majority_class",
            "most_frequent",
            "zeroruler",
        ]
    )


# ---------------------------------------------------------------------------
# 4. OverfittingDetectorHook — detects train/test performance gap
# ---------------------------------------------------------------------------

_METRIC_PATTERN = re.compile(
    r"(?:train|training)[\s_]*(?:acc|accuracy|f1|auc|score|rmse|mae|r2)"
    r"[\s:=]*([0-9]*\.?[0-9]+)",
    re.IGNORECASE,
)
_TEST_METRIC_PATTERN = re.compile(
    r"(?:test|val|validation)[\s_]*(?:acc|accuracy|f1|auc|score|rmse|mae|r2)"
    r"[\s:=]*([0-9]*\.?[0-9]+)",
    re.IGNORECASE,
)


class OverfittingDetectorHook(ToolHook):
    """Detects large train-test performance gap indicating overfitting."""

    name = "overfitting_detector"
    priority = 35

    OVERFITTING_THRESHOLD = 0.15  # 15% gap

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if tool_name not in ("train_model", "evaluate_model") or is_error:
            return PostToolUseResult()

        train_score, test_score = self._extract_scores(result)
        if train_score is not None and test_score is not None:
            gap = train_score - test_score
            if gap > self.OVERFITTING_THRESHOLD:
                context.emit(
                    "harness.warning",
                    {
                        "type": "overfitting",
                        "severity": "high",
                        "message": (
                            f"Overfitting detected: train={train_score:.3f}, "
                            f"test={test_score:.3f} (gap={gap:.3f})"
                        ),
                        "suggestion": (
                            "Increase regularization, reduce model complexity, "
                            "or add more training data"
                        ),
                    },
                )
                warning_text = (
                    f"\n\n---\n**Overfitting warning**: "
                    f"train={train_score:.3f}, test={test_score:.3f} (gap={gap:.3f})"
                )
                return PostToolUseResult(modified_result=result + warning_text)

        return PostToolUseResult()

    @staticmethod
    def _extract_scores(text: str) -> tuple[float | None, float | None]:
        train_match = _METRIC_PATTERN.search(text)
        test_match = _TEST_METRIC_PATTERN.search(text)
        train_score = float(train_match.group(1)) if train_match else None
        test_score = float(test_match.group(1)) if test_match else None
        return train_score, test_score


# ---------------------------------------------------------------------------
# 5. StageQualityHook — scores each DS stage based on quality rubric
# ---------------------------------------------------------------------------

_STAGE_CHECKS: dict[str, list[tuple[str, list[str], int, bool]]] = {
    # (check_name, keywords, points, is_critical)
    "profiling": [
        ("missing_analysis", ["missing", "null", "isnull"], 25, False),
        ("distribution_analysis", ["mean", "std", "describe"], 25, False),
        ("outlier_detection", ["outlier", "iqr", "z-score", "boxplot"], 25, False),
        ("quality_grade", ["quality_grade", "grade"], 25, False),
    ],
    "eda": [
        (
            "statistical_test",
            ["ttest", "chi2", "pearsonr", "spearmanr", "f_oneway", "pvalue"],
            30,
            False,
        ),
        ("visualization", ["savefig", "plt.save", "plot"], 20, False),
        ("hypothesis", ["hypothesis", "hypothes", "expect", "predict"], 20, False),
        ("correlation", ["corr()", "heatmap", "pearson"], 15, False),
        ("outlier_analysis", ["outlier", "iqr", "z-score"], 15, False),
    ],
    "feature_eng": [
        ("train_test_split", ["train_test_split", "x_train"], 40, True),
        (
            "encoding",
            ["labelencoder", "onehotencoder", "targetencoder", "get_dummies"],
            20,
            False,
        ),
        ("scaling", ["standardscaler", "minmaxscaler", "robustscaler"], 20, False),
        ("leakage_check", [], 20, True),  # scored by warning absence
    ],
    "modeling": [
        (
            "baseline",
            ["dummyclassifier", "dummyregressor", "baseline", "majority_class"],
            30,
            True,
        ),
        (
            "cross_validation",
            ["cross_val_score", "stratifiedkfold", "kfold", "cross_validate"],
            25,
            False,
        ),
        (
            "multiple_models",
            ["randomforest", "lightgbm", "xgboost", "logistic", "linear"],
            20,
            False,
        ),
        (
            "hyperparameter_tuning",
            ["optuna", "gridsearchcv", "randomizedsearchcv"],
            15,
            False,
        ),
        ("class_imbalance", ["class_weight", "smote", "balanced"], 10, False),
    ],
    "evaluation": [
        ("test_set_eval", ["x_test", "test_data", "holdout"], 30, True),
        (
            "multiple_metrics",
            ["accuracy", "f1", "auc", "rmse", "mae", "precision", "recall"],
            20,
            False,
        ),
        (
            "error_analysis",
            ["confusion_matrix", "residual", "worst_pred", "misclassif"],
            20,
            False,
        ),
        (
            "feature_importance",
            ["shap", "permutation_importance", "feature_importances_"],
            15,
            False,
        ),
        (
            "fairness",
            ["demographic_parity", "equal_opportunity", "protected"],
            15,
            False,
        ),
    ],
    "reporting": [
        ("summary", ["summary", "conclusion", "executive"], 25, False),
        ("limitations", ["limitation", "caveat", "risk", "weakness"], 25, False),
        ("recommendations", ["recommend", "suggestion", "next_step"], 25, False),
        ("model_card", ["model_card", "model card"], 25, False),
    ],
}

# Map tool names to stage quality checks
_TOOL_TO_QUALITY_STAGE: dict[str, str] = {
    "data_profiler": "profiling",
    "run_eda": "eda",
    "feature_engineer": "feature_eng",
    "train_model": "modeling",
    "evaluate_model": "evaluation",
    "generate_report": "reporting",
}


class StageQualityHook(ToolHook):
    """Scores each DS workflow stage based on quality rubric checks."""

    name = "stage_quality"
    priority = 45

    def __init__(self) -> None:
        self._scores: dict[str, int] = {}
        self._checks: dict[str, list[dict]] = {}

    @property
    def scores(self) -> dict[str, int]:
        return dict(self._scores)

    @property
    def all_checks(self) -> dict[str, list[dict]]:
        return dict(self._checks)

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        stage = _TOOL_TO_QUALITY_STAGE.get(tool_name)
        if not stage or is_error:
            return PostToolUseResult()

        code = arguments.get("code", "")
        combined_text = (code + " " + result).lower()

        score, checks = self._score_stage(stage, combined_text)
        self._scores[stage] = score
        self._checks[stage] = checks

        context.emit(
            "quality.update",
            {
                "stage": stage,
                "score": score,
                "checks": checks,
            },
        )
        return PostToolUseResult()

    def get_overall_score(self) -> tuple[int, str]:
        """Compute weighted overall score and grade."""
        weights = {
            "profiling": 0.10,
            "eda": 0.15,
            "feature_eng": 0.15,
            "modeling": 0.25,
            "evaluation": 0.25,
            "reporting": 0.10,
        }
        total = 0.0
        weight_sum = 0.0
        for stage, weight in weights.items():
            if stage in self._scores:
                total += self._scores[stage] * weight
                weight_sum += weight

        overall = round(total / weight_sum) if weight_sum > 0 else 0
        grade = _score_to_grade(overall)
        return overall, grade

    def reset(self) -> None:
        self._scores.clear()
        self._checks.clear()

    @staticmethod
    def _score_stage(stage: str, text: str) -> tuple[int, list[dict]]:
        checks_def = _STAGE_CHECKS.get(stage, [])
        checks: list[dict] = []
        score = 0

        for check_name, keywords, points, critical in checks_def:
            # Special case: leakage_check is scored by absence of warnings
            if check_name == "leakage_check":
                passed = "leakage" not in text or "leakage check" in text
            else:
                passed = any(kw in text for kw in keywords) if keywords else False
            checks.append({"name": check_name, "passed": passed, "critical": critical})
            if passed:
                score += points

        # CRITICAL penalty: -30 per failed critical check
        for check in checks:
            if check.get("critical") and not check["passed"]:
                score = max(0, score - 30)

        return min(100, score), checks


# ---------------------------------------------------------------------------
# 5b. ProfileResultsHook — emits structured profile results for UI
# ---------------------------------------------------------------------------

_ROW_COL_PATTERN = re.compile(r"(\d+)\s*rows?.*?(\d+)\s*col", re.IGNORECASE)
_MISSING_PCT_PATTERN = re.compile(r"missing.*?(\d+(?:\.\d+)?)\s*%", re.IGNORECASE)
_GRADE_PATTERN = re.compile(r"grade[\s:=]*([ABCD])", re.IGNORECASE)


class ProfileResultsHook(ToolHook):
    """Emits structured profile.results event when data_profiler completes."""

    name = "profile_results"
    priority = 46

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if tool_name != "data_profiler" or is_error:
            return PostToolUseResult()

        payload = self._parse_profile(result)
        context.emit("profile.results", payload)
        return PostToolUseResult()

    @staticmethod
    def _parse_profile(text: str) -> dict:
        """Extract structured profile data from profiler output."""
        rows, cols = 0, 0
        rc_match = _ROW_COL_PATTERN.search(text)
        if rc_match:
            rows = int(rc_match.group(1))
            cols = int(rc_match.group(2))

        missing_pct = 0.0
        miss_match = _MISSING_PCT_PATTERN.search(text)
        if miss_match:
            missing_pct = float(miss_match.group(1))

        grade = "C"
        grade_match = _GRADE_PATTERN.search(text)
        if grade_match:
            grade = grade_match.group(1).upper()

        # Extract issue mentions
        issues: list[dict] = []
        issue_keywords = {
            "high_missing": ["high missing", "many null", "> 50% missing"],
            "high_cardinality": ["high cardinality", "unique values"],
            "outliers": ["outlier", "extreme values"],
        }
        for issue_type, keywords in issue_keywords.items():
            if any(kw in text.lower() for kw in keywords):
                issues.append({"issue": issue_type, "detail": issue_type.replace("_", " ")})

        return {
            "summary": text[:500] if len(text) > 500 else text,
            "grade": grade,
            "rows": rows,
            "columns": cols,
            "missingPct": missing_pct,
            "issues": issues,
        }


def _score_to_grade(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# 6. ModelSanityCheckHook — auto sanity checks after model training
# ---------------------------------------------------------------------------

_PREDICTION_DIST_PATTERN = re.compile(
    r"predict(?:ion)?[\s_]*(?:distribution|unique|classes)[\s:=]*(\S+)",
    re.IGNORECASE,
)
_SINGLE_CLASS_PATTERN = re.compile(
    r"(?:all\s+predictions?\s+(?:are|=)\s+\d|only\s+(?:one|1)\s+class\s+predicted)",
    re.IGNORECASE,
)


class ModelSanityCheckHook(ToolHook):
    """Runs 3 automated sanity checks after model training.

    1. **Prediction distribution**: Checks if model predicts multiple classes
       (not collapsed to a single output).
    2. **Permutation test indicator**: Checks if the result mentions
       label shuffling / permutation importance.
    3. **Single-feature baseline**: Checks if single-feature performance
       is suspiciously close to full-model performance (potential leakage).
    """

    name = "model_sanity_check"
    priority = 40

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if tool_name != "train_model" or is_error:
            return PostToolUseResult()

        checks = []

        # Check 1: Prediction distribution — warn if all predictions are same class
        pred_ok = not bool(_SINGLE_CLASS_PATTERN.search(result))
        checks.append(
            {
                "name": "prediction_distribution",
                "passed": pred_ok,
                "detail": (
                    "Predictions span multiple classes"
                    if pred_ok
                    else "Model may predict only one class (collapsed)"
                ),
            }
        )

        # Check 2: Permutation test presence
        perm_keywords = ["permutation_importance", "permutation test", "label_shuffle"]
        perm_ok = any(kw in result.lower() for kw in perm_keywords)
        checks.append(
            {
                "name": "permutation_test",
                "passed": perm_ok,
                "detail": (
                    "Permutation importance computed"
                    if perm_ok
                    else "Consider running permutation importance to validate model"
                ),
            }
        )

        # Check 3: Single-feature baseline — flag if mentioned with suspicious gap
        single_ok = not self._detect_single_feature_concern(result)
        checks.append(
            {
                "name": "single_feature_baseline",
                "passed": single_ok,
                "detail": (
                    "No single-feature dominance detected"
                    if single_ok
                    else "Single feature achieves near-full performance — check for leakage"
                ),
            }
        )

        failed = [c for c in checks if not c["passed"]]
        if failed:
            context.emit(
                "harness.warning",
                {
                    "type": "sanity_check",
                    "severity": "medium",
                    "message": f"{len(failed)} sanity check(s) flagged",
                    "details": [c["detail"] for c in failed],
                },
            )

        context.emit(
            "quality.update",
            {
                "stage": "modeling",
                "checks": checks,
            },
        )

        check_lines = [
            f"{'PASS' if c['passed'] else 'WARN'} {c['name']}: {c['detail']}" for c in checks
        ]
        suffix = "\n\n---\n**Sanity Checks**:\n" + "\n".join(f"- {line}" for line in check_lines)
        return PostToolUseResult(modified_result=result + suffix)

    @staticmethod
    def _detect_single_feature_concern(text: str) -> bool:
        """Return True if text indicates a single feature nearly matches full model."""
        lower = text.lower()
        if "single feature" not in lower and "single_feature" not in lower:
            return False
        # Look for a score >= 0.9 near the single feature mention
        match = re.search(
            r"single[_\s]feature.*?([0-9]+\.[0-9]+)",
            lower,
        )
        if match:
            try:
                score = float(match.group(1))
                return score >= 0.90
            except ValueError:
                pass
        return False


class ExperimentDesignHook(ToolHook):
    """Check SRM and power adequacy for experiment workflows."""

    name = "experiment_design"
    priority = 42

    def __init__(self, analyzer: ABTestAnalyzer | None = None) -> None:
        self._analyzer = analyzer or ABTestAnalyzer()

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if tool_name != "ab_test" or is_error:
            return PostToolUseResult()

        checks: dict[str, dict[str, object]] = {}
        notes: list[str] = []

        control_n = arguments.get("control_n")
        treatment_n = arguments.get("treatment_n")
        if isinstance(control_n, int) and isinstance(treatment_n, int):
            srm = self._analyzer.srm_check(
                control_n=control_n,
                treatment_n=treatment_n,
                expected_ratio=(
                    float(arguments.get("expected_control_ratio", 0.5)),
                    float(arguments.get("expected_treatment_ratio", 0.5)),
                ),
            )
            checks["srm"] = srm.to_dict()
            if not srm.is_valid:
                notes.append(
                    f"SRM failed (p={srm.p_value:.4f}). "
                    "Check traffic allocation before interpreting lift."
                )

        effect_size = arguments.get("effect_size")
        observed_total_n = arguments.get("observed_total_n")
        if isinstance(effect_size, (int, float)) and isinstance(observed_total_n, int):
            required = self._analyzer.power_analysis(
                effect_size=float(effect_size),
                alpha=float(arguments.get("alpha", 0.05)),
                power=float(arguments.get("power", 0.8)),
                test_type=str(arguments.get("test_type", "proportion")),
            )
            checks["power"] = {
                "required_total_n": required.total_n,
                "observed_total_n": observed_total_n,
                "is_sufficient": observed_total_n >= required.total_n,
            }
            if observed_total_n < required.total_n:
                notes.append(
                    "Experiment is underpowered "
                    f"({observed_total_n} < required {required.total_n} total samples)."
                )

        if not notes:
            return PostToolUseResult()

        context.emit("experiment.design_warning", {"checks": checks, "notes": notes})
        suffix = (
            "\n\n---\n**Experiment Design Checks**:\n"
            + "\n".join(f"- {note}" for note in notes)
        )
        return PostToolUseResult(modified_result=result + suffix)


class DriftDetectionHook(ToolHook):
    """Check for drift after evaluation or deployment steps."""

    name = "drift_detection"
    priority = 60

    def __init__(self, analyzer: DriftAnalyzer | None = None) -> None:
        self._analyzer = analyzer or DriftAnalyzer()

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if tool_name not in {"evaluate_model", "deploy_model"} or is_error:
            return PostToolUseResult()

        reference = (
            arguments.get("reference_data")
            or arguments.get("train_data_path")
            or arguments.get("reference_path")
        )
        current = (
            arguments.get("current_data")
            or arguments.get("test_data_path")
            or arguments.get("current_path")
        )
        if reference is None or current is None:
            return PostToolUseResult()

        report = self._analyzer.analyze(reference, current, features=arguments.get("features"))
        if report.overall_status == "ok":
            return PostToolUseResult()

        context.emit("drift.detected", report.to_dict())
        summary = {
            "overall_status": report.overall_status,
            "top_drifting_features": report.top_drifting_features,
            "recommended_action": report.recommended_action,
        }
        suffix = (
            "\n\n---\n**Drift monitoring**:\n"
            f"- status: {summary['overall_status']}\n"
            f"- top features: {', '.join(summary['top_drifting_features'])}\n"
            f"- action: {summary['recommended_action']}"
        )
        return PostToolUseResult(modified_result=result + suffix)
