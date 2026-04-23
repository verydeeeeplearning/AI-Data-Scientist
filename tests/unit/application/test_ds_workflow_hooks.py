"""DS workflow hooks tests — leakage, baseline, overfitting, quality, tracking."""

from datetime import UTC, datetime

import pytest

from ds_agent.agent.ds_workflow_hooks import (
    DS_WORKFLOW_STAGES,
    TOOL_TO_STAGE,
    BaselineGuardHook,
    LeakageDetectionHook,
    ModelSanityCheckHook,
    OverfittingDetectorHook,
    ProfileResultsHook,
    StageQualityHook,
    WorkflowTrackerHook,
)
from ds_agent.agent.hooks import HookAction, HookContext
from ds_agent.domain.entities.task_contract import DeliverableSpec, TaskContract
from ds_agent.domain.value_objects.analysis_stage import AnalysisStage
from ds_agent.tools.ds_error_translator import translate_error

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


class EventCollectingHookContext(HookContext):
    _events: list[tuple[str, dict]]


def _ctx(**kwargs) -> EventCollectingHookContext:
    events: list[tuple[str, dict]] = []
    ctx = EventCollectingHookContext(emit=lambda e, p: events.append((e, p)), **kwargs)
    ctx._events = events
    return ctx


def _task_contract() -> TaskContract:
    return TaskContract(
        task_id="TC-2026-001",
        session_id="session-1",
        type="analysis",
        business_goal="Clarify the mission before loading data.",
        required_deliverables=[
            DeliverableSpec(type="exec_brief", audience="executive", format="md")
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# WorkflowTrackerHook
# ---------------------------------------------------------------------------


class TestWorkflowTracker:
    def test_stage_vocabulary_matches_canonical_analysis_stage_enum(self):
        assert set(DS_WORKFLOW_STAGES) == {stage.value for stage in AnalysisStage}
        assert set(TOOL_TO_STAGE.values()) <= {stage.value for stage in AnalysisStage}

    @pytest.mark.asyncio
    async def test_emits_plan_created_on_session_init(self):
        hook = WorkflowTrackerHook()
        ctx = _ctx()

        await hook.on_session_init(ctx)

        events = ctx._events
        plan_events = [event for event in events if event[0] == "plan.created"]
        assert len(plan_events) == 1
        assert plan_events[0][1]["planTree"]["id"] == "ds_workflow_plan"
        assert len(plan_events[0][1]["planTree"]["children"]) == len(hook.stages)

    @pytest.mark.asyncio
    async def test_session_init_marks_scoping_done_when_active_task_contract_exists(self):
        hook = WorkflowTrackerHook()
        ctx = _ctx(active_task_contract=_task_contract())

        await hook.on_session_init(ctx)

        assert hook.stages["scoping"] == "done"
        assert hook.current_stage_id() == "scoping"
        assert hook.current_stage_started_at() is not None

        workflow_events = [event for event in ctx._events if event[0] == "workflow.step"]
        plan_updates = [event for event in ctx._events if event[0] == "plan.updated"]

        assert len(workflow_events) == 1
        assert workflow_events[0][1]["stage"] == "scoping"
        assert workflow_events[0][1]["status"] == "done"
        assert len(plan_updates) == 2
        assert plan_updates[0][1]["nodeId"] == "scoping"
        assert plan_updates[1][1]["nodeId"] == "ds_workflow_plan"

    @pytest.mark.asyncio
    async def test_tracks_stage_on_tool_call(self):
        hook = WorkflowTrackerHook()
        ctx = _ctx()
        await hook.pre_tool_use("data_profiler", {}, ctx)
        assert hook.stages["profiling"] == "running"
        assert hook.current_stage_id() == "profiling"
        assert hook.current_stage_started_at() is not None

        await hook.post_tool_use("data_profiler", {}, "ok", False, ctx)
        assert hook.stages["profiling"] == "done"
        assert hook.current_stage_id() == "profiling"

    @pytest.mark.asyncio
    async def test_create_task_contract_maps_to_scoping_stage(self):
        hook = WorkflowTrackerHook()
        ctx = _ctx()

        await hook.pre_tool_use("create_task_contract", {}, ctx)
        assert hook.stages["scoping"] == "running"
        assert hook.current_stage_id() == "scoping"

        await hook.post_tool_use("create_task_contract", {}, "ok", False, ctx)
        assert hook.stages["scoping"] == "done"

    @pytest.mark.asyncio
    async def test_marks_error_on_failure(self):
        hook = WorkflowTrackerHook()
        ctx = _ctx()
        await hook.pre_tool_use("run_eda", {}, ctx)
        await hook.post_tool_use("run_eda", {}, "err", True, ctx)
        assert hook.stages["eda"] == "error"
        assert hook.current_stage_id() == "eda"

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
        await hook.on_session_init(ctx)
        await hook.pre_tool_use("train_model", {}, ctx)
        await hook.post_tool_use("train_model", {}, "ok", False, ctx)

        events = ctx._events
        workflow_events = [event for event in events if event[0] == "workflow.step"]
        plan_updates = [event for event in events if event[0] == "plan.updated"]

        assert len(workflow_events) == 2
        assert len(plan_updates) == 4
        assert plan_updates[0][1]["nodeId"] == "modeling"
        assert plan_updates[1][1]["nodeId"] == "ds_workflow_plan"
        assert workflow_events[0][1]["status"] == "running"
        assert workflow_events[1][1]["status"] == "done"

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
        hook._current_stage_id = "eda"
        hook.reset()
        assert hook.stages["eda"] == "pending"
        assert hook.current_stage_id() is None

    @pytest.mark.asyncio
    async def test_mark_replan_emits_plan_replanned_with_diff(self):
        """mark_replan should emit a plan.replanned event whose diff classifies
        added/removed/modified node ids correctly relative to the previous
        snapshot."""

        hook = WorkflowTrackerHook()
        ctx = _ctx()

        # Establish baseline + take initial snapshot (mimics session init).
        await hook.on_session_init(ctx)
        ctx._events.clear()

        # Mutate the tracker state in two ways:
        # 1) Toggle a stage from pending → running (status change).
        # 2) Append a reasoning ref to another stage (also a node-level mod
        #    via reasoningRefs, but only label/description/status/duration
        #    feed into the diff signature so this should NOT show up as
        #    "modified" — only the status change should).
        hook._stages["profiling"] = "running"
        hook._stage_reasoning_refs["eda"].append("r-001")

        diff_payload = hook.mark_replan(ctx, reason="manual-test")

        replan_events = [event for event in ctx._events if event[0] == "plan.replanned"]
        assert len(replan_events) == 1
        diff = replan_events[0][1]["diff"]
        assert diff["reason"] == "manual-test"
        # status flipped on profiling → that node id is "modified".
        assert "profiling" in diff["modified"]
        # No id was added or removed — the stage list is identical.
        assert diff["added"] == []
        assert diff["removed"] == []
        # Reasoning-only changes do NOT count as a "modified" diff entry per
        # the documented signature contract.
        assert "eda" not in diff["modified"]
        # Returned payload mirrors the emitted payload's "diff" sub-object.
        assert diff_payload is not None
        assert diff_payload["modified"] == diff["modified"]

    @pytest.mark.asyncio
    async def test_record_reasoning_ref_links_to_active_stage(self):
        """record_reasoning_ref appends to the active stage and emits a
        plan.updated patch so the renderer can show the link inline."""

        hook = WorkflowTrackerHook()
        ctx = _ctx()
        await hook.on_session_init(ctx)
        # Drive a stage into the running state via the standard pre_tool_use
        # path so we exercise the same accessor the agent core uses.
        await hook.pre_tool_use("data_profiler", {}, ctx)
        assert hook.current_active_stage_id() == "profiling"

        ctx._events.clear()
        attached_to = hook.record_reasoning_ref(ctx, "r-trace-1")
        assert attached_to == "profiling"
        # Internal state reflects the link.
        assert "r-trace-1" in hook._stage_reasoning_refs["profiling"]

        plan_updates = [event for event in ctx._events if event[0] == "plan.updated"]
        assert len(plan_updates) == 1
        assert plan_updates[0][1]["nodeId"] == "profiling"
        assert plan_updates[0][1]["updates"]["reasoningRefs"] == ["r-trace-1"]

        # Idempotent: a second call with the same id does NOT duplicate the
        # ref or emit another plan.updated patch.
        ctx._events.clear()
        attached_again = hook.record_reasoning_ref(ctx, "r-trace-1")
        assert attached_again == "profiling"
        assert hook._stage_reasoning_refs["profiling"] == ["r-trace-1"]
        assert [event for event in ctx._events if event[0] == "plan.updated"] == []

    @pytest.mark.asyncio
    async def test_record_reasoning_ref_noop_without_active_stage(self):
        """When no stage is running, record_reasoning_ref returns None and
        emits nothing (avoids noisy patches before any tool ran)."""

        hook = WorkflowTrackerHook()
        ctx = _ctx()
        await hook.on_session_init(ctx)
        ctx._events.clear()

        result = hook.record_reasoning_ref(ctx, "r-orphan")
        assert result is None
        assert ctx._events == []

    # ------------------------------------------------------------------
    # Gap 3-2: Stage entry checkpoint emitted in pre_tool_use
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_pre_tool_use_emits_checkpoint_before_workflow_step(self):
        """Gap 3-2: pre_tool_use must emit workflow.checkpoint immediately after
        the stage is set to 'running', before post_tool_use fires.

        This ensures that a crash during a long-running tool does not lose the
        entered stage: any consumer subscribed to workflow.checkpoint writes
        current_stage to durable storage atomically.
        """
        hook = WorkflowTrackerHook()
        ctx = _ctx()

        await hook.pre_tool_use("train_model", {}, ctx)

        checkpoint_events = [e for e in ctx._events if e[0] == "workflow.checkpoint"]
        assert len(checkpoint_events) == 1, (
            "pre_tool_use must emit exactly one workflow.checkpoint event "
            "when a new tracked stage is entered"
        )
        payload = checkpoint_events[0][1]
        assert payload["current_stage"] == "modeling"
        assert payload["status"] == "running"
        assert isinstance(payload["started_at"], int)

        # The checkpoint must appear before the workflow.step event in the
        # event stream so consumers can checkpoint before side-effects propagate.
        event_names = [e[0] for e in ctx._events]
        checkpoint_idx = event_names.index("workflow.checkpoint")
        step_idx = event_names.index("workflow.step")
        assert checkpoint_idx < step_idx, (
            "workflow.checkpoint must be emitted before workflow.step so that "
            "durable persistence happens before UI notification"
        )

    @pytest.mark.asyncio
    async def test_pre_tool_use_no_checkpoint_for_already_running_stage(self):
        """workflow.checkpoint is only emitted on state transitions (pending →
        running or terminal → running), not when the stage is already running."""
        hook = WorkflowTrackerHook()
        ctx = _ctx()

        # First entry: pending → running (should emit checkpoint)
        await hook.pre_tool_use("train_model", {}, ctx)
        checkpoint_count_first = sum(1 for e in ctx._events if e[0] == "workflow.checkpoint")
        assert checkpoint_count_first == 1

        # Force the stage back to running (re-entry from done)
        hook._stages["modeling"] = "done"
        ctx._events.clear()
        await hook.pre_tool_use("train_model", {}, ctx)
        checkpoint_count_reenter = sum(1 for e in ctx._events if e[0] == "workflow.checkpoint")
        assert checkpoint_count_reenter == 1, (
            "Re-entering a terminal stage (done → running) must also emit a checkpoint"
        )

        # Already running: a second pre_tool_use call with same stage already
        # running should NOT emit another checkpoint (the stage stays running).
        hook._stages["modeling"] = "running"
        ctx._events.clear()
        await hook.pre_tool_use("train_model", {}, ctx)
        checkpoint_count_already_running = sum(
            1 for e in ctx._events if e[0] == "workflow.checkpoint"
        )
        assert checkpoint_count_already_running == 0, (
            "No checkpoint is emitted when stage is already in running status"
        )

    # ------------------------------------------------------------------
    # Gap 3-3: current_stage_id semantics — "last entered", not "last completed"
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_current_stage_id_reflects_last_entered_not_last_completed(self):
        """Gap 3-3: current_stage_id() must return the stage of the most recent
        pre_tool_use call, not the most recent post_tool_use call.

        Concretely: if data_loading completes (done) and then profiling starts
        (running), current_stage_id() must return 'profiling' — the stage
        currently being entered — not 'data_loading' (which completed last).
        """
        hook = WorkflowTrackerHook()
        ctx = _ctx()

        # Stage 1: data_loading — full lifecycle
        await hook.pre_tool_use("data_loader", {}, ctx)
        assert hook.current_stage_id() == "data_loading"
        await hook.post_tool_use("data_loader", {}, "ok", False, ctx)
        # After completion, current_stage_id still reflects last *entered* stage.
        assert hook.current_stage_id() == "data_loading"
        assert hook.stages["data_loading"] == "done"

        # Stage 2: profiling — pre only (simulates crash mid-execution)
        await hook.pre_tool_use("data_profiler", {}, ctx)
        # current_stage_id must now point to the newly entered stage.
        assert hook.current_stage_id() == "profiling"
        # data_loading is still done — profiling is running.
        assert hook.stages["data_loading"] == "done"
        assert hook.stages["profiling"] == "running"

    @pytest.mark.asyncio
    async def test_current_stage_id_set_in_pre_not_overwritten_in_post(self):
        """Gap 3-3 regression pin: post_tool_use must NOT overwrite
        _current_stage_id so that the crash-recovery semantics are preserved.

        We verify this by advancing two stages and confirming that after the
        second stage's post_tool_use, current_stage_id() still equals the
        second stage (set in its pre_tool_use), not reverting to the first.
        """
        hook = WorkflowTrackerHook()
        ctx = _ctx()

        await hook.pre_tool_use("run_eda", {}, ctx)
        await hook.post_tool_use("run_eda", {}, "ok", False, ctx)
        # At this point: eda is done, current_stage_id = "eda"
        assert hook.current_stage_id() == "eda"

        await hook.pre_tool_use("feature_engineer", {}, ctx)
        await hook.post_tool_use("feature_engineer", {}, "ok", False, ctx)
        # current_stage_id must be "feature_eng" (set in pre_tool_use of feature_engineer)
        assert hook.current_stage_id() == "feature_eng", (
            "post_tool_use must not overwrite _current_stage_id; "
            "it should remain as the value set in pre_tool_use"
        )


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

        events = ctx._events
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

        events = ctx._events
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
        events = ctx2._events
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
        events = ctx._events
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
        events = ctx._events
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
        events = ctx._events
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
        events = ctx._events
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

        events = ctx._events
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
        events = ctx._events
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_ignores_errors(self):
        hook = ProfileResultsHook()
        ctx = _ctx()
        await hook.post_tool_use("data_profiler", {}, "error", True, ctx)
        events = ctx._events
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_detects_issues(self):
        hook = ProfileResultsHook()
        ctx = _ctx()
        result = "100 rows, 5 columns, high missing values, many outlier detected"
        await hook.post_tool_use("data_profiler", {}, result, False, ctx)
        events = ctx._events
        issues = events[0][1]["issues"]
        issue_types = [i["issue"] for i in issues]
        assert "high_missing" in issue_types
        assert "outliers" in issue_types
