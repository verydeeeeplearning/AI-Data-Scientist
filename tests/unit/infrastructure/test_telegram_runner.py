"""Tests for gateway/telegram_runner.py."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ds_agent.api.workspace_service import WorkspaceService
from ds_agent.channels.base import DeliveryResult, InboundMessage
from ds_agent.config.loader import load_config
from ds_agent.config.schema import AgentConfig, DSAgentConfig, GatewayConfig, ProviderConfig
from ds_agent.domain.entities.approval import ApprovalStatus
from ds_agent.domain.entities.goal import GoalStatus
from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.domain.entities.runtime_state import RuntimeStatus
from ds_agent.domain.entities.session_checkpoint import SessionCheckpoint
from ds_agent.domain.entities.working_memory import SessionWorkingMemory
from ds_agent.runtime.approval_store import JsonApprovalStore
from ds_agent.runtime.checkpoint_store import JsonCheckpointStore
from ds_agent.runtime.delivery_policy_store import JsonDeliveryPolicyStore
from ds_agent.runtime.goal_store import JsonGoalStore
from ds_agent.runtime.policy_store import JsonPolicyStore
from ds_agent.runtime.run_registry import RunRegistry
from ds_agent.runtime.runtime_event_log import RuntimeEventLog
from ds_agent.runtime.session_registry import RuntimeSessionRegistry
from ds_agent.runtime.task_ledger import TaskLedger
from ds_agent.runtime.transcript_store import JsonTranscriptStore
from ds_agent.runtime.working_memory import JsonWorkingMemoryStore


class TestTelegramCallbacks:
    """Test TelegramCallbacks tool counting and progress messages."""

    @pytest.mark.asyncio
    async def test_tool_count_increments(self):
        from ds_agent.gateway.telegram_runner import TelegramCallbacks

        plugin = MagicMock()
        plugin.send_text = AsyncMock()
        cb = TelegramCallbacks(plugin, "chat1")

        await cb.on_tool_start("tool_a", {})
        await cb.on_tool_start("tool_b", {})
        await cb.on_tool_start("tool_c", {})

        assert cb._tool_count == 3

    @pytest.mark.asyncio
    async def test_sends_progress_every_3(self):
        from ds_agent.gateway.telegram_runner import TelegramCallbacks

        plugin = MagicMock()
        plugin.send_text = AsyncMock()
        cb = TelegramCallbacks(plugin, "chat1")

        for _ in range(3):
            await cb.on_tool_start("tool", {})
        await cb.on_tool_end("tool", "ok", False)

        plugin.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_between(self):
        from ds_agent.gateway.telegram_runner import TelegramCallbacks

        plugin = MagicMock()
        plugin.send_text = AsyncMock()
        cb = TelegramCallbacks(plugin, "chat1")

        await cb.on_tool_start("tool", {})
        await cb.on_tool_end("tool", "ok", False)

        plugin.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_approval_requested_event_includes_context(self, tmp_path):
        from ds_agent.gateway.telegram_runner import TelegramCallbacks

        plugin = MagicMock()
        plugin.send_text = AsyncMock()
        approval_store = JsonApprovalStore(base_dir=tmp_path)
        approval = approval_store.create(
            session_id="telegram:chat1",
            run_id="run-1",
            surface="telegram",
            question="Choose the target column",
            options=["churn", "revenue"],
            default="churn",
        )
        cb = TelegramCallbacks(plugin, "chat1", approval_store=approval_store)

        cb.emit_event(
            "approval.requested",
            {
                "approvalId": approval.approval_id,
                "sessionId": approval.session_id,
                "runId": approval.run_id,
                "question": approval.question,
                "options": approval.options,
                "default": approval.default,
            },
        )
        await asyncio.sleep(0)

        sent = plugin.send_text.call_args[0][0]
        assert "Approval needed" in sent.text
        assert "Session: chat chat1" in sent.text
        assert "Run: run-1" in sent.text
        assert "Queue: 1 / 1" in sent.text
        assert f"/approval {approval.approval_id}" in sent.text


class TestTelegramCommands:
    """Test command handling in TelegramGatewayRunner."""

    def _make_runner(self):
        from ds_agent.gateway.telegram_runner import TelegramGatewayRunner

        runner = TelegramGatewayRunner.__new__(TelegramGatewayRunner)
        runner._plugin = MagicMock()
        runner._plugin.send_text = AsyncMock()
        runner._plugin.send_file = AsyncMock(
            return_value=DeliveryResult(success=True, message_id="9")
        )
        runner._plugin.answer_callback_query = AsyncMock(return_value=True)
        runner._plugin.edit_message_reply_markup = AsyncMock(
            return_value=DeliveryResult(success=True, message_id="9")
        )
        runner._plugin.chunk_text = MagicMock(side_effect=lambda text: [text])
        runner._sessions = MagicMock()
        runner._sessions.active_count.return_value = 2
        runner._transcript_store = JsonTranscriptStore(base_dir=self._tmp_path)
        runner._checkpoint_store = JsonCheckpointStore(base_dir=self._tmp_path)
        runner._approval_store = JsonApprovalStore(base_dir=self._tmp_path)
        runner._goal_store = JsonGoalStore(base_dir=self._tmp_path)
        runner._working_memory_store = JsonWorkingMemoryStore(base_dir=self._tmp_path)
        runner._policy_store = JsonPolicyStore(base_dir=self._tmp_path)
        runner._delivery_policy_store = JsonDeliveryPolicyStore(self._tmp_path)
        runner._runtime_event_log = RuntimeEventLog(base_dir=self._tmp_path)
        runner._workspace = WorkspaceService(str(self._tmp_path))
        runner._config_path = self._tmp_path / "config.yaml"
        runner._runtime_sessions = RuntimeSessionRegistry()
        runner._runs = RunRegistry(runner._runtime_sessions)
        runner._task_ledger = TaskLedger()
        from ds_agent.runtime.action_token import ActionTokenStore
        from ds_agent.runtime.operator_alert_state_store import JsonOperatorAlertStateStore
        from ds_agent.runtime.operator_preferences_store import JsonOperatorPreferencesStore

        runner._preferences = JsonOperatorPreferencesStore(self._tmp_path)
        runner._alert_state = JsonOperatorAlertStateStore(base_dir=self._tmp_path)
        runner._action_tokens = ActionTokenStore()
        runner._delivery_rate_limiter = runner._build_delivery_rate_limiter()
        runner._operator_chats = set()
        runner._delivery_targets = {}
        runner._seen_runtime_event_ids = set()
        runner._config = DSAgentConfig(
            agent=AgentConfig(workspace_dir=str(self._tmp_path)),
            gateway=GatewayConfig(
                autonomous_runtime_enabled=True,
                automation_profile="balanced",
            ),
        )
        return runner

    @pytest.fixture(autouse=True)
    def _setup_tmp(self, tmp_path):
        self._tmp_path = tmp_path

    @pytest.mark.asyncio
    async def test_handle_start(self):
        runner = self._make_runner()
        msg = InboundMessage(
            text="/start",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        runner._plugin.send_text.assert_called_once()
        sent = runner._plugin.send_text.call_args[0][0]
        assert "DS Agent" in sent.text
        assert "/sessions" in sent.text
        assert "/approvals" in sent.text

    @pytest.mark.asyncio
    async def test_handle_help_alias(self):
        runner = self._make_runner()
        msg = InboundMessage(
            text="/help",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "operator bot" in sent.text
        assert "/runs" in sent.text
        assert "/resume" in sent.text
        assert "/alerts" in sent.text

    @pytest.mark.asyncio
    async def test_handle_status(self):
        runner = self._make_runner()
        run = runner._runs.create("telegram:chat1", "telegram", "Analyze churn risk")
        runner._runs.mark_succeeded(run.run_id, "done")
        runner._approval_store.create(
            session_id="telegram:chat1",
            run_id="run-1",
            surface="telegram",
            question="Approve training?",
            options=["yes", "no"],
        )
        msg = InboundMessage(
            text="/status",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "Runtime: enabled (balanced)" in sent.text
        assert "Active sessions: 2" in sent.text
        assert "Pending approvals" in sent.text
        assert "This chat: succeeded" in sent.text

    @pytest.mark.asyncio
    async def test_handle_status_preserves_thread_context(self):
        runner = self._make_runner()
        msg = InboundMessage(
            text="/status",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
            thread_id="77",
        )

        await runner._handle_message(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert sent.thread_id == "77"

    @pytest.mark.asyncio
    async def test_handle_sessions(self):
        runner = self._make_runner()
        run = runner._runs.create("telegram:chat1", "telegram", "Analyze revenue forecast")
        runner._runs.mark_succeeded(run.run_id, "done")
        runner._runtime_sessions.ensure("telegram:chat2", "telegram")
        msg = InboundMessage(
            text="/sessions",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "Recent sessions:" in sent.text
        assert "chat chat1" in sent.text
        assert "succeeded" in sent.text

    @pytest.mark.asyncio
    async def test_handle_runs_defaults_to_current_chat(self):
        runner = self._make_runner()
        current = runner._runs.create("telegram:chat1", "telegram", "Analyze retention cohorts")
        runner._runs.mark_succeeded(current.run_id, "done")
        other = runner._runs.create("telegram:chat9", "telegram", "Ignore this run")
        runner._runs.mark_failed(other.run_id, "failed")
        msg = InboundMessage(
            text="/runs",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "Recent runs (this chat):" in sent.text
        assert current.run_id in sent.text
        assert other.run_id not in sent.text

    @pytest.mark.asyncio
    async def test_handle_runs_isolates_topics_with_same_chat(self):
        runner = self._make_runner()
        current = runner._runs.create("telegram:chat1:77", "telegram", "Topic 77 run")
        runner._runs.mark_succeeded(current.run_id, "done")
        other = runner._runs.create("telegram:chat1:88", "telegram", "Topic 88 run")
        runner._runs.mark_failed(other.run_id, "failed")
        msg = InboundMessage(
            text="/runs",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
            thread_id="77",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert current.run_id in sent.text
        assert other.run_id not in sent.text

    @pytest.mark.asyncio
    async def test_handle_run_detail_defaults_to_latest_chat_run(self):
        runner = self._make_runner()
        run = runner._runs.create("telegram:chat1", "telegram", "Train revenue model")
        runner._runs.mark_failed(run.run_id, "dataset missing target")
        msg = InboundMessage(
            text="/run",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert f"Run: {run.run_id}" in sent.text
        assert "Status: failed" in sent.text
        assert "dataset missing target" in sent.text

    @pytest.mark.asyncio
    async def test_handle_approvals(self):
        runner = self._make_runner()
        approval = runner._approval_store.create(
            session_id="telegram:chat1",
            run_id="run-1",
            surface="telegram",
            question="Ship the current report to stakeholders?",
            options=["yes", "wait"],
            default="wait",
        )
        msg = InboundMessage(
            text="/approvals",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "Pending approvals (this chat):" in sent.text
        assert approval.approval_id in sent.text
        assert "1/1" in sent.text
        assert "default: wait" in sent.text
        assert "Ship the current report" in sent.text

    @pytest.mark.asyncio
    async def test_handle_approvals_isolates_topics_with_same_chat(self):
        runner = self._make_runner()
        current = runner._approval_store.create(
            session_id="telegram:chat1:77",
            run_id="run-77",
            surface="telegram",
            question="Topic 77 approval?",
        )
        other = runner._approval_store.create(
            session_id="telegram:chat1:88",
            run_id="run-88",
            surface="telegram",
            question="Topic 88 approval?",
        )
        msg = InboundMessage(
            text="/approvals",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
            thread_id="77",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert current.approval_id in sent.text
        assert other.approval_id not in sent.text

    @pytest.mark.asyncio
    async def test_handle_approval_detail(self):
        runner = self._make_runner()
        approval = runner._approval_store.create(
            session_id="telegram:chat1",
            run_id="run-77",
            surface="telegram",
            question="Approve the final stakeholder summary?",
            options=["ship", "hold"],
            default="ship",
        )
        msg = InboundMessage(
            text=f"/approval {approval.approval_id}",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert f"Approval: {approval.approval_id}" in sent.text
        assert "Run: run-77" in sent.text
        assert "Queue: 1/1" in sent.text
        assert "Default: ship" in sent.text

    @pytest.mark.asyncio
    async def test_handle_session_summary(self):
        runner = self._make_runner()
        runner._runs.create("telegram:chat1", "telegram", "Analyze pricing")
        runner._checkpoint_store.save(
            SessionCheckpoint(
                session_id="telegram:chat1",
                step=4,
                messages=[
                    ChatMessage(role=Role.USER, content="Analyze pricing"),
                    ChatMessage(role=Role.ASSISTANT, content="Working on elasticity."),
                ],
                updated_at=1234.0,
            )
        )
        runner._goal_store.mark_status(
            "telegram:chat1",
            runner._goal_store.ensure_from_message("telegram:chat1", "Analyze pricing").goal_id,
            GoalStatus.IN_PROGRESS,
            note="Profiling started",
        )
        runner._working_memory_store.save(
            SessionWorkingMemory(
                session_id="telegram:chat1",
                current_summary="Reviewing price sensitivity by segment.",
                next_step="Train the elasticity baseline.",
                recovery_note="Safe to resume from feature review.",
            )
        )
        msg = InboundMessage(
            text="/session",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "Session: chat chat1" in sent.text
        assert "Checkpoint: step 4" in sent.text
        assert "Goal: in_progress" in sent.text
        assert "Next: Train the elasticity baseline." in sent.text

    @pytest.mark.asyncio
    async def test_handle_alerts_digest(self):
        runner = self._make_runner()
        runner._runtime_event_log.record(
            category="recovery",
            kind="recovery.resume_recommended",
            severity="info",
            message="Recovered session can resume.",
            session_id="telegram:chat1",
            surface="daemon",
            source="startup_recovery",
        )
        msg = InboundMessage(
            text="/alerts 1",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "Recent alerts (1):" in sent.text
        assert "recovery.resume_recommended" in sent.text
        assert "Use /ack <event_id>" in sent.text

    @pytest.mark.asyncio
    async def test_handle_notify_supports_category_updates(self):
        runner = self._make_runner()
        msg = InboundMessage(
            text="/notify only approval,recovery",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        pref = runner._preferences.get("chat1")
        assert pref.subscribed_categories == {"approval", "recovery"}
        sent = runner._plugin.send_text.call_args[0][0]
        assert "Subscribed categories saved" in sent.text
        assert "Approvals" in sent.text
        assert "Recoveries" in sent.text

    @pytest.mark.asyncio
    async def test_handle_digest_now_sends_suppressed_summary(self):
        runner = self._make_runner()
        event = runner._runtime_event_log.record(
            category="recovery",
            kind="recovery.resume_recommended",
            severity="warning",
            message="Recovered session can resume.",
            session_id="telegram:chat1",
            surface="daemon",
            source="startup_recovery",
        )
        runner._alert_state.record_suppressed("chat1", event.event_id, "muted")
        msg = InboundMessage(
            text="/digest now",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        assert runner._plugin.send_text.call_count == 2
        digest_sent = runner._plugin.send_text.call_args_list[0][0][0]
        status_sent = runner._plugin.send_text.call_args_list[1][0][0]
        assert "Digest (1 suppressed alerts)" in digest_sent.text
        assert event.event_id in digest_sent.text
        assert status_sent.text == "Digest sent above."

    @pytest.mark.asyncio
    async def test_handle_digest_named_cadence(self):
        runner = self._make_runner()
        msg = InboundMessage(
            text="/digest morning",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        pref = runner._preferences.get("chat1")
        sent = runner._plugin.send_text.call_args[0][0]
        assert pref.digest_mode is True
        assert pref.digest_cadence == "morning"
        assert "morning 09:00" in sent.text

    @pytest.mark.asyncio
    async def test_handle_digest_timezone(self):
        runner = self._make_runner()
        msg = InboundMessage(
            text="/digest timezone Asia/Seoul",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        pref = runner._preferences.get("chat1")
        sent = runner._plugin.send_text.call_args[0][0]
        assert pref.timezone == "Asia/Seoul"
        assert sent.text == "Digest timezone saved: Asia/Seoul."

    @pytest.mark.asyncio
    async def test_handle_mute_updates_alert_state(self):
        runner = self._make_runner()
        msg = InboundMessage(
            text="/mute 30m",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        assert runner._alert_state.is_muted("chat1")
        sent = runner._plugin.send_text.call_args[0][0]
        assert "Muted for 30m" in sent.text

    @pytest.mark.asyncio
    async def test_handle_policy_summary(self):
        runner = self._make_runner()
        runner._policy_store.upsert_recurring_goal(
            session_id="telegram:chat1",
            prompt="Re-run daily churn monitoring.",
            interval_seconds=1800,
        )
        runner._policy_store.set_standing_orders(
            [
                "Do not auto-delete artifacts.",
                "Escalate any failed training run.",
            ]
        )
        delivery_policy = runner._delivery_policy_store.get()
        delivery_policy.digest_enabled = True
        delivery_policy.quiet_hours_start = "22:00"
        delivery_policy.quiet_hours_end = "07:00"
        delivery_policy.quiet_hours_timezone = "Asia/Seoul"
        delivery_policy.escalation_repeat_threshold = 2
        runner._delivery_policy_store.update(delivery_policy)
        runner._workspace.create_project(name="Daily Churn Watch", task_type="classification")
        msg = InboundMessage(
            text="/policy",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "Policy summary" in sent.text
        assert "Autonomy: enabled" in sent.text
        assert "Profile: balanced" in sent.text
        assert "Recurring goals: 1" in sent.text
        assert "Standing orders: 2" in sent.text
        assert "Projects: 1" in sent.text
        assert "Live push policy: on" in sent.text
        assert "Default digest: on (15m)" in sent.text
        assert "Quiet hours: 22:00-07:00 Asia/Seoul" in sent.text
        assert "Escalation: on (threshold 2)" in sent.text

    @pytest.mark.asyncio
    async def test_handle_autonomy_persists_shared_config(self):
        runner = self._make_runner()
        msg = InboundMessage(
            text="/autonomy off",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "Autonomy saved: disabled" in sent.text
        saved = load_config(runner._config_path)
        assert saved.gateway.autonomous_runtime_enabled is False

    @pytest.mark.asyncio
    async def test_handle_profile_persists_shared_config(self):
        runner = self._make_runner()
        msg = InboundMessage(
            text="/profile aggressive",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "Profile saved: aggressive" in sent.text
        saved = load_config(runner._config_path)
        assert saved.gateway.automation_profile == "aggressive"

    @pytest.mark.asyncio
    async def test_handle_goals_summary(self):
        runner = self._make_runner()
        goal = runner._policy_store.upsert_recurring_goal(
            session_id="telegram:chat1",
            prompt="Refresh weekly pricing monitor.",
            interval_seconds=1800,
        )
        msg = InboundMessage(
            text="/goals",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "Recurring goals (1 of 1):" in sent.text
        assert goal.goal_id in sent.text
        assert "30m" in sent.text
        assert "Refresh weekly pricing monitor." in sent.text

    @pytest.mark.asyncio
    async def test_handle_orders_summary(self):
        runner = self._make_runner()
        runner._policy_store.set_standing_orders(
            [
                "Always summarize risk before action.",
                "Ask approval before external delivery.",
            ]
        )
        msg = InboundMessage(
            text="/orders",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "Standing orders (2 of 2):" in sent.text
        assert "Always summarize risk before action." in sent.text
        assert "Ask approval before external delivery." in sent.text

    @pytest.mark.asyncio
    async def test_handle_projects_summary(self):
        runner = self._make_runner()
        project_id = runner._workspace.create_project(
            name="Forecast Ops",
            task_type="forecasting",
        )
        msg = InboundMessage(
            text="/projects",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "Projects (1 of 1):" in sent.text
        assert project_id in sent.text
        assert "Forecast Ops" in sent.text
        assert "forecasting" in sent.text

    @pytest.mark.asyncio
    async def test_handle_project_create_and_detail(self):
        runner = self._make_runner()
        create_msg = InboundMessage(
            text="/project create Retention War Room",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(create_msg)

        created = runner._plugin.send_text.call_args[0][0]
        assert "Project created" in created.text
        created_id = created.text.splitlines()[1].split(": ", maxsplit=1)[1]
        assert runner._workspace.get_project(created_id) is not None

        runner._plugin.send_text.reset_mock()
        detail_msg = InboundMessage(
            text=f"/project {created_id}",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(detail_msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert f"Project: {created_id}" in sent.text
        assert "Name: Retention War Room" in sent.text
        assert "Artifacts: 0" in sent.text

    @pytest.mark.asyncio
    async def test_handle_artifacts_list(self):
        runner = self._make_runner()
        project_id = runner._workspace.create_project(name="Revenue Pack")
        project_dir = runner._workspace.get_project_dir(project_id)
        artifact_path = project_dir / "artifacts" / "report.md"
        artifact_path.write_text("# Revenue report", encoding="utf-8")
        plot_path = project_dir / "plots" / "roc.png"
        plot_path.write_bytes(b"fake-image")
        msg = InboundMessage(
            text=f"/artifacts {project_id}",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "Project files (2 of 2):" in sent.text
        assert "artifacts/report.md" in sent.text
        assert "plots/roc.png" in sent.text

    @pytest.mark.asyncio
    async def test_handle_artifact_send_uses_thread_context(self):
        runner = self._make_runner()
        project_id = runner._workspace.create_project(name="Retention Pack")
        project_dir = runner._workspace.get_project_dir(project_id)
        artifact_path = project_dir / "artifacts" / "summary.md"
        artifact_path.write_text("# Summary", encoding="utf-8")
        msg = InboundMessage(
            text=f"/artifact {project_id} 1",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
            thread_id="91",
        )

        await runner._handle_command(msg)

        first_sent = runner._plugin.send_text.call_args[0][0]
        assert "Sending file" in first_sent.text
        assert first_sent.thread_id == "91"
        runner._plugin.send_file.assert_awaited_once()
        _, kwargs = runner._plugin.send_file.await_args
        assert kwargs["thread_id"] == "91"
        assert kwargs["caption"].startswith("Retention Pack | artifacts/summary.md")

    @pytest.mark.asyncio
    async def test_handle_history_with_limit(self):
        runner = self._make_runner()
        runner._transcript_store.replace_messages(
            "telegram:chat1",
            [
                ChatMessage(role=Role.USER, content="First ask"),
                ChatMessage(role=Role.ASSISTANT, content="First answer"),
                ChatMessage(role=Role.USER, content="Second ask"),
                ChatMessage(role=Role.ASSISTANT, content="Second answer"),
            ],
        )
        msg = InboundMessage(
            text="/history 2",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "Recent history (2):" in sent.text
        assert "Second ask" in sent.text
        assert "Second answer" in sent.text
        assert "First ask" not in sent.text

    @pytest.mark.asyncio
    async def test_handle_history_isolates_topics_with_same_chat(self):
        runner = self._make_runner()
        runner._transcript_store.replace_messages(
            "telegram:chat1:77",
            [
                ChatMessage(role=Role.USER, content="Topic 77 ask"),
                ChatMessage(role=Role.ASSISTANT, content="Topic 77 answer"),
            ],
        )
        runner._transcript_store.replace_messages(
            "telegram:chat1:88",
            [
                ChatMessage(role=Role.USER, content="Topic 88 ask"),
                ChatMessage(role=Role.ASSISTANT, content="Topic 88 answer"),
            ],
        )
        msg = InboundMessage(
            text="/history 2",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
            thread_id="77",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "Topic 77 ask" in sent.text
        assert "Topic 77 answer" in sent.text
        assert "Topic 88 ask" not in sent.text

    @pytest.mark.asyncio
    async def test_handle_stop(self):
        runner = self._make_runner()
        task = asyncio.create_task(asyncio.sleep(10))
        run = runner._runs.create("telegram:chat1", "telegram", "long task")
        task_state = runner._task_ledger.register(run.run_id, task)
        runner._runs.attach_task(run.run_id, task_state.task_id)

        msg = InboundMessage(
            text="/stop",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert f"Stopped run {run.run_id}" in sent.text
        await runner._task_ledger.wait_for_run(run.run_id, timeout_seconds=1.0)

    @pytest.mark.asyncio
    async def test_handle_stop_defaults_to_current_topic_run(self):
        runner = self._make_runner()
        current_task = asyncio.create_task(asyncio.sleep(10))
        current = runner._runs.create("telegram:chat1:77", "telegram", "topic 77 task")
        current_state = runner._task_ledger.register(current.run_id, current_task)
        runner._runs.attach_task(current.run_id, current_state.task_id)

        other_task = asyncio.create_task(asyncio.sleep(10))
        other = runner._runs.create("telegram:chat1:88", "telegram", "topic 88 task")
        other_state = runner._task_ledger.register(other.run_id, other_task)
        runner._runs.attach_task(other.run_id, other_state.task_id)

        msg = InboundMessage(
            text="/stop",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
            thread_id="77",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert f"Stopped run {current.run_id}" in sent.text
        await runner._task_ledger.wait_for_run(current.run_id, timeout_seconds=1.0)
        assert runner._runs.get(other.run_id) is not None
        assert runner._runs.get(other.run_id).status == RuntimeStatus.RUNNING
        other_task.cancel()
        await asyncio.gather(other_task, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_handle_stop_with_explicit_run_id(self):
        runner = self._make_runner()
        task = asyncio.create_task(asyncio.sleep(10))
        run = runner._runs.create("telegram:chat9", "telegram", "background task")
        task_state = runner._task_ledger.register(run.run_id, task)
        runner._runs.attach_task(run.run_id, task_state.task_id)
        msg = InboundMessage(
            text=f"/stop {run.run_id}",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert f"Stopped run {run.run_id}" in sent.text
        await runner._task_ledger.wait_for_run(run.run_id, timeout_seconds=1.0)

    @pytest.mark.asyncio
    async def test_handle_approve_command(self):
        runner = self._make_runner()
        approval = runner._approval_store.create(
            session_id="telegram:chat1",
            run_id="run-1",
            surface="telegram",
            question="Need approval",
        )
        msg = InboundMessage(
            text=f"/approve {approval.approval_id} yes",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "Approval approved" in sent.text
        assert approval.approval_id in sent.text
        assert "Pending left: 0" in sent.text
        resolved = runner._approval_store.get(approval.approval_id)
        assert resolved is not None
        assert resolved.status == ApprovalStatus.APPROVED
        assert resolved.response == "yes"

    @pytest.mark.asyncio
    async def test_handle_reject_command(self):
        runner = self._make_runner()
        approval = runner._approval_store.create(
            session_id="telegram:chat1",
            run_id="run-1",
            surface="telegram",
            question="Need approval",
        )
        msg = InboundMessage(
            text=f"/reject {approval.approval_id} not now",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "Approval rejected" in sent.text
        assert "Pending left: 0" in sent.text
        resolved = runner._approval_store.get(approval.approval_id)
        assert resolved is not None
        assert resolved.status == ApprovalStatus.REJECTED
        assert resolved.response == "not now"

    @pytest.mark.asyncio
    async def test_handle_unknown(self):
        runner = self._make_runner()
        msg = InboundMessage(
            text="/unknown",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        sent = runner._plugin.send_text.call_args[0][0]
        assert "Unknown command" in sent.text

    @pytest.mark.asyncio
    async def test_handle_resume_starts_agent_turn_from_checkpoint(self):
        runner = self._make_runner()
        runner._checkpoint_store.save(
            SessionCheckpoint(
                session_id="telegram:chat1",
                step=3,
                messages=[
                    ChatMessage(role=Role.USER, content="Continue the blocked analysis"),
                ],
                updated_at=1234.0,
            )
        )
        runner._goal_store.mark_status(
            "telegram:chat1",
            runner._goal_store.ensure_from_message(
                "telegram:chat1",
                "Continue the blocked analysis",
            ).goal_id,
            GoalStatus.BLOCKED,
            blocked_reason="Need target confirmation",
        )
        runner._working_memory_store.save(
            SessionWorkingMemory(
                session_id="telegram:chat1",
                current_summary="Target column chosen, ready to continue.",
                next_step="Resume feature validation.",
                recovery_note="Resume from the last blocked checkpoint.",
            )
        )

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Resumed successfully")
        mock_agent._budget = MagicMock()
        mock_agent._budget.state = MagicMock()
        mock_agent._budget.state.total_cost_usd = 0.0
        mock_session = MagicMock()
        mock_session.agent = mock_agent
        mock_session.session_key = "telegram:chat1"
        runner._sessions.get_or_create = AsyncMock(return_value=mock_session)
        runner._plugin.chunk_text = MagicMock(return_value=["Resumed successfully"])

        msg = InboundMessage(
            text="/resume",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        mock_agent.run.assert_called_once()
        resume_prompt = mock_agent.run.call_args.args[0]
        assert "Checkpoint step: 3" in resume_prompt
        assert "Suggested next step: Resume feature validation." in resume_prompt
        assert runner._plugin.send_text.call_count >= 2

    @pytest.mark.asyncio
    async def test_runtime_alert_push_is_deduped(self):
        runner = self._make_runner()
        runner._operator_chats.add("chat1")
        runner._delivery_targets["chat1"] = runner._delivery_target_for_conversation("chat1")
        runner._runtime_event_log.record(
            category="pressure",
            kind="system.resource.pressure",
            severity="warning",
            message="Runtime pressure changed: activeRuns=2, sensorBacklog=4.",
            session_id="autonomous:system",
            surface="daemon",
            source="system_resource",
        )
        runner._runtime_event_log.record(
            category="pressure",
            kind="system.resource.pressure",
            severity="warning",
            message="Runtime pressure changed: activeRuns=2, sensorBacklog=5.",
            session_id="autonomous:system",
            surface="daemon",
            source="system_resource",
        )

        await runner._process_runtime_alerts_once()

        assert runner._plugin.send_text.call_count == 1
        sent = runner._plugin.send_text.call_args[0][0]
        assert "Runtime alert" in sent.text
        assert "Use /alerts" in sent.text

    @pytest.mark.asyncio
    async def test_runtime_alert_push_uses_event_session_topic(self):
        runner = self._make_runner()
        await runner._handle_message(
            InboundMessage(
                text="/status",
                sender_id="user1",
                conversation_id="chat1",
                channel_id="telegram",
                account_id="bot1",
                thread_id="55",
            )
        )
        runner._plugin.send_text.reset_mock()
        runner._runtime_event_log.record(
            category="recovery",
            kind="recovery.resume_recommended",
            severity="warning",
            message="Recovered session can resume.",
            session_id="telegram:chat1:66",
            surface="daemon",
            source="startup_recovery",
        )

        await runner._process_runtime_alerts_once()

        sent = runner._plugin.send_text.call_args[0][0]
        assert sent.thread_id == "66"
        assert sent.reply_markup is not None

    @pytest.mark.asyncio
    async def test_runtime_alert_push_suppresses_and_buffers_for_digest(self):
        runner = self._make_runner()
        runner._operator_chats.add("chat1")
        runner._preferences.set_digest_mode("chat1", True, interval_seconds=900)
        event = runner._runtime_event_log.record(
            category="recovery",
            kind="recovery.resume_recommended",
            severity="warning",
            message="Recovered session can resume.",
            session_id="telegram:chat1",
            surface="daemon",
            source="startup_recovery",
        )

        await runner._process_runtime_alerts_once()

        runner._plugin.send_text.assert_not_called()
        assert runner._alert_state.suppression_reason("chat1", event.event_id) == "digest"

    @pytest.mark.asyncio
    async def test_runtime_alert_push_respects_global_delivery_policy_digest(self):
        runner = self._make_runner()
        runner._operator_chats.add("chat1")
        policy = runner._delivery_policy_store.get()
        policy.live_push_enabled = False
        policy.digest_enabled = True
        runner._delivery_policy_store.update(policy)
        event = runner._runtime_event_log.record(
            category="recovery",
            kind="recovery.resume_recommended",
            severity="warning",
            message="Recovered session can resume.",
            session_id="telegram:chat1",
            surface="daemon",
            source="startup_recovery",
        )

        await runner._process_runtime_alerts_once()

        runner._plugin.send_text.assert_not_called()
        assert runner._alert_state.suppression_reason("chat1", event.event_id) == "digest"

    @pytest.mark.asyncio
    async def test_runtime_alert_push_respects_quiet_hours_policy(self):
        runner = self._make_runner()
        runner._operator_chats.add("chat1")
        current_hour = time.gmtime().tm_hour
        policy = runner._delivery_policy_store.get()
        policy.quiet_hours_start = f"{current_hour:02d}:00"
        policy.quiet_hours_end = f"{(current_hour + 1) % 24:02d}:00"
        policy.quiet_hours_timezone = "UTC"
        runner._delivery_policy_store.update(policy)
        runner._delivery_rate_limiter = runner._build_delivery_rate_limiter()
        event = runner._runtime_event_log.record(
            category="recovery",
            kind="recovery.resume_recommended",
            severity="warning",
            message="Recovered session can resume.",
            session_id="telegram:chat1",
            surface="daemon",
            source="startup_recovery",
        )

        await runner._process_runtime_alerts_once()

        runner._plugin.send_text.assert_not_called()
        assert runner._alert_state.suppression_reason("chat1", event.event_id) == "quiet_hours"

    @pytest.mark.asyncio
    async def test_runtime_alert_push_respects_chat_timezone_for_quiet_hours(self):
        from zoneinfo import ZoneInfo

        runner = self._make_runner()
        runner._operator_chats.add("chat1")
        seoul_now = datetime.now(tz=ZoneInfo("Asia/Seoul"))
        policy = runner._delivery_policy_store.get()
        policy.quiet_hours_start = f"{seoul_now.hour:02d}:00"
        policy.quiet_hours_end = f"{(seoul_now.hour + 1) % 24:02d}:00"
        policy.quiet_hours_timezone = "UTC"
        runner._delivery_policy_store.update(policy)
        runner._preferences.set_timezone("chat1", "Asia/Seoul")
        runner._delivery_rate_limiter = runner._build_delivery_rate_limiter()
        event = runner._runtime_event_log.record(
            category="recovery",
            kind="recovery.resume_recommended",
            severity="warning",
            message="Recovered session can resume.",
            session_id="telegram:chat1",
            surface="daemon",
            source="startup_recovery",
        )

        await runner._process_runtime_alerts_once()

        runner._plugin.send_text.assert_not_called()
        assert runner._alert_state.suppression_reason("chat1", event.event_id) == "quiet_hours"

    @pytest.mark.asyncio
    async def test_runtime_alert_push_escalates_repeated_failures_during_quiet_hours(self):
        runner = self._make_runner()
        runner._operator_chats.add("chat1")
        current_hour = time.gmtime().tm_hour
        policy = runner._delivery_policy_store.get()
        policy.quiet_hours_start = f"{current_hour:02d}:00"
        policy.quiet_hours_end = f"{(current_hour + 1) % 24:02d}:00"
        policy.quiet_hours_timezone = "UTC"
        policy.escalation_repeat_threshold = 2
        runner._delivery_policy_store.update(policy)
        runner._delivery_rate_limiter = runner._build_delivery_rate_limiter()
        first = runner._runtime_event_log.record(
            category="policy",
            kind="policy.dispatch_failed",
            severity="error",
            message="Dispatch attempt 1 failed.",
            session_id="telegram:chat1",
            surface="daemon",
            source="test",
        )
        second = runner._runtime_event_log.record(
            category="policy",
            kind="policy.dispatch_failed",
            severity="error",
            message="Dispatch attempt 2 failed.",
            session_id="telegram:chat1",
            surface="daemon",
            source="test",
        )

        await runner._process_runtime_alerts_once()

        assert runner._alert_state.suppression_reason("chat1", first.event_id) == "quiet_hours"
        assert runner._plugin.send_text.call_count == 1
        sent = runner._plugin.send_text.call_args[0][0]
        assert second.event_id in sent.text

    @pytest.mark.asyncio
    async def test_runtime_alert_push_escalates_repeated_blocked_state_during_quiet_hours(self):
        runner = self._make_runner()
        runner._operator_chats.add("chat1")
        current_hour = time.gmtime().tm_hour
        policy = runner._delivery_policy_store.get()
        policy.quiet_hours_start = f"{current_hour:02d}:00"
        policy.quiet_hours_end = f"{(current_hour + 1) % 24:02d}:00"
        policy.quiet_hours_timezone = "UTC"
        policy.escalation_repeat_threshold = 2
        runner._delivery_policy_store.update(policy)
        runner._delivery_rate_limiter = runner._build_delivery_rate_limiter()
        first = runner._runtime_event_log.record(
            category="recovery",
            kind="recovery.awaiting_approval",
            severity="warning",
            message="Approval is still required before resuming.",
            session_id="telegram:chat1",
            surface="daemon",
            source="test",
        )
        second = runner._runtime_event_log.record(
            category="recovery",
            kind="recovery.awaiting_approval",
            severity="warning",
            message="Approval is still required before resuming.",
            session_id="telegram:chat1",
            surface="daemon",
            source="test",
        )

        await runner._process_runtime_alerts_once()

        assert runner._alert_state.suppression_reason("chat1", first.event_id) == "quiet_hours"
        assert runner._plugin.send_text.call_count == 1
        sent = runner._plugin.send_text.call_args[0][0]
        assert second.event_id in sent.text

    @pytest.mark.asyncio
    async def test_digest_now_uses_curated_digest_builder(self):
        runner = self._make_runner()
        event = runner._runtime_event_log.record(
            category="health",
            kind="pipeline.health.degraded",
            severity="error",
            message="Training pipeline failed on fold 3.",
            session_id="telegram:chat1",
            surface="daemon",
            source="test",
        )
        runner._alert_state.record_suppressed("chat1", event.event_id, "digest")
        msg = InboundMessage(
            text="/digest now",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_command(msg)

        digest_sent = runner._plugin.send_text.call_args_list[0][0][0]
        status_sent = runner._plugin.send_text.call_args_list[1][0][0]
        assert "Unresolved incidents" in digest_sent.text
        assert "pipeline.health.degraded" in digest_sent.text
        assert status_sent.text == "Digest sent above."


class TestTelegramHandleMessage:
    """Test _handle_message routing and agent execution."""

    def _make_runner(self, tmp_path):
        from ds_agent.gateway.telegram_runner import TelegramGatewayRunner

        runner = TelegramGatewayRunner.__new__(TelegramGatewayRunner)
        runner._plugin = MagicMock()
        runner._plugin.send_text = AsyncMock()
        runner._plugin.send_file = AsyncMock(
            return_value=DeliveryResult(success=True, message_id="9")
        )
        runner._plugin.answer_callback_query = AsyncMock(return_value=True)
        runner._plugin.edit_message_reply_markup = AsyncMock(
            return_value=DeliveryResult(success=True, message_id="9")
        )
        runner._plugin.chunk_text = MagicMock(return_value=["Response text"])
        runner._sessions = MagicMock()
        runner._transcript_store = JsonTranscriptStore(base_dir=tmp_path)
        runner._checkpoint_store = JsonCheckpointStore(base_dir=tmp_path)
        runner._approval_store = JsonApprovalStore(base_dir=tmp_path)
        runner._goal_store = JsonGoalStore(base_dir=tmp_path)
        runner._working_memory_store = JsonWorkingMemoryStore(base_dir=tmp_path)
        runner._policy_store = JsonPolicyStore(base_dir=tmp_path)
        runner._delivery_policy_store = JsonDeliveryPolicyStore(tmp_path)
        runner._runtime_event_log = RuntimeEventLog(base_dir=tmp_path)
        runner._workspace = WorkspaceService(str(tmp_path))
        runner._config_path = tmp_path / "config.yaml"
        runner._runtime_sessions = RuntimeSessionRegistry()
        runner._runs = RunRegistry(runner._runtime_sessions)
        runner._task_ledger = TaskLedger()
        from ds_agent.runtime.action_token import ActionTokenStore
        from ds_agent.runtime.operator_alert_state_store import JsonOperatorAlertStateStore
        from ds_agent.runtime.operator_preferences_store import JsonOperatorPreferencesStore

        runner._preferences = JsonOperatorPreferencesStore(tmp_path)
        runner._alert_state = JsonOperatorAlertStateStore(base_dir=tmp_path)
        runner._action_tokens = ActionTokenStore()
        runner._delivery_rate_limiter = runner._build_delivery_rate_limiter()
        runner._operator_chats = set()
        runner._delivery_targets = {}
        runner._seen_runtime_event_ids = set()
        runner._config = DSAgentConfig(
            agent=AgentConfig(workspace_dir=str(tmp_path)),
            gateway=GatewayConfig(
                autonomous_runtime_enabled=True,
                automation_profile="balanced",
            ),
        )
        return runner

    @pytest.mark.asyncio
    async def test_command_message_routes_to_handle_command(self, tmp_path):
        runner = self._make_runner(tmp_path)
        msg = InboundMessage(
            text="/help",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_message(msg)
        runner._plugin.send_text.assert_called()

    @pytest.mark.asyncio
    async def test_plain_message_resolves_pending_approval(self, tmp_path):
        runner = self._make_runner(tmp_path)
        approval = runner._approval_store.create(
            session_id="telegram:chat1",
            run_id="run-1",
            surface="telegram",
            question="Which target?",
        )
        msg = InboundMessage(
            text="target_col",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_message(msg)

        resolved = runner._approval_store.get(approval.approval_id)
        assert resolved is not None
        assert resolved.status == ApprovalStatus.APPROVED
        assert resolved.response == "target_col"
        sent = runner._plugin.send_text.call_args[0][0]
        assert "Approval approved" in sent.text
        assert "Pending left: 0" in sent.text

    @pytest.mark.asyncio
    async def test_plain_message_resolves_pending_approval_for_current_topic_only(self, tmp_path):
        runner = self._make_runner(tmp_path)
        current = runner._approval_store.create(
            session_id="telegram:chat1:77",
            run_id="run-77",
            surface="telegram",
            question="Topic 77 approval?",
        )
        other = runner._approval_store.create(
            session_id="telegram:chat1:88",
            run_id="run-88",
            surface="telegram",
            question="Topic 88 approval?",
        )
        msg = InboundMessage(
            text="topic-77-response",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
            thread_id="77",
        )

        await runner._handle_message(msg)

        resolved = runner._approval_store.get(current.approval_id)
        untouched = runner._approval_store.get(other.approval_id)
        assert resolved is not None
        assert resolved.status == ApprovalStatus.APPROVED
        assert resolved.response == "topic-77-response"
        assert untouched is not None
        assert untouched.status == ApprovalStatus.PENDING

    @pytest.mark.asyncio
    async def test_normal_message_runs_agent(self, tmp_path):
        runner = self._make_runner(tmp_path)

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Analysis complete")
        mock_agent._budget = MagicMock()
        mock_agent._budget.state = MagicMock()
        mock_agent._budget.state.total_cost_usd = 0.0
        mock_session = MagicMock()
        mock_session.agent = mock_agent
        mock_session.session_key = "telegram:chat1"
        runner._sessions.get_or_create = AsyncMock(return_value=mock_session)

        msg = InboundMessage(
            text="Analyze my data",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_message(msg)

        mock_agent.run.assert_called_once_with("Analyze my data")
        assert runner._plugin.send_text.call_count >= 2

    @pytest.mark.asyncio
    async def test_normal_message_uses_thread_aware_session_lookup(self, tmp_path):
        runner = self._make_runner(tmp_path)

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Analysis complete")
        mock_agent._budget = MagicMock()
        mock_agent._budget.state = MagicMock()
        mock_agent._budget.state.total_cost_usd = 0.0
        mock_session = MagicMock()
        mock_session.agent = mock_agent
        mock_session.session_key = "telegram:chat1:77"
        runner._sessions.get_or_create = AsyncMock(return_value=mock_session)

        msg = InboundMessage(
            text="Analyze my data",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
            thread_id="77",
        )

        await runner._handle_message(msg)

        _, kwargs = runner._sessions.get_or_create.await_args
        assert kwargs["thread_id"] == "77"

    @pytest.mark.asyncio
    async def test_agent_error_sends_error_message(self, tmp_path):
        runner = self._make_runner(tmp_path)

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=RuntimeError("LLM crashed"))
        mock_session = MagicMock()
        mock_session.agent = mock_agent
        mock_session.session_key = "telegram:chat1"
        runner._sessions.get_or_create = AsyncMock(return_value=mock_session)
        runner._plugin.chunk_text = MagicMock(return_value=["Error: LLM crashed"])

        msg = InboundMessage(
            text="Analyze data",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_message(msg)

        assert runner._plugin.send_text.call_count >= 2

    @pytest.mark.asyncio
    async def test_chunked_response(self, tmp_path):
        runner = self._make_runner(tmp_path)

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Very long response")
        mock_agent._budget = MagicMock()
        mock_agent._budget.state = MagicMock()
        mock_agent._budget.state.total_cost_usd = 0.0
        mock_session = MagicMock()
        mock_session.agent = mock_agent
        mock_session.session_key = "telegram:chat1"
        runner._sessions.get_or_create = AsyncMock(return_value=mock_session)
        runner._plugin.chunk_text = MagicMock(return_value=["chunk1", "chunk2", "chunk3"])

        msg = InboundMessage(
            text="Analyze",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_message(msg)

        assert runner._plugin.send_text.call_count == 4

    @pytest.mark.asyncio
    async def test_execute_agent_turn_announces_run_with_inline_markup(self, tmp_path):
        runner = self._make_runner(tmp_path)

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Analysis complete")
        mock_agent._budget = MagicMock()
        mock_agent._budget.state = MagicMock()
        mock_agent._budget.state.total_cost_usd = 0.0
        mock_session = MagicMock()
        mock_session.agent = mock_agent
        mock_session.session_key = "telegram:chat1"
        runner._sessions.get_or_create = AsyncMock(return_value=mock_session)

        msg = InboundMessage(
            text="Analyze my data",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_message(msg)

        first_sent = runner._plugin.send_text.call_args_list[0][0][0]
        assert "Run:" in first_sent.text
        assert first_sent.reply_markup is not None

    @pytest.mark.asyncio
    async def test_execute_agent_turn_auto_delivers_selected_artifacts(self, tmp_path):
        runner = self._make_runner(tmp_path)
        project_id = runner._workspace.create_project(name="Revenue Pack")
        project_dir = runner._workspace.get_project_dir(project_id)
        artifact_path = project_dir / "artifacts" / "summary.md"
        artifact_path.write_text("# Summary", encoding="utf-8")

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Analysis complete")
        mock_agent._budget = MagicMock()
        mock_agent._budget.state = MagicMock()
        mock_agent._budget.state.total_cost_usd = 0.0
        mock_session = MagicMock()
        mock_session.agent = mock_agent
        mock_session.session_key = "telegram:chat1"
        runner._sessions.get_or_create = AsyncMock(return_value=mock_session)

        msg = InboundMessage(
            text="Analyze my data",
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
        )

        await runner._handle_message(msg)

        runner._plugin.send_file.assert_awaited_once()
        _, kwargs = runner._plugin.send_file.await_args
        assert kwargs["thread_id"] is None
        assert kwargs["caption"].startswith(project_id)

    @pytest.mark.asyncio
    async def test_callback_query_rejects_wrong_actor(self, tmp_path):
        from ds_agent.runtime.action_token import ACTION_STOP

        runner = self._make_runner(tmp_path)
        token = runner._action_tokens.create(
            ACTION_STOP,
            "run-1",
            actor="owner",
            chat_id="chat1",
        )
        msg = InboundMessage(
            text=token,
            sender_id="intruder",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
            callback_data=token,
            callback_query_id="query-1",
            source_message_id="10",
        )

        await runner._handle_message(msg)

        runner._plugin.answer_callback_query.assert_awaited_once()
        _, kwargs = runner._plugin.answer_callback_query.await_args
        assert kwargs["show_alert"] is True
        assert "original operator" in kwargs["text"]
        runner._plugin.edit_message_reply_markup.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_callback_query_acknowledges_alert(self, tmp_path):
        from ds_agent.runtime.action_token import ACTION_ACK

        runner = self._make_runner(tmp_path)
        event = runner._runtime_event_log.record(
            category="pressure",
            kind="system.resource.pressure",
            severity="warning",
            message="Runtime pressure changed.",
            session_id="telegram:chat1",
            surface="daemon",
            source="system_resource",
        )
        token = runner._action_tokens.create(
            ACTION_ACK,
            event.event_id,
            chat_id="chat1",
        )
        msg = InboundMessage(
            text=token,
            sender_id="user1",
            conversation_id="chat1",
            channel_id="telegram",
            account_id="bot1",
            callback_data=token,
            callback_query_id="query-2",
            source_message_id="11",
        )

        await runner._handle_message(msg)

        assert runner._alert_state.is_acknowledged("chat1", event.event_id)
        runner._plugin.edit_message_reply_markup.assert_awaited_once()
        sent = runner._plugin.send_text.call_args[0][0]
        assert f"Acknowledged: {event.event_id}" in sent.text


class TestTelegramImportTools:
    def test_import_tools_does_not_crash(self):
        from ds_agent.gateway.telegram_runner import TelegramGatewayRunner

        TelegramGatewayRunner._import_tools()


class TestTelegramCreateAgent:
    def test_create_agent_uses_shared_provider_factory(self):
        from ds_agent.gateway.telegram_runner import TelegramGatewayRunner

        runner = TelegramGatewayRunner.__new__(TelegramGatewayRunner)
        runner._plugin = MagicMock()
        runner._token_store = MagicMock()
        runner._transcript_store = MagicMock()
        runner._checkpoint_store = MagicMock()
        runner._approval_store = MagicMock()
        from ds_agent.runtime.action_token import ActionTokenStore

        runner._action_tokens = ActionTokenStore()
        runner._config = DSAgentConfig(
            provider=ProviderConfig(default_model="codex/gpt-5.4"),
            agent=AgentConfig(workspace_dir="C:/workspace"),
        )
        mock_provider = MagicMock()
        mock_agent = MagicMock()

        with (
            patch(
                "ds_agent.runtime.provider_factory.create_provider_router",
                return_value=mock_provider,
            ) as mock_provider_factory,
            patch(
                "ds_agent.gateway.telegram_runner.create_agent", return_value=mock_agent
            ) as mock_create_agent,
        ):
            agent = runner._create_agent("chat-1")

        assert agent is mock_agent
        mock_provider_factory.assert_called_once_with(
            "codex/gpt-5.4",
            runner._config,
            token_store=runner._token_store,
        )
        assert mock_create_agent.call_args.kwargs["session_id"] == "telegram:chat-1"
        assert mock_create_agent.call_args.kwargs["approval_store"] is runner._approval_store
