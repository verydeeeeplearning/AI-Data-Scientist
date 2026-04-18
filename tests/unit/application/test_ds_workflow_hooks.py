"""DS workflow hooks tests — leakage, baseline, overfitting, quality, tracking."""

import pytest

from ds_agent.agent.ds_workflow_hooks import (
    BaselineGuardHook,
    LeakageDetectionHook,
    ModelSanityCheckHook,
    OverfittingDetectorHook,
    ProfileResultsHook,
    StageQualityHook,
    WorkflowTrackerHook,
)
from ds_agent.agent.hooks import HookAction, HookContext
from ds_agent.tools.ds_error_translator import translate_error

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _ctx(**kwargs) -> HookContext:
    events: list[tuple[str, dict]] = []
    ctx = HookContext(emit=lambda e, p: events.append((e, p)), **kwargs)
    ctx._events = events  # type: ignore[attr-defined]
    return ctx


# ---------------------------------------------------------------------------
# WorkflowTrackerHook
# ---------------------------------------------------------------------------


class TestWorkflowTracker:
    @pytest.mark.asyncio
    async def test_tracks_stage_on_tool_call(self):
        hook = WorkflowTrackerHook()
        ctx = _ctx()
        await hook.pre_tool_use("data_profiler", {}, ctx)
        assert hook.stages["profiling"] == "running"

        await hook.post_tool_use("data_profiler", {}, "ok", False, ctx)
        assert hook.stages["profiling"] == "done"

    @pytest.mark.asyncio
    async def test_marks_error_on_failure(self):
        hook = WorkflowTrackerHook()
        ctx = _ctx()
        await hook.pre_tool_use("run_eda", {}, ctx)
        await hook.post_tool_use("run_eda", {}, "err", True, ctx)
        assert hook.stages["eda"] == "error"

    @pytest.mark.asyncio
    async def test_ignores_non_ds_tools(self):
        hook = WorkflowTrackerHook()
        ctx = _ctx()
        await hook.pre_tool_use("read_file", {}, ctx)
        # No stage should change
        assert all(s == "pending" for s in hook.stages.values())

    @pytest.mark.asyncio
    async def test_emits_workflow_step_events(self):
        hook = WorkflowTrackerHook()
        ctx = _ctx()
        await hook.pre_tool_use("train_model", {}, ctx)
        await hook.post_tool_use("train_model", {}, "ok", False, ctx)

        events = ctx._events  # type: ignore[attr-defined]
        assert len(events) == 2
        assert events[0][0] == "workflow.step"
        assert events[0][1]["status"] == "running"
        assert events[1][1]["status"] == "done"

    def test_completeness(self):
        hook = WorkflowTrackerHook()
        hook._stages["data_loading"] = "done"
        hook._stages["profiling"] = "done"
        hook._stages["eda"] = "done"
        comp = hook.get_completeness()
        assert comp["completed"] == 3
        assert comp["pct"] == 38  # 3/8
        assert "modeling" in comp["missing"]

    def test_reset(self):
        hook = WorkflowTrackerHook()
        hook._stages["eda"] = "done"
        hook.reset()
        assert hook.stages["eda"] == "pending"


# ---------------------------------------------------------------------------
# LeakageDetectionHook
# ---------------------------------------------------------------------------


class TestLeakageDetection:
    @pytest.mark.asyncio
    async def test_detects_fit_transform_on_test(self):
        hook = LeakageDetectionHook()
        ctx = _ctx()
        code = "scaler.fit_transform(X_test)"
        result = await hook.post_tool_use("feature_engineer", {"code": code}, "ok", False, ctx)
        assert result.modified_result is not None
        assert "Leakage Detection" in result.modified_result

        events = ctx._events  # type: ignore[attr-defined]
        assert len(events) == 1
        assert events[0][0] == "harness.warning"
        assert events[0][1]["type"] == "leakage"

    @pytest.mark.asyncio
    async def test_detects_fit_on_val(self):
        hook = LeakageDetectionHook()
        ctx = _ctx()
        code = "encoder.fit(X_val)"
        result = await hook.post_tool_use("feature_engineer", {"code": code}, "ok", False, ctx)
        assert "Leakage Detection" in (result.modified_result or "")

    @pytest.mark.asyncio
    async def test_passes_clean_code(self):
        hook = LeakageDetectionHook()
        ctx = _ctx()
        code = "scaler.fit(X_train)\nX_test_scaled = scaler.transform(X_test)"
        result = await hook.post_tool_use("feature_engineer", {"code": code}, "ok", False, ctx)
        assert "passed" in (result.modified_result or "")

    @pytest.mark.asyncio
    async def test_ignores_non_fe_tools(self):
        hook = LeakageDetectionHook()
        ctx = _ctx()
        result = await hook.post_tool_use("train_model", {"code": "fit(X_test)"}, "ok", False, ctx)
        assert result.modified_result is None

    @pytest.mark.asyncio
    async def test_ignores_errors(self):
        hook = LeakageDetectionHook()
        ctx = _ctx()
        result = await hook.post_tool_use(
            "feature_engineer", {"code": "fit_transform(X_test)"}, "err", True, ctx
        )
        assert result.modified_result is None


# ---------------------------------------------------------------------------
# BaselineGuardHook
# ---------------------------------------------------------------------------


class TestBaselineGuard:
    @pytest.mark.asyncio
    async def test_warns_when_no_baseline(self):
        hook = BaselineGuardHook()
        ctx = _ctx()
        await hook.pre_tool_use("train_model", {}, ctx)

        events = ctx._events  # type: ignore[attr-defined]
        assert len(events) == 1
        assert events[0][1]["type"] == "baseline_missing"

    @pytest.mark.asyncio
    async def test_no_warn_after_baseline_established(self):
        hook = BaselineGuardHook()
        ctx = _ctx()

        # Establish baseline
        await hook.post_tool_use(
            "train_model",
            {"code": "model = DummyClassifier()\nmodel.fit(X_train, y_train)"},
            "accuracy: 0.65",
            False,
            ctx,
        )
        assert hook.baseline_established is True

        # Now train a real model — no warning expected
        ctx2 = _ctx()
        await hook.pre_tool_use("train_model", {}, ctx2)
        events = ctx2._events  # type: ignore[attr-defined]
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_detects_baseline_via_execute_code(self):
        hook = BaselineGuardHook()
        ctx = _ctx()
        await hook.post_tool_use(
            "execute_code",
            {"code": "baseline = majority_class_accuracy"},
            "0.65",
            False,
            ctx,
        )
        assert hook.baseline_established is True

    @pytest.mark.asyncio
    async def test_allows_tool_execution(self):
        """Baseline guard should warn but never DENY."""
        hook = BaselineGuardHook()
        ctx = _ctx()
        result = await hook.pre_tool_use("train_model", {}, ctx)
        assert result.action == HookAction.ALLOW

    def test_reset(self):
        hook = BaselineGuardHook()
        hook._baseline_established = True
        hook.reset()
        assert hook.baseline_established is False


# ---------------------------------------------------------------------------
# OverfittingDetectorHook
# ---------------------------------------------------------------------------


class TestOverfittingDetector:
    @pytest.mark.asyncio
    async def test_detects_large_gap(self):
        hook = OverfittingDetectorHook()
        ctx = _ctx()
        result_text = "train_accuracy: 0.99\ntest_accuracy: 0.72"
        result = await hook.post_tool_use("train_model", {}, result_text, False, ctx)

        assert result.modified_result is not None
        assert "Overfitting" in result.modified_result
        events = ctx._events  # type: ignore[attr-defined]
        assert events[0][1]["type"] == "overfitting"

    @pytest.mark.asyncio
    async def test_no_warning_for_small_gap(self):
        hook = OverfittingDetectorHook()
        ctx = _ctx()
        result_text = "train_accuracy: 0.88\ntest_accuracy: 0.85"
        result = await hook.post_tool_use("train_model", {}, result_text, False, ctx)
        assert result.modified_result is None

    @pytest.mark.asyncio
    async def test_no_warning_when_no_metrics(self):
        hook = OverfittingDetectorHook()
        ctx = _ctx()
        result = await hook.post_tool_use("train_model", {}, "Model trained.", False, ctx)
        assert result.modified_result is None

    @pytest.mark.asyncio
    async def test_ignores_non_model_tools(self):
        hook = OverfittingDetectorHook()
        ctx = _ctx()
        result = await hook.post_tool_use(
            "run_eda", {}, "train_accuracy: 0.99\ntest_accuracy: 0.50", False, ctx
        )
        assert result.modified_result is None


# ---------------------------------------------------------------------------
# StageQualityHook
# ---------------------------------------------------------------------------


class TestStageQuality:
    @pytest.mark.asyncio
    async def test_scores_modeling_with_baseline(self):
        hook = StageQualityHook()
        ctx = _ctx()
        code = "DummyClassifier cross_val_score lightgbm xgboost"
        result_text = "accuracy: 0.87"
        await hook.post_tool_use("train_model", {"code": code}, result_text, False, ctx)

        assert "modeling" in hook.scores
        assert hook.scores["modeling"] > 0
        events = ctx._events  # type: ignore[attr-defined]
        assert events[0][0] == "quality.update"
        assert events[0][1]["stage"] == "modeling"

    @pytest.mark.asyncio
    async def test_scores_eda_with_stats(self):
        hook = StageQualityHook()
        ctx = _ctx()
        code = "from scipy.stats import ttest_ind\nplt.savefig('plot.png')\nhypothesis: age > 50"
        await hook.post_tool_use("run_eda", {"code": code}, "p-value=0.03", False, ctx)

        assert hook.scores["eda"] >= 50

    @pytest.mark.asyncio
    async def test_critical_penalty_applied(self):
        hook = StageQualityHook()
        ctx = _ctx()
        # Modeling without baseline — CRITICAL fail
        code = "lightgbm cross_val_score"
        await hook.post_tool_use("train_model", {"code": code}, "ok", False, ctx)

        score = hook.scores["modeling"]
        # Has CV (25) + multiple_models partial — but baseline CRITICAL miss → -30
        assert score < 50

    @pytest.mark.asyncio
    async def test_ignores_non_ds_tools(self):
        hook = StageQualityHook()
        ctx = _ctx()
        await hook.post_tool_use("read_file", {"code": ""}, "ok", False, ctx)
        assert len(hook.scores) == 0

    @pytest.mark.asyncio
    async def test_ignores_errors(self):
        hook = StageQualityHook()
        ctx = _ctx()
        await hook.post_tool_use("train_model", {"code": "DummyClassifier"}, "err", True, ctx)
        assert len(hook.scores) == 0

    def test_overall_score(self):
        hook = StageQualityHook()
        hook._scores = {"profiling": 100, "eda": 80, "modeling": 70, "evaluation": 90}
        overall, grade = hook.get_overall_score()
        assert 70 <= overall <= 90
        assert grade in ("A", "B")

    def test_overall_no_scores(self):
        hook = StageQualityHook()
        overall, grade = hook.get_overall_score()
        assert overall == 0
        assert grade == "F"

    def test_reset(self):
        hook = StageQualityHook()
        hook._scores["eda"] = 80
        hook.reset()
        assert len(hook.scores) == 0


# ---------------------------------------------------------------------------
# DS Error Translator
# ---------------------------------------------------------------------------


class TestDSErrorTranslator:
    def test_translates_string_to_float(self):
        err = "ValueError: could not convert string to float: 'Male'"
        result = translate_error(err)
        assert "Diagnosis" in result
        assert "LabelEncoder" in result

    def test_translates_nan_input(self):
        err = "ValueError: Input contains NaN, infinity or a value too large"
        result = translate_error(err)
        assert "Impute" in result or "impute" in result.lower()

    def test_translates_multiclass_binary(self):
        err = "ValueError: Target is multiclass but average='binary'"
        result = translate_error(err)
        assert "weighted" in result or "macro" in result

    def test_translates_inconsistent_samples(self):
        err = "ValueError: Found input variables with inconsistent numbers of samples: [100, 80]"
        result = translate_error(err)
        assert "row count" in result.lower() or "train_test_split" in result

    def test_unknown_error_returns_tail(self):
        err = "line1\nline2\nline3\nline4\nline5\nline6\nline7"
        result = translate_error(err)
        lines = result.strip().split("\n")
        assert len(lines) == 5

    def test_translates_feature_mismatch(self):
        err = (
            "ValueError: Number of features of the model must match "
            "the input. Model n_features is 10 and input n_features is 8"
        )
        result = translate_error(err)
        assert "column" in result.lower() or "feature" in result.lower()

    def test_translates_duplicate_axis(self):
        err = "ValueError: cannot reindex from a duplicate axis"
        result = translate_error(err)
        assert "reset_index" in result

    def test_translates_one_class(self):
        err = "ValueError: Only one class present in y_true"
        result = translate_error(err)
        assert "stratif" in result.lower()


# ---------------------------------------------------------------------------
# ModelSanityCheckHook
# ---------------------------------------------------------------------------


class TestModelSanityCheck:
    @pytest.mark.asyncio
    async def test_passes_normal_result(self):
        hook = ModelSanityCheckHook()
        ctx = _ctx()
        result = await hook.post_tool_use(
            "train_model", {}, "Model trained. Accuracy: 0.85", False, ctx
        )
        assert result.modified_result is not None
        assert "Sanity Checks" in result.modified_result

    @pytest.mark.asyncio
    async def test_detects_collapsed_predictions(self):
        hook = ModelSanityCheckHook()
        ctx = _ctx()
        result = await hook.post_tool_use(
            "train_model",
            {},
            "All predictions are 0. Only one class predicted.",
            False,
            ctx,
        )
        assert result.modified_result is not None
        assert "WARN" in result.modified_result
        events = ctx._events  # type: ignore[attr-defined]
        warning_events = [e for e in events if e[0] == "harness.warning"]
        assert len(warning_events) >= 1

    @pytest.mark.asyncio
    async def test_recognizes_permutation_importance(self):
        hook = ModelSanityCheckHook()
        ctx = _ctx()
        result = await hook.post_tool_use(
            "train_model",
            {},
            "Trained. permutation_importance shows feature_1 is most important",
            False,
            ctx,
        )
        assert result.modified_result is not None
        assert "PASS permutation_test" in result.modified_result

    @pytest.mark.asyncio
    async def test_detects_single_feature_concern(self):
        hook = ModelSanityCheckHook()
        ctx = _ctx()
        result = await hook.post_tool_use(
            "train_model",
            {},
            "single_feature baseline: 0.95, full model: 0.96",
            False,
            ctx,
        )
        assert result.modified_result is not None
        assert "WARN single_feature_baseline" in result.modified_result

    @pytest.mark.asyncio
    async def test_ignores_non_train_tools(self):
        hook = ModelSanityCheckHook()
        ctx = _ctx()
        result = await hook.post_tool_use("run_eda", {}, "ok", False, ctx)
        assert result.modified_result is None

    @pytest.mark.asyncio
    async def test_ignores_errors(self):
        hook = ModelSanityCheckHook()
        ctx = _ctx()
        result = await hook.post_tool_use("train_model", {}, "error", True, ctx)
        assert result.modified_result is None

    @pytest.mark.asyncio
    async def test_emits_quality_update(self):
        hook = ModelSanityCheckHook()
        ctx = _ctx()
        await hook.post_tool_use("train_model", {}, "Model ok", False, ctx)
        events = ctx._events  # type: ignore[attr-defined]
        quality_events = [e for e in events if e[0] == "quality.update"]
        assert len(quality_events) == 1
        assert quality_events[0][1]["stage"] == "modeling"
        assert len(quality_events[0][1]["checks"]) == 3


# ---------------------------------------------------------------------------
# ProfileResultsHook
# ---------------------------------------------------------------------------


class TestProfileResults:
    @pytest.mark.asyncio
    async def test_emits_profile_results(self):
        hook = ProfileResultsHook()
        ctx = _ctx()
        result = "500 rows, 12 columns, missing 3.5%, quality Grade: A"
        await hook.post_tool_use("data_profiler", {}, result, False, ctx)

        events = ctx._events  # type: ignore[attr-defined]
        assert len(events) == 1
        assert events[0][0] == "profile.results"
        payload = events[0][1]
        assert payload["rows"] == 500
        assert payload["columns"] == 12
        assert payload["grade"] == "A"
        assert payload["missingPct"] == 3.5

    @pytest.mark.asyncio
    async def test_ignores_non_profiler_tools(self):
        hook = ProfileResultsHook()
        ctx = _ctx()
        await hook.post_tool_use("run_eda", {}, "some result", False, ctx)
        events = ctx._events  # type: ignore[attr-defined]
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_ignores_errors(self):
        hook = ProfileResultsHook()
        ctx = _ctx()
        await hook.post_tool_use("data_profiler", {}, "error", True, ctx)
        events = ctx._events  # type: ignore[attr-defined]
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_detects_issues(self):
        hook = ProfileResultsHook()
        ctx = _ctx()
        result = "100 rows, 5 columns, high missing values, many outlier detected"
        await hook.post_tool_use("data_profiler", {}, result, False, ctx)
        events = ctx._events  # type: ignore[attr-defined]
        issues = events[0][1]["issues"]
        issue_types = [i["issue"] for i in issues]
        assert "high_missing" in issue_types
        assert "outliers" in issue_types
