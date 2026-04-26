"""Telegram gateway runner that connects Telegram conversations to DSAgent."""

from __future__ import annotations

import asyncio
import time
import typing
from dataclasses import dataclass
from pathlib import Path

import structlog

from ds_agent.agent.callbacks import NullCallbacks
from ds_agent.agent.core import DSAgent
from ds_agent.agent.factory import create_agent
from ds_agent.api.workspace_service import WorkspaceService
from ds_agent.application.dtos.task_contract import TaskContractUpdateDTO, TaskContractViewDTO
from ds_agent.application.learning.harness_warning_ingestor import HarnessWarningIngestor
from ds_agent.application.use_cases.check_quiet_hours_usecase import (
    CheckQuietHoursUseCase,
    QuietHoursPolicyPort,
)
from ds_agent.application.use_cases.send_notification_usecase import (
    NotificationTransportPort,
    SendNotificationUseCase,
)
from ds_agent.channels.base import OutboundMessage
from ds_agent.channels.bundled.telegram.callback_handler import (
    CALLBACK_PREFIX,
    ApprovalSubmitOutcome,
    CallbackParseError,
    TelegramApprovalCallbackHandler,
    parse_approval_callback,
)
from ds_agent.channels.bundled.telegram.message_builder import (
    BuiltMessage,
    TelegramMessageBuilder,
)
from ds_agent.channels.bundled.telegram.plugin import TelegramPlugin
from ds_agent.config.loader import get_default_config_path, save_config
from ds_agent.config.schema import DSAgentConfig
from ds_agent.domain.entities.approval import ApprovalRequest, ApprovalStatus
from ds_agent.domain.entities.goal import GoalRecord
from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.domain.entities.review_verdict import ReviewVerdict
from ds_agent.domain.entities.runtime_state import RunState, RuntimeStatus
from ds_agent.domain.entities.session_checkpoint import SessionCheckpoint
from ds_agent.domain.entities.shadow_comparison import ShadowComparisonRecord
from ds_agent.domain.entities.task_contract import TaskContractStatus
from ds_agent.domain.entities.working_memory import SessionWorkingMemory
from ds_agent.domain.errors.task_contract_errors import TaskContractError, TaskContractNotFoundError
from ds_agent.domain.notification import (
    InlineButton,
    Notification,
    NotificationCategory,
    QuietHours,
    QuietHoursPolicy,
)
from ds_agent.gateway.session_manager import SessionManager
from ds_agent.gateway.telegram_strings import telegram_string
from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore
from ds_agent.infrastructure.task_contract_container import (
    TaskContractContainer,
    build_task_contract_container,
)
from ds_agent.infrastructure.verifier_container import VerifierContainer, build_verifier_container
from ds_agent.presentation.certification_presenters import (
    render_certification_status,
    render_certification_submission,
)
from ds_agent.presentation.shadow_comparison_presenters import (
    render_shadow_comparison_report,
)
from ds_agent.presentation.task_contract_presenters import render_task_contract_summary
from ds_agent.presentation.verdict_presenters import (
    pick_effective_review_verdict,
    render_verdict_report,
)
from ds_agent.runtime.action_token import (
    ACTION_ACK,
    ACTION_APPROVE,
    ACTION_INSPECT,
    ACTION_MUTE,
    ACTION_REJECT,
    ACTION_RESUME,
    ACTION_STOP,
    ActionTokenStore,
    action_label,
)
from ds_agent.runtime.approval_store import JsonApprovalStore
from ds_agent.runtime.channel_identity import parse_telegram_session_id, telegram_session_id
from ds_agent.runtime.checkpoint_store import JsonCheckpointStore
from ds_agent.runtime.deferred_notification_store import JsonDeferredNotificationStore
from ds_agent.runtime.delivery_policy_store import DeliveryPolicy, JsonDeliveryPolicyStore
from ds_agent.runtime.delivery_rate_limiter import DeliveryRateLimiter, QuietHoursWindow
from ds_agent.runtime.delivery_settings import (
    EffectiveDeliverySettings,
    resolve_effective_delivery_settings,
)
from ds_agent.runtime.digest_builder import build_digest_from_events
from ds_agent.runtime.event_classifier import (
    ClassifiedEvent,
    DeliveryDecision,
    classify_event,
    evaluate_delivery,
)
from ds_agent.runtime.goal_store import JsonGoalStore
from ds_agent.runtime.operator_alert_state_store import JsonOperatorAlertStateStore
from ds_agent.runtime.operator_preferences_store import (
    DEFAULT_NOTIFICATION_CATEGORIES,
    JsonOperatorPreferencesStore,
    digest_cadence_label,
)
from ds_agent.runtime.outcome_delivery import select_outcome_deliverables
from ds_agent.runtime.policy_store import JsonPolicyStore
from ds_agent.runtime.provider_factory import create_auth_profile_store
from ds_agent.runtime.run_registry import RunRegistry
from ds_agent.runtime.runtime_event_log import RuntimeEventLog, RuntimeEventRecord
from ds_agent.runtime.session_registry import RuntimeSessionRegistry
from ds_agent.runtime.task_ledger import TaskLedger
from ds_agent.runtime.transcript_store import JsonTranscriptStore
from ds_agent.runtime.working_memory import JsonWorkingMemoryStore

logger = structlog.get_logger()
_AUTOMATION_PROFILES = {"manual", "balanced", "aggressive"}
_MOBILE_LIST_LIMIT = 5
_DEFAULT_HISTORY_LIMIT = 6
_MAX_HISTORY_LIMIT = 12
_DEFAULT_ALERT_LIMIT = 5
_MAX_ALERT_LIMIT = 10
_ALERT_POLL_INTERVAL_SECONDS = 5.0
_ACK_ACTION_MUTE_WINDOW = "30m"
_SEVERITY_ORDER = ("info", "warning", "error", "critical")
_DEFAULT_DEEP_LINK_WORKSPACE_ID = "default"
_NOTIFICATION_CATEGORY_LABELS: dict[str, str] = {
    "approval": "Approvals",
    "recovery": "Recoveries",
    "health": "Health",
    "pressure": "Resource Pressure",
    "policy": "Policy",
    "operator_action": "Operator Audit",
}
_NOTIFICATION_CATEGORY_ALIASES: dict[str, str] = {
    "approval": "approval",
    "approvals": "approval",
    "recoveries": "recovery",
    "recovery": "recovery",
    "health": "health",
    "pressure": "pressure",
    "policy": "policy",
    "audit": "operator_action",
    "operator": "operator_action",
    "operator_action": "operator_action",
}
_TASK_CONTRACT_INCLUDE = [
    "goal_brief",
    "metric_specs",
    "dataset_manifest",
    "assumption_log",
    "review_verdicts",
    "delivery_pack",
]


@dataclass(frozen=True, slots=True)
class TelegramDeliveryTarget:
    """Preferred Telegram delivery destination for one chat."""

    conversation_id: str
    thread_id: str | None = None


class _TelegramApprovalSubmitter:
    """Adapter that bridges Telegram callback handler to the approval use case."""

    def __init__(self, runner: TelegramGatewayRunner) -> None:
        self._runner = runner

    async def submit(
        self,
        *,
        approval_id: str,
        decision: str,
        operator_id: str,
        reason: str | None,
    ) -> ApprovalSubmitOutcome:
        return await self._runner._submit_approval_callback(
            approval_id=approval_id,
            decision=decision,
            operator_id=operator_id,
            reason=reason,
        )


class _DeliveryPolicyQuietHoursPort(QuietHoursPolicyPort):
    """Adapter: read quiet-hours window from the runtime delivery policy.

    Translates the wire-level :class:`DeliveryPolicy` (string hours / tz)
    into the domain :class:`QuietHoursPolicy` consumed by the use case.
    Operator-specific overrides are not yet wired through delivery policy,
    so the same window applies to every operator until per-chat overrides
    land in PLAN_04 follow-up.
    """

    def __init__(self, policy_store: JsonDeliveryPolicyStore) -> None:
        self._policy_store = policy_store

    def load(self, *, operator_id: str) -> QuietHoursPolicy:
        policy = self._policy_store.get()
        start = TelegramGatewayRunner._parse_quiet_hour(policy.quiet_hours_start)
        end = TelegramGatewayRunner._parse_quiet_hour(policy.quiet_hours_end)
        if start is None or end is None:
            return QuietHoursPolicy(
                window=QuietHours(
                    timezone_name=policy.quiet_hours_timezone or "UTC",
                    start_hour=0,
                    end_hour=0,
                    enabled=False,
                )
            )
        return QuietHoursPolicy(
            window=QuietHours(
                timezone_name=policy.quiet_hours_timezone or "UTC",
                start_hour=start,
                end_hour=end,
                enabled=True,
            )
        )


class _NullNotificationTransport(NotificationTransportPort):
    """Sync no-op transport used purely to satisfy the use case port.

    The actual async Telegram I/O lives on the runner; this adapter only
    exists so the use case stays framework-free.  ``dispatch_notification``
    inspects :class:`SendNotificationResult` and performs the live send
    itself when ``delivered=True``.
    """

    def deliver(self, *, operator_id: str, notification: Notification) -> str:
        return f"deferred-decision:{operator_id}"


class TelegramCallbacks(NullCallbacks):
    """Callbacks that send lightweight progress updates to Telegram."""

    def __init__(
        self,
        plugin: TelegramPlugin,
        chat_id: str,
        thread_id: str | None = None,
        approval_store: JsonApprovalStore | None = None,
        action_tokens: ActionTokenStore | None = None,
        workspace_dir: str | None = None,
        warning_ingestor: HarnessWarningIngestor | None = None,
    ) -> None:
        self._plugin = plugin
        self._chat_id = chat_id
        self._thread_id = thread_id
        self._approval_store = approval_store
        self._action_tokens = action_tokens
        self._tool_count = 0
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._warning_ingestor = warning_ingestor
        if self._warning_ingestor is None and workspace_dir is not None:
            self._warning_ingestor = HarnessWarningIngestor(
                SqliteLearningStore.for_workspace(workspace_dir)
            )
        self._current_session_id = telegram_session_id(chat_id, thread_id)
        self._current_run_id: str | None = None
        self._surface = "telegram"

    async def on_tool_start(self, tool_name: str, arguments: dict) -> None:
        self._tool_count += 1

    async def on_tool_end(self, tool_name: str, result: str, is_error: bool) -> None:
        if self._tool_count % 3 == 0:
            await self._plugin.send_text(
                OutboundMessage(
                    text=f"Working... ({self._tool_count} tool calls)",
                    conversation_id=self._chat_id,
                    thread_id=self._thread_id,
                    parse_mode="",
                )
            )

    def emit_event(self, event: str, payload: dict) -> None:
        self._remember_runtime_context(payload)
        self._ingest_warning_if_needed(event, payload)
        if event not in {"approval.requested", "approval.resolved"}:
            return

        async def _send() -> None:
            if event == "approval.requested":
                options = payload.get("options") or []
                default = payload.get("default")
                approval_id = str(payload.get("approvalId", ""))
                session_id = str(payload.get("sessionId", ""))
                run_id = payload.get("runId")
                queue_text = self._queue_text(approval_id)
                lines = [
                    "Approval needed",
                    f"ID: {approval_id}",
                    f"Session: {self._display_session(session_id)}",
                    f"Run: {run_id or '-'}",
                    f"Question: {payload.get('question', '')}",
                ]
                if queue_text:
                    lines.append(queue_text)
                if options:
                    lines.append(f"Options: {', '.join(str(item) for item in options[:4])}")
                if isinstance(default, str):
                    lines.append(f"Default: {default}")
                lines.append(
                    "Reply in plain text, or use /approval "
                    f"{approval_id} / /approve {approval_id} <response>."
                )
                text = "\n".join(lines)
                markup = None
                if approval_id:
                    markup = {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "Approve",
                                    "callback_data": f"{CALLBACK_PREFIX}:approve:{approval_id}",
                                },
                                {
                                    "text": "Reject",
                                    "callback_data": f"{CALLBACK_PREFIX}:reject:{approval_id}",
                                },
                            ],
                        ],
                    }
            else:
                markup = None
                lines = [
                    "Approval resolved",
                    f"ID: {payload.get('approvalId')}",
                    f"Session: {self._display_session(str(payload.get('sessionId', '')))}",
                    f"Run: {payload.get('runId') or '-'}",
                    f"Status: {payload.get('status')}",
                    f"Response: {payload.get('response') or '-'}",
                ]
                text = "\n".join(lines)

            await self._plugin.send_text(
                OutboundMessage(
                    text=text,
                    conversation_id=self._chat_id,
                    thread_id=self._thread_id,
                    parse_mode="",
                    reply_markup=markup,
                )
            )

        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(_send())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        except RuntimeError:
            logger.debug("telegram_emit_event_no_loop", event=event)

    def _remember_runtime_context(self, payload: dict) -> None:
        session_id = payload.get("sessionId")
        run_id = payload.get("runId")
        if isinstance(session_id, str) and session_id.strip():
            self._current_session_id = session_id
        if isinstance(run_id, str) and run_id.strip():
            self._current_run_id = run_id
        surface = payload.get("surface")
        if isinstance(surface, str) and surface.strip():
            self._surface = surface

    def _ingest_warning_if_needed(self, event: str, payload: dict) -> None:
        if event != "harness.warning" or self._warning_ingestor is None:
            return
        try:
            self._warning_ingestor.ingest(
                payload,
                session_id=_first_non_empty_string(
                    payload.get("sessionId"),
                    self._current_session_id,
                ),
                run_id=_first_non_empty_string(payload.get("runId"), self._current_run_id),
                surface=_first_non_empty_string(payload.get("surface"), self._surface)
                or "telegram",
            )
        except Exception as exc:
            logger.warning("telegram_harness_warning_ingest_failed", error=str(exc))

    def _queue_text(self, approval_id: str) -> str:
        if self._approval_store is None or not approval_id:
            return ""
        pending = sorted(
            self._approval_store.list(status=ApprovalStatus.PENDING, limit=10_000),
            key=lambda item: item.created_at,
        )
        total = len(pending)
        for index, approval in enumerate(pending, start=1):
            if approval.approval_id == approval_id:
                return f"Queue: {index} / {total}"
        return ""

    @staticmethod
    def _display_session(session_id: str) -> str:
        if session_id.startswith("telegram:"):
            conv_id, thread_id = parse_telegram_session_id(session_id)
            if thread_id is not None:
                return f"chat {conv_id} / topic {thread_id}"
            return f"chat {conv_id}"
        return session_id or "-"


def _first_non_empty_string(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
    return None


class TelegramGatewayRunner:
    """Main Telegram gateway loop."""

    def __init__(
        self,
        config: DSAgentConfig,
        *,
        supervisor: object | None = None,
        token_override: str | None = None,
    ) -> None:
        self._config = config
        self._supervisor = supervisor
        self._token_store = create_auth_profile_store(config)
        self._transcript_store = JsonTranscriptStore(config.agent.workspace_dir)
        self._checkpoint_store = JsonCheckpointStore(config.agent.workspace_dir)
        self._approval_store = JsonApprovalStore(config.agent.workspace_dir)
        self._goal_store = JsonGoalStore(config.agent.workspace_dir)
        self._working_memory_store = JsonWorkingMemoryStore(config.agent.workspace_dir)
        self._policy_store = JsonPolicyStore(config.agent.workspace_dir)
        self._delivery_policy_store = JsonDeliveryPolicyStore(config.agent.workspace_dir)
        self._runtime_event_log = RuntimeEventLog(config.agent.workspace_dir)
        self._workspace = WorkspaceService(str(config.agent.workspace_dir))
        self._config_path = get_default_config_path()
        bot_token = token_override or config.channels.telegram.bot_token
        self._plugin = TelegramPlugin(
            bot_token=bot_token,
            allow_from=config.channels.telegram.allow_from or None,
            workspace_dir=config.agent.workspace_dir,
        )
        self._sessions = SessionManager()
        self._runtime_sessions = RuntimeSessionRegistry()
        self._task_ledger = TaskLedger()
        self._runs = RunRegistry(self._runtime_sessions)
        self._preferences = JsonOperatorPreferencesStore(config.agent.workspace_dir)
        self._alert_state = JsonOperatorAlertStateStore(config.agent.workspace_dir)
        self._action_tokens = ActionTokenStore()
        self._delivery_rate_limiter = self._build_delivery_rate_limiter()
        self._operator_chats: set[str] = set()
        self._delivery_targets: dict[str, TelegramDeliveryTarget] = {}
        self._seen_runtime_event_ids: set[str] = set()
        # PLAN_04 §4.5: lazy adapter for Notification → Telegram payload.
        self._message_builder = TelegramMessageBuilder()
        # PLAN_04 close-out: persist quiet-hours-suppressed notifications so
        # they survive process restarts.  Composition (transport + quiet
        # hours port + persistent deferred store) lives at the gateway
        # layer to honour the dependency rule.
        self._deferred_notification_store = JsonDeferredNotificationStore(
            str(config.agent.workspace_dir)
        )
        self._send_notification_use_case = SendNotificationUseCase(
            transport=_NullNotificationTransport(),
            quiet_hours=CheckQuietHoursUseCase(
                _DeliveryPolicyQuietHoursPort(self._delivery_policy_store)
            ),
            deferred_store=self._deferred_notification_store,
        )

    # Threshold (seconds) before surfacing the "Analyzing... + Run/Stop controls"
    # operator block. Quick chat-style replies that finish under this stay silent.
    _RUN_ANNOUNCE_DELAY_SECONDS: typing.ClassVar[float] = 60.0

    _BOT_COMMANDS: typing.ClassVar[list[tuple[str, str]]] = [
        ("status", "Runtime summary"),
        ("contract", "Task contract summary and agree"),
        ("verdict", "Latest verifier verdict"),
        ("runs", "Recent runs"),
        ("approvals", "Pending approvals"),
        ("alerts", "Recent runtime alerts"),
        ("menu", "Quick actions menu"),
        ("stop", "Stop current run"),
        ("resume", "Resume from checkpoint"),
        ("subscriptions", "Notification preferences"),
        ("severity", "Set minimum alert severity"),
        ("digest", "Configure or force alert digests"),
        ("mute", "Mute alerts temporarily"),
        ("projects", "Recent projects"),
        ("artifact", "Send one project file"),
        ("unmute", "Resume live alerts"),
        ("semantic_proposal", "Semantic proposals (list/approve/reject)"),
    ]

    async def run(self) -> None:
        """Start the gateway."""
        await self._plugin.start()
        await self._plugin.set_my_commands(self._BOT_COMMANDS)
        logger.info("telegram_gateway_started")
        self._seed_seen_runtime_events()

        self._import_tools()
        await self._sessions.start_cleanup_task()

        poll_task = asyncio.create_task(self._plugin.poll_updates())
        alert_task = asyncio.create_task(self._poll_runtime_alerts())
        background_tasks: set[asyncio.Task[None]] = set()

        try:
            while True:
                msg = await self._plugin.get_next_message()
                task = asyncio.create_task(self._handle_message(msg))
                background_tasks.add(task)
                task.add_done_callback(background_tasks.discard)
        except asyncio.CancelledError:
            pass
        finally:
            poll_task.cancel()
            alert_task.cancel()
            await asyncio.gather(alert_task, return_exceptions=True)
            await self._plugin.stop()

    async def _handle_message(self, msg: object) -> None:
        """Handle one inbound Telegram message."""
        from ds_agent.channels.base import InboundMessage

        inbound: InboundMessage = msg  # type: ignore[assignment]
        self._remember_delivery_target(inbound)
        self._operator_chats.add(inbound.conversation_id)

        if inbound.callback_data and inbound.callback_query_id:
            await self._handle_callback_query(inbound)
            return

        text = (inbound.text or "").strip()
        if text.lower().startswith("/pair "):
            await self._handle_pairing_command(inbound, text)
            return

        if inbound.text.startswith("/"):
            await self._handle_command(inbound)
            return

        pending_approval = self._approval_store.latest_pending_for_session(
            self._session_id(inbound.conversation_id, inbound.thread_id)
        )
        if pending_approval is not None:
            resolved = self._approval_store.resolve(
                pending_approval.approval_id,
                status=ApprovalStatus.APPROVED,
                response=inbound.text,
                source="telegram",
                actor=inbound.sender_id,
            )
            if resolved is None:
                return
            await self._send_text(
                self._format_approval_resolution_summary(resolved),
                inbound.conversation_id,
                thread_id=inbound.thread_id,
            )
            return

        await self._execute_agent_turn(inbound, inbound.text)

    async def _handle_pairing_command(self, inbound: object, text: str) -> None:
        """Handle OTP pairing before normal command dispatch."""
        from ds_agent.channels.base import InboundMessage
        from ds_agent.domain.errors.telegram_errors import PairingError

        msg: InboundMessage = inbound  # type: ignore[assignment]
        language = getattr(self._config.agent, "language", "en")
        parts = text.split(maxsplit=1)
        code = parts[1].strip() if len(parts) == 2 else ""
        supervisor = self._supervisor
        confirm = getattr(supervisor, "confirm_pairing_by_code", None)
        if not code or not callable(confirm):
            await self._send_text(
                telegram_string(language, "pairing.invalid_code"),
                msg.conversation_id,
                thread_id=msg.thread_id,
            )
            return
        try:
            paired_chat_id = msg.sender_id or msg.conversation_id
            await confirm(code, paired_chat_id)
        except PairingError:
            await self._send_text(
                telegram_string(language, "pairing.invalid_code"),
                msg.conversation_id,
                thread_id=msg.thread_id,
            )
            return
        await self._send_text(
            telegram_string(language, "pairing.success"),
            msg.conversation_id,
            thread_id=msg.thread_id,
        )

    async def _handle_command(self, msg: object) -> None:
        """Handle Telegram slash commands."""
        from ds_agent.channels.base import InboundMessage

        inbound: InboundMessage = msg  # type: ignore[assignment]
        parts = inbound.text.split()
        cmd = parts[0].lower()
        args = parts[1:]

        text: str | None
        if cmd in {"/start", "/help"}:
            text = self._help_text()
        elif cmd in {"/ops", "/menu"}:
            text = self._format_ops_menu(inbound.conversation_id, thread_id=inbound.thread_id)
        elif cmd == "/status":
            text = self._format_status(inbound.conversation_id, thread_id=inbound.thread_id)
        elif cmd == "/contract":
            text = self._handle_contract_command(inbound, args)
        elif cmd == "/certification":
            text = self._handle_certification_command(inbound, args)
        elif cmd == "/verdict":
            text = self._handle_verdict_command(inbound, args)
        elif cmd == "/sessions":
            text = self._format_sessions()
        elif cmd == "/runs":
            text = self._format_runs(inbound.conversation_id, thread_id=inbound.thread_id)
        elif cmd == "/run":
            await self._send_run_detail(
                inbound,
                run_id=args[0] if args else None,
            )
            return
        elif cmd == "/approvals":
            text = self._format_approvals(inbound.conversation_id, thread_id=inbound.thread_id)
        elif cmd == "/approval":
            await self._send_approval_detail(
                inbound,
                approval_id=args[0] if args else None,
            )
            return
        elif cmd == "/alerts":
            text = self._format_alert_digest(inbound.conversation_id, args[0] if args else None)
        elif cmd == "/policy":
            text = self._format_policy_summary()
        elif cmd == "/autonomy":
            text = self._handle_autonomy_command(args[0] if args else None)
        elif cmd == "/profile":
            text = self._handle_profile_command(args[0] if args else None)
        elif cmd == "/goals":
            text = self._format_recurring_goals()
        elif cmd == "/orders":
            text = self._format_standing_orders()
        elif cmd == "/projects":
            text = self._format_projects()
        elif cmd == "/project":
            text = self._handle_project_command(args)
        elif cmd == "/artifacts":
            text = self._format_artifacts(args[0] if args else None)
        elif cmd == "/artifact":
            text = await self._handle_artifact_command(inbound, args)
        elif cmd == "/session":
            text = self._format_session(inbound.conversation_id, thread_id=inbound.thread_id)
        elif cmd == "/history":
            text = self._format_history(
                inbound.conversation_id,
                args[0] if args else None,
                thread_id=inbound.thread_id,
            )
        elif cmd == "/resume":
            text = await self._handle_resume_command(inbound)
        elif cmd == "/stop":
            text = await self._handle_stop_command(inbound, args[0] if args else None)
        elif cmd in {"/approve", "/reject"}:
            text = await self._handle_approval_command(inbound)
        elif cmd == "/notify":
            text = self._handle_notify_command(inbound, args)
        elif cmd == "/subscriptions":
            text = self._format_subscriptions(inbound.conversation_id)
        elif cmd == "/severity":
            text = self._handle_severity_command(inbound.conversation_id, args[0] if args else None)
        elif cmd == "/digest":
            text = await self._handle_digest_command(inbound, args)
        elif cmd == "/ack":
            text = self._handle_ack_command(inbound, args[0] if args else None)
        elif cmd == "/mute":
            text = self._handle_mute_command(inbound, args[0] if args else None)
        elif cmd == "/semantic_proposal":
            text = await self._handle_semantic_proposal_command(inbound, args)
        elif cmd == "/unmute":
            self._alert_state.unmute(inbound.conversation_id)
            self._record_operator_action(
                action="Unmute",
                target_id=inbound.conversation_id,
                actor=inbound.sender_id,
                chat_id=inbound.conversation_id,
                thread_id=inbound.thread_id,
                outcome="Live alerts resumed.",
            )
            text = (
                "Unmuted. Live alerts will resume. Use /digest now to review anything you missed."
            )
        else:
            text = "Unknown command. Use /start to see available commands."

        if text is not None:
            await self._send_text(
                text,
                inbound.conversation_id,
                thread_id=inbound.thread_id,
            )

    async def _execute_agent_turn(
        self,
        inbound: object,
        user_message: str,
        *,
        announce_text: str = "Analyzing...",
    ) -> None:
        from ds_agent.channels.base import InboundMessage

        message: InboundMessage = inbound  # type: ignore[assignment]
        session = await self._sessions.get_or_create(
            channel_id="telegram",
            conversation_id=message.conversation_id,
            thread_id=message.thread_id,
            agent_factory=lambda: self._create_agent(
                message.conversation_id,
                thread_id=message.thread_id,
            ),
        )
        set_callbacks = getattr(session.agent, "set_callbacks", None)
        if callable(set_callbacks):
            set_callbacks(
                TelegramCallbacks(
                    self._plugin,
                    message.conversation_id,
                    thread_id=message.thread_id,
                    approval_store=self._approval_store,
                    action_tokens=self._action_tokens,
                    workspace_dir=str(self._config.agent.workspace_dir),
                )
            )

        existing = self._runs.latest_for_session(
            session.session_key,
            statuses={RuntimeStatus.RUNNING},
        )
        if existing is not None:
            self._task_ledger.cancel_for_run(existing.run_id)
            await self._task_ledger.wait_for_run(existing.run_id, timeout_seconds=1.0)

        self._runtime_sessions.ensure(session.session_key, "telegram")
        run = self._runs.create(session.session_key, "telegram", user_message)

        # Deferred run announcement: only surface "Analyzing... + Run/Stop controls"
        # if the agent task is still going after RUN_ANNOUNCE_DELAY_SECONDS. Quick
        # replies (chat-style messages that finish in <1 min) stay quiet.
        async def _deferred_announce() -> None:
            try:
                await asyncio.sleep(self._RUN_ANNOUNCE_DELAY_SECONDS)
            except asyncio.CancelledError:
                return
            try:
                await self._send_text(
                    "\n".join(
                        [
                            announce_text,
                            f"Run: {run.run_id}",
                            f"Session: {self._display_session(session.session_key)}",
                            f"Fallback: /stop {run.run_id} or /run {run.run_id}",
                        ]
                    ),
                    message.conversation_id,
                    thread_id=message.thread_id,
                    reply_markup=self._build_run_markup(
                        run.run_id,
                        running=True,
                        actor=message.sender_id,
                        chat_id=message.conversation_id,
                    ),
                )
            except Exception as exc:
                logger.warning(
                    "telegram_announce_failed",
                    run_id=run.run_id,
                    error=str(exc),
                )

        announce_task = asyncio.create_task(
            _deferred_announce(),
            name=f"telegram-announce:{run.run_id}",
        )

        set_runtime_context = getattr(session.agent, "set_runtime_context", None)
        if callable(set_runtime_context):
            set_runtime_context(run.run_id, surface="telegram")
        task = asyncio.create_task(
            session.agent.run(user_message),  # type: ignore[attr-defined]
            name=f"telegram-run:{run.run_id}",
        )
        task_state = self._task_ledger.register(run.run_id, task)
        self._runs.attach_task(run.run_id, task_state.task_id)

        try:
            try:
                result = await task
                cost = 0.0
                if hasattr(session.agent, "_budget"):
                    cost = session.agent._budget.state.total_cost_usd  # type: ignore[attr-defined]
                self._runs.mark_succeeded(run.run_id, result, cost_usd=cost)
            except asyncio.CancelledError:
                self._runs.mark_cancelled(run.run_id)
                result = "Current run aborted."
                logger.info("telegram_run_cancelled", run_id=run.run_id)
            except Exception as exc:
                self._runs.mark_failed(run.run_id, str(exc))
                result = f"Error: {exc}"
                logger.error("telegram_run_failed", run_id=run.run_id, error=str(exc), exc_info=True)
        finally:
            if not announce_task.done():
                announce_task.cancel()
                try:
                    await announce_task
                except (asyncio.CancelledError, Exception):
                    pass

        await self._send_chunks(
            result,
            message.conversation_id,
            thread_id=message.thread_id,
        )
        await self._deliver_run_outcome(message, run)

    async def _handle_stop_command(
        self,
        inbound: object,
        run_id: str | None,
    ) -> str:
        """Abort a running task by explicit run id or current-chat default."""
        from ds_agent.channels.base import InboundMessage

        message: InboundMessage = inbound  # type: ignore[assignment]
        conversation_id = message.conversation_id
        runs = getattr(self, "_runs", None)
        tasks = getattr(self, "_task_ledger", None)
        if runs is None or tasks is None:
            return "Runtime control is unavailable."

        active = self._resolve_run_for_control(
            conversation_id,
            run_id,
            thread_id=message.thread_id,
        )
        if active is None:
            if run_id:
                return f"Unknown run id: {run_id}. Use /runs to inspect active runs."
            return "No running task for this chat. Use /runs to inspect recent runs."
        if active.status != RuntimeStatus.RUNNING:
            return (
                f"Run {active.run_id} is {active.status.value}; nothing to stop. "
                f"Use /run {active.run_id} to inspect the current state."
            )

        cancelled = tasks.cancel_for_run(active.run_id)
        await asyncio.sleep(0)
        if not cancelled:
            return f"Run {active.run_id} is already stopping. Use /run {active.run_id} to inspect."
        result = f"Stopped run {active.run_id} ({self._display_session(active.session_id)})."
        self._record_operator_action(
            action="Stop",
            target_id=active.run_id,
            actor=message.sender_id,
            chat_id=conversation_id,
            thread_id=message.thread_id,
            outcome=result,
        )
        return result

    async def _handle_approval_command(self, inbound: object) -> str:
        from ds_agent.channels.base import InboundMessage

        message: InboundMessage = inbound  # type: ignore[assignment]
        parts = message.text.split(maxsplit=2)
        cmd = parts[0].lower()
        default_pending = self._approval_store.latest_pending_for_session(
            self._session_id(message.conversation_id, message.thread_id)
        )
        approval_id = default_pending.approval_id if default_pending is not None else ""
        response: str | None = None

        if len(parts) >= 2:
            existing = self._approval_store.get(parts[1])
            if existing is not None:
                approval_id = parts[1]
                if len(parts) == 3:
                    response = parts[2]
            else:
                response = " ".join(parts[1:])
        if not approval_id:
            return "No pending approval found for this chat. Use /approvals to inspect the queue."

        status = ApprovalStatus.APPROVED if cmd == "/approve" else ApprovalStatus.REJECTED
        resolved = self._approval_store.resolve(
            approval_id,
            status=status,
            response=response,
            source="telegram",
            actor=message.sender_id,
        )
        if resolved is None:
            existing = self._approval_store.get(approval_id)
            if existing is None:
                return f"Unknown approval id: {approval_id}. Use /approvals to inspect the queue."
            return (
                f"Approval {approval_id} is already {existing.status.value}. "
                f"Use /approval {approval_id} to inspect the recorded response."
            )

        outcome = self._format_approval_resolution_summary(resolved)
        self._record_operator_action(
            action="Approve" if status == ApprovalStatus.APPROVED else "Reject",
            target_id=resolved.approval_id,
            actor=message.sender_id,
            chat_id=message.conversation_id,
            thread_id=message.thread_id,
            outcome=outcome,
        )
        return outcome

    def _help_text(self) -> str:
        return (
            "DS Agent operator bot.\n\n"
            "Send a message to start an analysis.\n"
            "Read:\n"
            "/menu - compact quick actions\n"
            "/status - runtime summary\n"
            "/contract [show|agree|abandon] [task_id] - inspect or transition task contracts\n"
            "/certification <mission> | status <mission> | submit <mission> <level>\n"
            "  [approver...] - inspect or submit mission certification\n"
            "/verdict [verdict_id] | /verdict shadow [comparison_id] - inspect the "
            "latest verifier verdict or shadow diff review\n"
            "/sessions - recent sessions\n"
            "/runs - recent runs for this chat\n"
            "/run [id] - inspect one run\n"
            "/approvals - pending approvals\n"
            "/approval [id] - inspect one approval\n"
            "/alerts [n] - recent runtime alerts\n"
            "/policy - autonomy and policy summary\n"
            "/goals - recurring goal summary\n"
            "/orders - standing orders summary\n"
            "/projects - recent projects\n"
            "/project <id> - inspect one project\n"
            "/artifacts <project_id> - list project files\n"
            "/artifact <project_id> <index> - send one file\n"
            "/session - summarize this chat session\n"
            "/history [n] - recent user/assistant turns\n"
            "Control:\n"
            "/resume - continue from checkpoint or memory\n"
            "/autonomy on|off - save shared autonomy toggle\n"
            "/profile manual|balanced|aggressive - save automation profile\n"
            "/project create <name> - create a project\n"
            "/stop [id] - stop the current run or one run id\n"
            "/approve <id> <response>\n"
            "/reject <id> [reason]\n"
            "Notifications:\n"
            "/subscriptions - view notification preferences\n"
            "/notify approvals|all|off|on - set notification mode\n"
            "/notify add|remove|only <categories> - change alert categories\n"
            "/severity info|warning|error|critical - set minimum severity\n"
            "/digest on|off|<minutes>|hourly|morning|end-of-day|timezone <IANA>|now\n"
            "/ack [event_id] - acknowledge an alert\n"
            "/mute <duration> - mute alerts (e.g. 30m, 2h)\n"
            "/unmute - resume live alerts"
        )

    def _handle_contract_command(self, inbound: object, args: list[str]) -> str:
        from ds_agent.channels.base import InboundMessage

        message: InboundMessage = inbound  # type: ignore[assignment]
        action = args[0].lower() if args else "show"
        task_id = args[1] if len(args) > 1 else None
        session_id = self._session_id(message.conversation_id, message.thread_id)

        try:
            view = self._resolve_task_contract_view(session_id, task_id)
        except TaskContractNotFoundError as exc:
            return str(exc)
        except TaskContractError as exc:
            return f"Contract error: {exc}"

        if action in {"show", "summary"}:
            return render_task_contract_summary(view)

        if action == "agree":
            try:
                return self._transition_task_contract(
                    view,
                    transition_to=TaskContractStatus.AGREED,
                    reason="telegram operator agreed contract",
                    outcome_label="Transitioned to agreed.",
                )
            except (TaskContractError, ValueError) as exc:
                return f"Contract error: {exc}"

        if action == "abandon":
            try:
                return self._transition_task_contract(
                    view,
                    transition_to=TaskContractStatus.ABANDONED,
                    reason="telegram operator abandoned contract",
                    outcome_label="Transitioned to abandoned.",
                )
            except (TaskContractError, ValueError) as exc:
                return f"Contract error: {exc}"

        return "Usage: /contract [show|agree|abandon] [task_id]"

    def _handle_verdict_command(self, inbound: object, args: list[str]) -> str:
        from ds_agent.channels.base import InboundMessage

        message: InboundMessage = inbound  # type: ignore[assignment]
        if args and args[0].lower() == "shadow":
            comparison_id = args[1] if len(args) > 1 else None
            record = self._resolve_shadow_comparison(
                self._session_id(message.conversation_id, message.thread_id),
                comparison_id=comparison_id,
            )
            if record is None:
                if comparison_id:
                    return f"Shadow comparison not found: {comparison_id}"
                return "No shadow comparison recorded for the active verifier verdict."
            return render_shadow_comparison_report(record, compact=True)

        verdict_id = args[0] if args else None
        verdict = self._resolve_review_verdict(
            self._session_id(message.conversation_id, message.thread_id),
            verdict_id=verdict_id,
        )
        if verdict is None:
            if verdict_id:
                return f"Review verdict not found: {verdict_id}"
            return "No review verdict recorded for the active task contract."
        return render_verdict_report(verdict, compact=True)

    def _handle_certification_command(self, inbound: object, args: list[str]) -> str:
        from ds_agent.application.services.certification_usecases import (
            GetCertificationStatusUseCase,
            SubmitCertificationInput,
            SubmitCertificationUseCase,
        )
        from ds_agent.channels.base import InboundMessage
        from ds_agent.infrastructure.persistence.certification_store import SqliteCertificationStore
        from ds_agent.skills.mission_pack_loader import MissionPackLoader

        message: InboundMessage = inbound  # type: ignore[assignment]
        if not args:
            return (
                "Usage: /certification <mission> | "
                "/certification status <mission> | "
                "/certification submit <mission> <level> [approver...]"
            )

        action = args[0].lower()
        mission_loader = MissionPackLoader()
        store = SqliteCertificationStore.for_workspace(str(self._config.agent.workspace_dir))

        if action == "submit":
            if len(args) < 3:
                return "Usage: /certification submit <mission> <level> [approver...]"
            mission_name = args[1]
            target_level = args[2]
            approvers = tuple(args[3:])
            try:
                result = SubmitCertificationUseCase(mission_loader, store).execute(
                    SubmitCertificationInput(
                        mission_name=mission_name,
                        target_level=target_level,
                        approved_by=approvers,
                    )
                )
            except ValueError as exc:
                return f"Certification error: {exc}"
            rendered = render_certification_submission(result)
            self._record_operator_action(
                action="CertificationSubmit",
                target_id=mission_name,
                actor=message.sender_id,
                chat_id=message.conversation_id,
                thread_id=message.thread_id,
                outcome=rendered,
            )
            return rendered

        mission_name = args[1] if action == "status" and len(args) > 1 else args[0]
        try:
            status_result = GetCertificationStatusUseCase(mission_loader, store).execute(
                mission_name
            )
        except ValueError as exc:
            return f"Certification error: {exc}"
        return render_certification_status(status_result, compact=True)

    def _resolve_task_contract_view(
        self,
        session_id: str,
        task_id: str | None,
    ) -> TaskContractViewDTO:
        container = self._task_contract_container()
        if task_id:
            return container.get.execute(task_id, include=_TASK_CONTRACT_INCLUDE)

        bundle = container.store.get_active_bundle(session_id)
        if bundle is None:
            raise TaskContractNotFoundError("No active task contract for this chat.")
        return TaskContractViewDTO.from_bundle(
            bundle,
            include=set(_TASK_CONTRACT_INCLUDE),
            dod_summary=[],
        )

    def _resolve_review_verdict(
        self,
        session_id: str,
        *,
        verdict_id: str | None = None,
    ) -> ReviewVerdict | None:
        if verdict_id:
            return self._verifier_container().repo.get(verdict_id)
        bundle = self._task_contract_container().store.get_active_bundle(session_id)
        if bundle is None:
            return None
        return pick_effective_review_verdict(bundle.review_verdicts)

    def _resolve_shadow_comparison(
        self,
        session_id: str,
        *,
        comparison_id: str | None = None,
    ) -> ShadowComparisonRecord | None:
        verifier_container = self._verifier_container()
        if comparison_id:
            return verifier_container.shadow_repo.get(comparison_id)
        verdict = self._resolve_review_verdict(session_id)
        if verdict is None:
            return None
        shadow_id = verdict.metadata.get("shadow_comparison_id")
        if isinstance(shadow_id, str) and shadow_id.strip():
            record = verifier_container.shadow_repo.get(shadow_id.strip())
            if record is not None:
                return record
        records = verifier_container.shadow_repo.list_for_verdict(verdict.verdict_id)
        return records[0] if records else None

    def _transition_task_contract(
        self,
        view: TaskContractViewDTO,
        *,
        transition_to: TaskContractStatus,
        reason: str,
        outcome_label: str,
    ) -> str:
        container = self._task_contract_container()
        result = container.update.execute(
            TaskContractUpdateDTO(
                task_id=view.contract.task_id,
                expected_version=view.contract.version,
                patch={},
                transition_to=transition_to,
                reason=reason,
            )
        )
        refreshed = container.get.execute(view.contract.task_id, include=_TASK_CONTRACT_INCLUDE)
        return (
            f"{outcome_label}\n"
            f"Status: {result['status']} | Version: {result['new_version']}\n\n"
            f"{render_task_contract_summary(refreshed)}"
        )

    def _format_status(self, conversation_id: str, *, thread_id: str | None = None) -> str:
        session_id = self._session_id(conversation_id, thread_id)
        active_sessions = self._runtime_active_count()
        active_runs = getattr(self, "_runs", None)
        run_count = 0 if active_runs is None else active_runs.active_count
        pending_total = self._approval_store.pending_count
        pending_chat = self._approval_store.list(
            session_id=session_id,
            status=ApprovalStatus.PENDING,
            limit=3,
        )
        latest_run = None if active_runs is None else active_runs.latest_for_session(session_id)
        latest_run_text = "idle"
        if latest_run is not None:
            latest_run_text = (
                f"{latest_run.status.value} / {latest_run.run_id} / "
                f"{self._truncate(latest_run.message, 36)}"
            )

        automation_mode = "enabled" if self._autonomous_runtime_enabled() else "manual"
        return "\n".join(
            [
                f"Runtime: {automation_mode} ({self._automation_profile()})",
                f"Active sessions: {active_sessions}",
                f"Active runs: {run_count}",
                f"Pending approvals: {pending_total}",
                f"This chat: {latest_run_text}",
                "Chat approvals: "
                + (
                    ", ".join(item.approval_id for item in pending_chat) if pending_chat else "none"
                ),
            ]
        )

    def _format_sessions(self) -> str:
        registry = self._runtime_session_registry()
        if registry is None:
            return "Recent sessions: unavailable"

        sessions = registry.list(limit=_MOBILE_LIST_LIMIT)
        if not sessions:
            return "Recent sessions: none"

        lines = ["Recent sessions:"]
        runs = getattr(self, "_runs", None)
        for session in sessions:
            latest_run = None
            if runs is not None and session.last_run_id:
                latest_run = runs.get(session.last_run_id)
            status = latest_run.status.value if latest_run is not None else "idle"
            lines.append(
                "- "
                + f"{self._display_session(session.session_id)} | {status} | "
                + f"active {self._relative_age(session.last_active)}"
            )
        return "\n".join(lines)

    def _format_runs(self, conversation_id: str, *, thread_id: str | None = None) -> str:
        runs = getattr(self, "_runs", None)
        if runs is None:
            return "Recent runs: unavailable"

        session_id = self._session_id(conversation_id, thread_id)
        scoped_runs = runs.list(session_id=session_id, limit=_MOBILE_LIST_LIMIT)
        scope = "this chat"
        if not scoped_runs:
            scoped_runs = runs.list(limit=_MOBILE_LIST_LIMIT)
            scope = "all sessions"
        if not scoped_runs:
            return "Recent runs: none"

        lines = [f"Recent runs ({scope}):"]
        for run in scoped_runs:
            detail = self._truncate(run.message, 42)
            lines.append(
                f"- {run.run_id} | {run.status.value} | {detail} | "
                f"{self._relative_age(run.created_at)}"
            )
        return "\n".join(lines)

    def _format_run_detail(
        self,
        conversation_id: str,
        run_id: str | None,
        *,
        thread_id: str | None = None,
    ) -> str:
        run = self._resolve_run_for_control(
            conversation_id,
            run_id,
            thread_id=thread_id,
            allow_any_status=True,
        )
        if run is None:
            if run_id:
                return f"Unknown run id: {run_id}. Use /runs to inspect recent runs."
            return "No run found for this chat. Use /runs to inspect recent runs."

        lines = [
            f"Run: {run.run_id}",
            f"Session: {self._display_session(run.session_id)}",
            f"Status: {run.status.value}",
            f"Started: {self._relative_age(run.created_at)}",
            f"Prompt: {self._truncate(run.message, 120)}",
        ]
        if run.task_id:
            lines.append(f"Task: {run.task_id}")
        if run.result_preview:
            lines.append(f"Result: {self._truncate(run.result_preview, 120)}")
        if run.error:
            lines.append(f"Error: {self._truncate(run.error, 120)}")
        if run.cost_usd > 0:
            lines.append(f"Cost: ${run.cost_usd:.4f}")
        if run.status == RuntimeStatus.RUNNING:
            lines.append(f"Next: /stop {run.run_id}")
        else:
            lines.append(f"Next: /runs or /run {run.run_id}")
        return "\n".join(lines)

    async def _send_run_detail(self, inbound: object, *, run_id: str | None) -> None:
        from ds_agent.channels.base import InboundMessage

        message: InboundMessage = inbound  # type: ignore[assignment]
        run = self._resolve_run_for_control(
            message.conversation_id,
            run_id,
            thread_id=message.thread_id,
            allow_any_status=True,
        )
        text = self._format_run_detail(
            message.conversation_id,
            run_id,
            thread_id=message.thread_id,
        )
        markup = None
        if run is not None:
            markup = self._build_run_markup(
                run.run_id,
                running=run.status == RuntimeStatus.RUNNING,
                actor=message.sender_id,
                chat_id=message.conversation_id,
            )
        await self._send_text(
            text,
            message.conversation_id,
            thread_id=message.thread_id,
            reply_markup=markup,
        )

    def _format_approvals(self, conversation_id: str, *, thread_id: str | None = None) -> str:
        session_id = self._session_id(conversation_id, thread_id)
        pending = self._approval_store.list(
            session_id=session_id,
            status=ApprovalStatus.PENDING,
            limit=_MOBILE_LIST_LIMIT,
        )
        scope = "this chat"
        if not pending:
            pending = self._approval_store.list(
                status=ApprovalStatus.PENDING,
                limit=_MOBILE_LIST_LIMIT,
            )
            scope = "all sessions"
        if not pending:
            return "Pending approvals: none"

        lines = [f"Pending approvals ({scope}):"]
        for approval in pending:
            prompt = self._truncate(approval.question, 48)
            options = f" | options: {', '.join(approval.options[:3])}" if approval.options else ""
            queue_text = self._queue_position_text(approval.approval_id)
            default_text = f" | default: {approval.default}" if approval.default else ""
            run_text = f" | run: {approval.run_id}" if approval.run_id else ""
            session_text = ""
            if scope == "all sessions":
                session_text = f" | {self._display_session(approval.session_id)}"
            lines.append(
                f"- {queue_text} | {approval.approval_id}{session_text}{run_text}"
                f" | {prompt}{options}{default_text}"
            )
        lines.append("Use /approval <id> for detail, or /approve <id> <response>.")
        return "\n".join(lines)

    def _format_approval_detail(
        self,
        conversation_id: str,
        approval_id: str | None,
        *,
        thread_id: str | None = None,
    ) -> str:
        approval = self._resolve_approval(conversation_id, approval_id, thread_id=thread_id)
        if approval is None:
            return (
                f"Unknown approval id: {approval_id}"
                if approval_id
                else "No pending approval found for this chat."
            )

        lines = [
            f"Approval: {approval.approval_id}",
            f"Session: {self._display_session(approval.session_id)}",
            f"Run: {approval.run_id or '-'}",
            f"Status: {approval.status.value}",
            f"Queue: {self._queue_position_text(approval.approval_id)}",
            f"Created: {self._relative_age(approval.created_at)}",
            f"Question: {self._truncate(approval.question, 180)}",
        ]
        if approval.options:
            lines.append(f"Options: {', '.join(approval.options[:5])}")
        if approval.default:
            lines.append(f"Default: {approval.default}")
        if approval.response:
            lines.append(f"Response: {approval.response}")
        lines.append(
            f"Reply in plain text, or use /approve {approval.approval_id} <response> "
            f"or /reject {approval.approval_id} [reason]."
        )
        return "\n".join(lines)

    async def _send_approval_detail(self, inbound: object, *, approval_id: str | None) -> None:
        from ds_agent.channels.base import InboundMessage

        message: InboundMessage = inbound  # type: ignore[assignment]
        approval = self._resolve_approval(
            message.conversation_id,
            approval_id,
            thread_id=message.thread_id,
        )
        text = self._format_approval_detail(
            message.conversation_id,
            approval_id,
            thread_id=message.thread_id,
        )
        markup = None
        if approval is not None and approval.status == ApprovalStatus.PENDING:
            markup = self._build_approval_markup(
                approval.approval_id,
                chat_id=message.conversation_id,
            )
        await self._send_text(
            text,
            message.conversation_id,
            thread_id=message.thread_id,
            reply_markup=markup,
        )

    def _format_alert_digest(self, conversation_id: str, count_arg: str | None) -> str:
        limit = _DEFAULT_ALERT_LIMIT
        if count_arg is not None:
            try:
                limit = max(1, min(_MAX_ALERT_LIMIT, int(count_arg)))
            except ValueError:
                return "Usage: /alerts [count]"

        events = self._runtime_event_log.list(limit=limit)
        if not events:
            return "Recent alerts: none"

        lines = [f"Recent alerts ({len(events)}):"]
        for event in events:
            lines.append(self._format_alert_digest_line(conversation_id, event))
        lines.append("Use /ack <event_id> to acknowledge one alert.")
        return "\n".join(lines)

    def _format_policy_summary(self) -> str:
        policy_store = getattr(self, "_policy_store", None)
        delivery_policy_store = getattr(self, "_delivery_policy_store", None)
        workspace = getattr(self, "_workspace", None)
        if not isinstance(policy_store, JsonPolicyStore) or not isinstance(
            workspace,
            WorkspaceService,
        ):
            return "Policy summary unavailable."

        goals = policy_store.list_recurring_goals()
        orders = policy_store.get_standing_orders()
        project_count = len(workspace.list_projects())
        delivery_policy = (
            delivery_policy_store.get()
            if isinstance(delivery_policy_store, JsonDeliveryPolicyStore)
            else DeliveryPolicy()
        )
        quiet_hours = "off"
        if delivery_policy.quiet_hours_start and delivery_policy.quiet_hours_end:
            quiet_hours = (
                f"{delivery_policy.quiet_hours_start}-{delivery_policy.quiet_hours_end} "
                f"{delivery_policy.quiet_hours_timezone}"
            )
        return "\n".join(
            [
                "Policy summary",
                f"Autonomy: {'enabled' if self._autonomous_runtime_enabled() else 'disabled'}",
                f"Profile: {self._automation_profile()}",
                f"Recurring goals: {len(goals)}",
                f"Standing orders: {len(orders)}",
                f"Projects: {project_count}",
                f"Live push policy: {'on' if delivery_policy.live_push_enabled else 'off'}",
                "Default digest: "
                + ("on" if delivery_policy.digest_enabled else "off")
                + f" ({int(delivery_policy.digest_interval_seconds / 60)}m)",
                "Artifact auto-send: "
                + ("on" if delivery_policy.artifact_auto_delivery_enabled else "off"),
                f"Quiet hours: {quiet_hours}",
                "Escalation: "
                + ("on" if delivery_policy.escalation_enabled else "off")
                + f" (threshold {delivery_policy.escalation_repeat_threshold})",
                "Use /goals, /orders, /projects for detail.",
            ]
        )

    def _handle_autonomy_command(self, value: str | None) -> str:
        if value is None:
            state = "enabled" if self._autonomous_runtime_enabled() else "disabled"
            return f"Autonomy: {state}"
        normalized = value.strip().lower()
        if normalized not in {"on", "off"}:
            return "Usage: /autonomy on|off"
        self._config.gateway.autonomous_runtime_enabled = normalized == "on"
        self._persist_runtime_config()
        return "\n".join(
            [
                "Autonomy saved: "
                + ("enabled" if self._autonomous_runtime_enabled() else "disabled"),
                f"Profile: {self._automation_profile()}",
                "Note: running backends may need reload to apply.",
            ]
        )

    def _handle_profile_command(self, value: str | None) -> str:
        if value is None:
            return f"Profile: {self._automation_profile()}"
        normalized = value.strip().lower()
        if normalized not in _AUTOMATION_PROFILES:
            return "Usage: /profile manual|balanced|aggressive"
        self._config.gateway.automation_profile = normalized
        self._persist_runtime_config()
        return "\n".join(
            [
                f"Profile saved: {self._automation_profile()}",
                f"Autonomy: {'enabled' if self._autonomous_runtime_enabled() else 'disabled'}",
                "Note: running backends may need reload to apply.",
            ]
        )

    def _format_recurring_goals(self) -> str:
        policy_store = getattr(self, "_policy_store", None)
        if not isinstance(policy_store, JsonPolicyStore):
            return "Recurring goals: unavailable"

        goals = policy_store.list_recurring_goals()
        if not goals:
            return "Recurring goals: none"

        lines = [f"Recurring goals ({min(len(goals), _MOBILE_LIST_LIMIT)} of {len(goals)}):"]
        for goal in goals[:_MOBILE_LIST_LIMIT]:
            lines.append(
                "- "
                + f"{goal.goal_id} | {'on' if goal.enabled else 'off'} | "
                + f"{self._interval_label(goal.interval_seconds)} | "
                + f"{self._display_session(goal.session_id)} | "
                + f"{self._truncate(goal.prompt, 48)}"
            )
        return "\n".join(lines)

    def _format_standing_orders(self) -> str:
        policy_store = getattr(self, "_policy_store", None)
        if not isinstance(policy_store, JsonPolicyStore):
            return "Standing orders: unavailable"

        orders = policy_store.get_standing_orders()
        if not orders:
            return "Standing orders: none"
        lines = [f"Standing orders ({min(len(orders), _MOBILE_LIST_LIMIT)} of {len(orders)}):"]
        for index, order in enumerate(orders[:_MOBILE_LIST_LIMIT], start=1):
            lines.append(f"- {index}. {self._truncate(order, 90)}")
        return "\n".join(lines)

    def _format_projects(self) -> str:
        workspace = getattr(self, "_workspace", None)
        if not isinstance(workspace, WorkspaceService):
            return "Projects: unavailable"

        projects = workspace.list_projects()
        if not projects:
            return "Projects: none"

        lines = [f"Projects ({min(len(projects), _MOBILE_LIST_LIMIT)} of {len(projects)}):"]
        for project in projects[:_MOBILE_LIST_LIMIT]:
            project_name = self._truncate(str(project.get("name", "")), 32)
            task_type = project.get("task_type") or "general"
            artifacts = project.get("artifacts", [])
            artifact_count = len(artifacts) if isinstance(artifacts, list) else 0
            lines.append(
                "- "
                + f"{project.get('id', '')} | {project_name} | {task_type!s} | "
                + f"{artifact_count} artifacts"
            )
        lines.append("Use /project <id> or /project create <name>.")
        return "\n".join(lines)

    def _handle_project_command(self, args: list[str]) -> str:
        workspace = getattr(self, "_workspace", None)
        if not isinstance(workspace, WorkspaceService):
            return "Project controls are unavailable."

        if not args:
            return "Usage: /project <id> or /project create <name>"
        action = args[0].strip()
        if action.lower() == "create":
            name = " ".join(args[1:]).strip()
            if not name:
                return "Usage: /project create <name>"
            project_id = workspace.create_project(name=name)
            project = workspace.get_project(project_id)
            project_name = name if project is None else str(project.get("name", name))
            return (
                "Project created\n"
                f"ID: {project_id}\n"
                f"Name: {project_name}\n"
                "Use /project "
                f"{project_id} to inspect."
            )

        project = workspace.get_project(action)
        if project is None:
            return f"Unknown project id: {action}"
        artifacts = project.get("artifacts", [])
        artifact_count = len(artifacts) if isinstance(artifacts, list) else 0
        lines = [
            f"Project: {project.get('id', action)}",
            f"Name: {project.get('name', '-')}",
            f"Task: {project.get('task_type') or 'general'}",
            f"Artifacts: {artifact_count}",
            f"Updated: {self._relative_age(float(project.get('updated_at', 0.0)))}",
        ]
        description = str(project.get("description", "")).strip()
        if description:
            lines.append(f"Description: {self._truncate(description, 120)}")
        files = self._list_project_files(action)
        if files:
            lines.append(f"Files: {len(files)}")
            for index, file_entry in enumerate(files[:3], start=1):
                lines.append(f"File {index}: {file_entry['path']}")
            lines.append(f"Use /artifacts {action} or /artifact {action} <index>.")
        return "\n".join(lines)

    def _format_artifacts(self, project_id: str | None) -> str:
        if not project_id:
            return "Usage: /artifacts <project_id>"
        project = self._workspace.get_project(project_id)
        if project is None:
            return f"Unknown project id: {project_id}"

        files = self._list_project_files(project_id)
        if not files:
            return f"Project files: none for {project_id}"

        lines = [
            f"Project files ({min(len(files), _MOBILE_LIST_LIMIT)} of {len(files)}):",
            f"Project: {project.get('name', project_id)}",
        ]
        for index, file_entry in enumerate(files[:_MOBILE_LIST_LIMIT], start=1):
            modified_at = file_entry.get("modifiedAt", 0)
            try:
                age = self._relative_age(float(modified_at) / 1000.0)
            except (TypeError, ValueError):
                age = "unknown"
            lines.append(
                f"- {index}. {file_entry['path']} | {file_entry.get('type') or 'file'} | {age}"
            )
        lines.append(f"Use /artifact {project_id} <index> to receive one file.")
        return "\n".join(lines)

    async def _handle_artifact_command(self, inbound: object, args: list[str]) -> str | None:
        from ds_agent.channels.base import InboundMessage

        message: InboundMessage = inbound  # type: ignore[assignment]
        if len(args) < 2:
            return "Usage: /artifact <project_id> <index>"

        project_id = args[0].strip()
        project = self._workspace.get_project(project_id)
        if project is None:
            return f"Unknown project id: {project_id}"

        try:
            index = int(args[1])
        except ValueError:
            return "Usage: /artifact <project_id> <index>"
        if index < 1:
            return "Artifact index must be >= 1."

        files = self._list_project_files(project_id)
        if index > len(files):
            return f"Artifact index out of range: {index}."

        file_entry = files[index - 1]
        file_path = self._workspace.resolve_project_file(project_id, file_entry["path"])
        project_name = str(project.get("name", project_id))
        await self._send_text(
            f"Sending file\nProject: {project_name}\nPath: {file_entry['path']}",
            message.conversation_id,
            thread_id=message.thread_id,
        )
        result = await self._plugin.send_file(
            message.conversation_id,
            str(file_path),
            thread_id=message.thread_id,
            caption=self._truncate(f"{project_name} | {file_entry['path']}", 180),
        )
        if not result.success:
            return f"Artifact delivery failed: {result.error or 'unknown error'}"
        return None

    async def _deliver_run_outcome(self, inbound: object, run: RunState) -> None:
        from ds_agent.channels.base import InboundMessage

        message: InboundMessage = inbound  # type: ignore[assignment]
        project_id, project_files = self._recent_project_files_for_run(run)
        deliverables = self._select_run_outcome_deliverables(run, project_id, project_files)
        self._record_run_outcome_event(run, project_id, deliverables)
        if not deliverables:
            return

        for item in deliverables:
            if item.kind == "summary" and item.text:
                await self._send_text(
                    item.text,
                    message.conversation_id,
                    thread_id=message.thread_id,
                )
                continue
            if item.kind == "hint" and item.text:
                await self._send_text(
                    item.text,
                    message.conversation_id,
                    thread_id=message.thread_id,
                )
                continue
            if item.kind != "file" or not item.file_path:
                continue
            result = await self._plugin.send_file(
                message.conversation_id,
                item.file_path,
                thread_id=message.thread_id,
                caption=self._truncate(item.caption or Path(item.file_path).name, 180),
            )
            if not result.success:
                await self._send_text(
                    f"Auto-delivery failed: {result.error or Path(item.file_path).name}",
                    message.conversation_id,
                    thread_id=message.thread_id,
                )

    def _select_run_outcome_deliverables(
        self,
        run: RunState,
        project_id: str | None,
        project_files: list[dict[str, object]],
    ) -> list[object]:
        policy_store = getattr(self, "_delivery_policy_store", None)
        if not isinstance(policy_store, JsonDeliveryPolicyStore):
            return []
        policy = policy_store.get()
        deliverables = select_outcome_deliverables(
            run_status=run.status.value,
            run_message=run.message,
            result_preview=run.result_preview,
            error=run.error,
            project_id=project_id,
            project_files=project_files,
            policy_store=policy_store,
            max_artifacts=policy.platform_defaults.max_auto_send_artifacts_per_run,
        )
        if run.status == RuntimeStatus.SUCCEEDED and not any(
            item.kind in {"file", "hint"} for item in deliverables
        ):
            return []
        return deliverables

    def _recent_project_files_for_run(
        self,
        run: RunState,
    ) -> tuple[str | None, list[dict[str, object]]]:
        workspace = getattr(self, "_workspace", None)
        if not isinstance(workspace, WorkspaceService):
            return None, []

        projects = workspace.list_projects()
        threshold_ms = int(((run.started_at or run.created_at) - 5.0) * 1000)
        candidates: list[tuple[int, str, list[dict[str, object]]]] = []

        for project in projects:
            project_id = str(project.get("id", "")).strip()
            if not project_id:
                continue
            files = self._enriched_project_files(project_id)
            recent = [entry for entry in files if int(entry.get("modifiedAt", 0)) >= threshold_ms]
            if not recent:
                continue
            newest = max(int(entry.get("modifiedAt", 0)) for entry in recent)
            candidates.append((newest, project_id, recent))

        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            _newest, project_id, files = candidates[0]
            return project_id, files

        if len(projects) == 1:
            project_id = str(projects[0].get("id", "")).strip()
            if project_id:
                return project_id, self._enriched_project_files(project_id)
        return None, []

    def _enriched_project_files(self, project_id: str) -> list[dict[str, object]]:
        workspace = getattr(self, "_workspace", None)
        if not isinstance(workspace, WorkspaceService):
            return []

        files: list[dict[str, object]] = []
        for entry in self._list_project_files(project_id):
            path = str(entry.get("path", "")).strip()
            if not path:
                continue
            try:
                full_path = str(workspace.resolve_project_file(project_id, path))
            except (FileNotFoundError, ValueError):
                continue
            enriched = dict(entry)
            enriched["full_path"] = full_path
            files.append(enriched)
        files.sort(key=lambda item: int(item.get("modifiedAt", 0)), reverse=True)
        return files

    def _record_run_outcome_event(
        self,
        run: RunState,
        project_id: str | None,
        deliverables: list[object],
    ) -> None:
        kind = f"run.outcome.{run.status.value}"
        category = "recovery" if run.status == RuntimeStatus.SUCCEEDED else "health"
        severity = {
            RuntimeStatus.SUCCEEDED: "info",
            RuntimeStatus.CANCELLED: "warning",
            RuntimeStatus.FAILED: "error",
        }.get(run.status, "warning")
        if run.status == RuntimeStatus.SUCCEEDED:
            message = f"Run completed: {self._truncate(run.message, 80)}"
        elif run.status == RuntimeStatus.CANCELLED:
            message = f"Run cancelled: {self._truncate(run.message, 80)}"
        else:
            detail = self._truncate(run.error or "unknown error", 120)
            message = f"Run failed: {detail}"

        self._runtime_event_log.record(
            category=category,
            kind=kind,
            severity=severity,
            message=message,
            session_id=run.session_id,
            run_id=run.run_id,
            surface="telegram",
            source="telegram_runner",
            metadata={
                "projectId": project_id,
                "deliverableKinds": [
                    getattr(item, "kind", "") for item in deliverables if getattr(item, "kind", "")
                ],
            },
        )

    def _format_session(self, conversation_id: str, *, thread_id: str | None = None) -> str:
        session_id = self._session_id(conversation_id, thread_id)
        latest_run = self._runs.latest_for_session(session_id) if hasattr(self, "_runs") else None
        checkpoint = self._load_checkpoint(session_id)
        goal_store = getattr(self, "_goal_store", None)
        working_memory_store = getattr(self, "_working_memory_store", None)
        goal = None if goal_store is None else goal_store.get_active_goal(session_id)
        memory = None if working_memory_store is None else working_memory_store.load(session_id)
        pending = self._approval_store.list(
            session_id=session_id,
            status=ApprovalStatus.PENDING,
            limit=3,
        )
        history_messages = self._load_session_messages(session_id, limit=8)

        lines = [f"Session: {self._display_session(session_id)}"]
        lines.append(
            "Latest run: "
            + (
                f"{latest_run.run_id} ({latest_run.status.value})"
                if latest_run is not None
                else "none"
            )
        )
        lines.append(
            "Checkpoint: "
            + (
                f"step {checkpoint.step} / {self._relative_age(checkpoint.updated_at)}"
                if checkpoint is not None
                else "none"
            )
        )
        lines.append(
            "Goal: "
            + (
                f"{goal.status.value} / {self._truncate(goal.summary, 60)}"
                if goal is not None
                else "none"
            )
        )
        lines.append(f"Pending approvals: {len(pending)}")
        lines.append(f"Recent messages: {len(history_messages)}")
        if memory is not None and memory.current_summary:
            lines.append(f"Summary: {self._truncate(memory.current_summary, 90)}")
        if memory is not None and memory.next_step:
            lines.append(f"Next: {self._truncate(memory.next_step, 90)}")
        if memory is not None and memory.recovery_note:
            lines.append(f"Recovery: {self._truncate(memory.recovery_note, 90)}")
        return "\n".join(lines)

    def _format_history(
        self,
        conversation_id: str,
        count_arg: str | None,
        *,
        thread_id: str | None = None,
    ) -> str:
        count = _DEFAULT_HISTORY_LIMIT
        if count_arg is not None:
            try:
                count = max(1, min(_MAX_HISTORY_LIMIT, int(count_arg)))
            except ValueError:
                return "Usage: /history [count]"

        session_id = self._session_id(conversation_id, thread_id)
        messages = [
            message
            for message in self._load_session_messages(session_id, limit=count * 4)
            if message.role in {Role.USER, Role.ASSISTANT}
        ]
        messages = messages[-count:]
        if not messages:
            return "Recent history: none"

        lines = [f"Recent history ({len(messages)}):"]
        for message in messages:
            label = "U" if message.role == Role.USER else "A"
            content = message.content or "[no text]"
            lines.append(f"- {label}: {self._truncate(content, 100)}")
        return "\n".join(lines)

    async def _handle_resume_command(self, inbound: object) -> str | None:
        from ds_agent.channels.base import InboundMessage

        message: InboundMessage = inbound  # type: ignore[assignment]
        session_id = self._session_id(message.conversation_id, message.thread_id)
        active = self._resolve_run_for_control(
            message.conversation_id,
            None,
            thread_id=message.thread_id,
        )
        if active is not None and active.status == RuntimeStatus.RUNNING:
            return f"Run already active: {active.run_id}"

        checkpoint = self._load_checkpoint(session_id)
        goal_store = getattr(self, "_goal_store", None)
        working_memory_store = getattr(self, "_working_memory_store", None)
        goal = None if goal_store is None else goal_store.get_active_goal(session_id)
        memory = None if working_memory_store is None else working_memory_store.load(session_id)
        latest_run = self._runs.latest_for_session(session_id) if hasattr(self, "_runs") else None

        if checkpoint is None and goal is None and memory is None and latest_run is None:
            return "No resumable context for this chat."

        resume_prompt = self._build_resume_prompt(
            checkpoint=checkpoint,
            goal=goal,
            memory=memory,
            latest_run=latest_run,
        )
        announce_text = "Resuming current session..."
        if checkpoint is not None:
            announce_text = f"Resuming from checkpoint step {checkpoint.step}..."
        await self._execute_agent_turn(message, resume_prompt, announce_text=announce_text)
        self._record_operator_action(
            action="Resume",
            target_id=session_id,
            actor=message.sender_id,
            chat_id=message.conversation_id,
            thread_id=message.thread_id,
            outcome=announce_text,
        )
        return None

    def _build_resume_prompt(
        self,
        *,
        checkpoint: SessionCheckpoint | None,
        goal: GoalRecord | None,
        memory: SessionWorkingMemory | None,
        latest_run: RunState | None,
    ) -> str:
        parts = [
            (
                "Resume the current Telegram session using the persisted "
                "checkpoint and working memory."
            ),
            (
                "Start by briefly stating what you are resuming, then "
                "continue with the next concrete step."
            ),
        ]
        if goal is not None:
            parts.append(f"Active goal: {goal.summary}")
        if memory is not None and memory.current_summary:
            parts.append(f"Current summary: {memory.current_summary}")
        if memory is not None and memory.next_step:
            parts.append(f"Suggested next step: {memory.next_step}")
        if memory is not None and memory.recovery_note:
            parts.append(f"Recovery note: {memory.recovery_note}")
        if checkpoint is not None:
            parts.append(f"Checkpoint step: {checkpoint.step}")
        if latest_run is not None:
            parts.append(f"Latest run status: {latest_run.status.value}")
        if latest_run is not None and latest_run.error:
            parts.append(f"Latest run error: {latest_run.error}")
        return "\n".join(parts)

    def _resolve_approval(
        self,
        conversation_id: str,
        approval_id: str | None,
        *,
        thread_id: str | None = None,
    ) -> ApprovalRequest | None:
        if approval_id:
            return self._approval_store.get(approval_id)
        return self._approval_store.latest_pending_for_session(
            self._session_id(conversation_id, thread_id)
        )

    def _queue_position_text(self, approval_id: str) -> str:
        pending = sorted(
            self._approval_store.list(status=ApprovalStatus.PENDING, limit=10_000),
            key=lambda item: item.created_at,
        )
        total = len(pending)
        for index, approval in enumerate(pending, start=1):
            if approval.approval_id == approval_id:
                return f"{index}/{total}"
        return f"-/{total}" if total else "-/-"

    def _format_approval_resolution_summary(self, approval: ApprovalRequest) -> str:
        remaining = self._approval_store.pending_count
        lines = [
            f"Approval {approval.status.value}",
            f"ID: {approval.approval_id}",
            f"Session: {self._display_session(approval.session_id)}",
            f"Run: {approval.run_id or '-'}",
            f"Response: {approval.response or '-'}",
            f"Pending left: {remaining}",
            "Next: /approvals to inspect the queue.",
        ]
        return "\n".join(lines)

    async def _poll_runtime_alerts(self) -> None:
        while True:
            await asyncio.sleep(_ALERT_POLL_INTERVAL_SECONDS)
            try:
                await self._process_runtime_alerts_once()
            except Exception as exc:
                logger.warning("telegram_alert_poll_failed", error=str(exc))

    async def _process_runtime_alerts_once(self) -> None:
        if not self._operator_chats:
            return

        self._delivery_rate_limiter = self._build_delivery_rate_limiter()
        events = self._runtime_event_log.list(limit=20)
        for event in reversed(events):
            if event.event_id in self._seen_runtime_event_ids:
                continue
            self._seen_runtime_event_ids.add(event.event_id)
            classified = classify_event(event)
            if not self._should_route_runtime_event(event, classified):
                continue
            is_escalation = self._should_escalate_runtime_event(event, classified)
            throttle_checked = False
            throttle_allowed = False
            throttle_reason = "rate_limited"
            for conversation_id in sorted(self._operator_chats):
                decision, suppress_reason = self._chat_alert_delivery_decision(
                    conversation_id,
                    event,
                    classified=classified,
                    force_escalation=is_escalation,
                )
                if decision in {DeliveryDecision.SUPPRESS, DeliveryDecision.DIGEST_ONLY}:
                    if suppress_reason is not None and suppress_reason != "acknowledged":
                        self._alert_state.record_suppressed(
                            conversation_id,
                            event.event_id,
                            suppress_reason,
                        )
                    continue
                if not throttle_checked:
                    throttle_allowed = self._passes_alert_throttle(
                        conversation_id,
                        event,
                        is_escalation=decision == DeliveryDecision.ESCALATE,
                    )
                    throttle_reason = self._rate_limit_reason(
                        conversation_id,
                        event,
                        is_escalation=decision == DeliveryDecision.ESCALATE,
                    )
                    throttle_checked = True
                if not throttle_allowed:
                    self._alert_state.record_suppressed(
                        conversation_id,
                        event.event_id,
                        throttle_reason,
                    )
                    continue
                target = self._delivery_target_for_event(conversation_id, event)
                notification = self._build_runtime_event_notification(
                    event,
                    classified=classified,
                    chat_id=conversation_id,
                )
                await self.dispatch_notification(
                    notification,
                    target.conversation_id,
                    thread_id=target.thread_id,
                )
        await self._send_due_digests()
        self._trim_seen_runtime_events()

    def _seed_seen_runtime_events(self) -> None:
        events = self._runtime_event_log.list(limit=100)
        self._seen_runtime_event_ids = {event.event_id for event in events}

    def _trim_seen_runtime_events(self) -> None:
        if len(self._seen_runtime_event_ids) <= 200:
            return
        events = self._runtime_event_log.list(limit=200)
        self._seen_runtime_event_ids = {event.event_id for event in events}

    @staticmethod
    def _should_route_runtime_event(
        event: RuntimeEventRecord,
        classified: ClassifiedEvent,
    ) -> bool:
        if event.kind == "policy.suppressed":
            reason = str(event.metadata.get("policyReason", "")).strip()
            return reason in {"resource_pressure", "dispatch_throttled", "run_already_active"}
        if classified.actionable:
            return True
        if classified.severity in {"error", "critical"}:
            return True
        if classified.category in {"approval", "recovery", "pressure"}:
            return True
        return classified.urgency != "low"

    def _passes_alert_throttle(
        self,
        conversation_id: str,
        event: RuntimeEventRecord,
        *,
        is_escalation: bool,
    ) -> bool:
        limiter = getattr(self, "_delivery_rate_limiter", None)
        if not isinstance(limiter, DeliveryRateLimiter):
            return True
        settings = self._effective_delivery_settings(conversation_id)
        return limiter.should_deliver(
            event.kind,
            event.severity or "info",
            is_escalation=is_escalation,
            quiet_hours=settings.quiet_hours,
        )

    def _chat_alert_delivery_decision(
        self,
        conversation_id: str,
        event: RuntimeEventRecord,
        *,
        classified: ClassifiedEvent,
        force_escalation: bool = False,
    ) -> tuple[DeliveryDecision, str | None]:
        pref = self._preferences.get(conversation_id)
        settings = self._effective_delivery_settings(conversation_id)
        if self._alert_state.is_acknowledged(conversation_id, event.event_id):
            return DeliveryDecision.SUPPRESS, "acknowledged"

        decision = evaluate_delivery(
            classified,
            chat_enabled=settings.enabled,
            chat_min_severity=settings.min_severity,
            chat_subscribed_categories=settings.subscribed_categories,
            chat_muted=self._alert_state.is_muted(conversation_id),
            chat_approvals_only=settings.approvals_only,
            chat_digest_mode=settings.digest_enabled,
        )

        if decision == DeliveryDecision.SUPPRESS:
            if not settings.enabled:
                return DeliveryDecision.SUPPRESS, "disabled"
            if self._alert_state.is_muted(conversation_id) and classified.severity != "critical":
                return DeliveryDecision.SUPPRESS, "muted"
            return DeliveryDecision.SUPPRESS, self._suppression_reason_for_chat(pref, classified)
        if decision == DeliveryDecision.DIGEST_ONLY:
            return DeliveryDecision.DIGEST_ONLY, "digest"
        if decision == DeliveryDecision.ESCALATE and not settings.escalation_enabled:
            decision = DeliveryDecision.LIVE_PUSH
        if decision != DeliveryDecision.ESCALATE and not settings.live_push_enabled:
            if settings.digest_enabled and classified.category != "approval":
                return DeliveryDecision.DIGEST_ONLY, "digest"
            return DeliveryDecision.SUPPRESS, "policy_disabled"
        if (
            force_escalation
            and decision == DeliveryDecision.LIVE_PUSH
            and settings.escalation_enabled
            and not self._alert_state.is_muted(conversation_id)
        ):
            return DeliveryDecision.ESCALATE, None
        return decision, None

    def _effective_digest_settings(self, conversation_id: str) -> tuple[bool, float, str, str]:
        settings = self._effective_delivery_settings(conversation_id)
        return (
            settings.digest_enabled,
            settings.digest_interval_seconds,
            settings.digest_cadence,
            settings.timezone,
        )

    def _effective_delivery_settings(self, conversation_id: str) -> EffectiveDeliverySettings:
        pref = self._preferences.get(conversation_id)
        return resolve_effective_delivery_settings(pref, self._delivery_policy())

    @staticmethod
    def _suppression_reason_for_chat(
        pref: object,
        classified: ClassifiedEvent,
    ) -> str | None:
        enabled = getattr(pref, "enabled", True)
        approvals_only = getattr(pref, "approvals_only", False)
        subscribed = set(getattr(pref, "subscribed_categories", set()))
        min_severity = str(getattr(pref, "min_severity", "warning"))
        muted_until = float(getattr(pref, "muted_until", 0.0))
        if not enabled:
            return "disabled"
        if approvals_only and classified.category != "approval":
            return None
        if subscribed and classified.category not in subscribed:
            return None
        if TelegramGatewayRunner._severity_index(
            classified.severity
        ) < TelegramGatewayRunner._severity_index(min_severity):
            return None
        if muted_until > time.time() and classified.severity != "critical":
            return "muted"
        return None

    def _should_escalate_runtime_event(
        self,
        event: RuntimeEventRecord,
        classified: ClassifiedEvent,
    ) -> bool:
        policy = self._delivery_policy()
        if not policy.escalation_enabled:
            return False
        failure_key = self._event_failure_key(event, classified)
        if failure_key is None:
            return False
        limiter = getattr(self, "_delivery_rate_limiter", None)
        if not isinstance(limiter, DeliveryRateLimiter):
            return False
        return limiter.record_failure(failure_key)

    @staticmethod
    def _event_failure_key(
        event: RuntimeEventRecord,
        classified: ClassifiedEvent,
    ) -> str | None:
        if event.kind in {
            "pipeline.health.degraded",
            "model.monitor.degraded",
            "policy.dispatch_failed",
            "run.outcome.failed",
            "recovery.awaiting_approval",
        }:
            return f"{event.kind}:{event.session_id or '-'}"
        if classified.severity == "critical":
            return f"{event.kind}:{event.session_id or '-'}"
        if classified.category == "health" and classified.severity == "error":
            return f"{event.kind}:{event.session_id or '-'}"
        return None

    def _rate_limit_reason(
        self,
        conversation_id: str,
        event: RuntimeEventRecord,
        *,
        is_escalation: bool,
    ) -> str:
        limiter = getattr(self, "_delivery_rate_limiter", None)
        if not isinstance(limiter, DeliveryRateLimiter):
            return "rate_limited"
        settings = self._effective_delivery_settings(conversation_id)
        if (
            limiter.is_in_quiet_hours_for(quiet_hours=settings.quiet_hours)
            and not is_escalation
            and (event.severity or "info") != "critical"
        ):
            return "quiet_hours"
        return "rate_limited"

    def _build_delivery_rate_limiter(self) -> DeliveryRateLimiter:
        policy = self._delivery_policy()
        return DeliveryRateLimiter(
            escalation_threshold=max(1, int(policy.escalation_repeat_threshold)),
        )

    def _delivery_policy(self) -> DeliveryPolicy:
        policy_store = getattr(self, "_delivery_policy_store", None)
        if isinstance(policy_store, JsonDeliveryPolicyStore):
            return policy_store.get()
        return DeliveryPolicy()

    @staticmethod
    def _quiet_hours_window(policy: DeliveryPolicy) -> QuietHoursWindow:
        start = TelegramGatewayRunner._parse_quiet_hour(policy.quiet_hours_start)
        end = TelegramGatewayRunner._parse_quiet_hour(policy.quiet_hours_end)
        if start is None or end is None:
            return QuietHoursWindow()
        return QuietHoursWindow(
            start_hour=start,
            end_hour=end,
            timezone=policy.quiet_hours_timezone or "UTC",
            enabled=True,
        )

    @staticmethod
    def _parse_quiet_hour(value: str) -> int | None:
        text = value.strip()
        if not text:
            return None
        try:
            hour_text, *_rest = text.split(":", maxsplit=1)
            hour = int(hour_text)
        except ValueError:
            return None
        if 0 <= hour <= 23:
            return hour
        return None

    @staticmethod
    def _is_valid_timezone(value: str) -> bool:
        try:
            from zoneinfo import ZoneInfo

            ZoneInfo(value)
            return True
        except Exception:
            return False

    async def _send_due_digests(self) -> None:
        for conversation_id in sorted(self._operator_chats):
            await self._send_digest_for_chat(conversation_id)

    async def _send_digest_for_chat(
        self,
        conversation_id: str,
        *,
        thread_id: str | None = None,
        force: bool = False,
    ) -> str | None:
        digest_mode, digest_interval, digest_cadence, digest_timezone = (
            self._effective_digest_settings(conversation_id)
        )
        suppressed = self._alert_state.list_suppressed(conversation_id, limit=50)
        if not suppressed:
            return "No suppressed alerts waiting for digest delivery." if force else None
        if not force:
            if not digest_mode:
                return None
            if not self._alert_state.should_send_digest(
                conversation_id,
                digest_interval,
                cadence=digest_cadence,
                timezone=digest_timezone,
            ):
                return None

        digest_notification, delivered_event_ids = self._build_chat_digest(
            conversation_id,
            suppressed,
        )
        if digest_notification is None or not delivered_event_ids:
            self._alert_state.mark_digest_sent(conversation_id)
            return "No digestible alerts remain." if force else None

        built = await self.dispatch_notification(
            digest_notification,
            conversation_id,
            thread_id=thread_id,
        )
        self._alert_state.mark_digest_sent(
            conversation_id,
            delivered_event_ids=delivered_event_ids,
        )
        return built.text

    def _build_chat_digest(
        self,
        conversation_id: str,
        suppressed: list[object],
    ) -> tuple[Notification | None, list[str]]:
        items: list[tuple[RuntimeEventRecord, str]] = []
        for record in suppressed:
            event_id = getattr(record, "event_id", "")
            reason = str(getattr(record, "reason", "unknown"))
            event = self._runtime_event_log.get(event_id)
            if event is None:
                continue
            items.append((event, reason))

        if not items:
            return (None, [])

        items.sort(key=lambda item: item[0].created_at, reverse=True)
        digest = build_digest_from_events([event for event, _reason in items])
        digest_lines = digest.text.splitlines()
        digest_body = "\n".join(digest_lines[1:]) if len(digest_lines) > 1 else ""
        lines = [f"Digest ({len(items)} suppressed alerts):"]
        if digest_body:
            lines.append(digest_body)
        lines.append("Alert summary:")
        for event, _reason in items[:5]:
            lines.append(self._format_alert_digest_line(conversation_id, event))
        if len(items) > 5:
            lines.append(f"- + {len(items) - 5} more suppressed alerts")
        lines.append("Use /alerts 10 to inspect full history.")
        text = "\n".join(lines)
        title, body = self._split_notification_text(text)
        return (
            Notification(
                category=NotificationCategory.DIGEST,
                title=title,
                body=body,
                deep_link=self._deep_link_for_events([event for event, _reason in items]),
                workspace_id=self._deep_link_workspace_id(),
                run_id=next((event.run_id for event, _reason in items if event.run_id), None),
            ),
            [event.event_id for event, _reason in items],
        )

    @staticmethod
    def _should_bypass_soft_controls(event: RuntimeEventRecord) -> bool:
        return (event.severity or "info") == "critical"

    # ------------------------------------------------------------------
    # Semantic proposals (Phase 7)
    # ------------------------------------------------------------------

    async def _handle_semantic_proposal_command(
        self,
        inbound: object,
        args: list[str],
    ) -> str:
        """Handle /semantic_proposal [list|approve|reject|diff] <id>."""
        from ds_agent.channels.base import InboundMessage
        from ds_agent.gateway.telegram_semantic import (
            format_proposal_detail,
            format_proposal_diff,
            format_proposal_list,
        )

        msg: InboundMessage = inbound  # type: ignore[assignment]
        sub = args[0].lower() if args else "list"

        try:
            repo = self._get_semantic_proposal_repo()
        except Exception:
            return (
                "Semantic proposal store is not available. "
                "Ensure the semantic memory module is configured."
            )

        if sub == "list":
            proposals = repo.list_pending(limit=10)
            return format_proposal_list(proposals)

        if sub in {"approve", "reject"} and len(args) >= 2:
            proposal_id = args[1]
            proposal = repo.get(proposal_id)
            if proposal is None:
                return f"Proposal {proposal_id} not found."
            from datetime import UTC, datetime

            from ds_agent.memory.semantic.domain.proposal import (
                SemanticProposalStatus,
            )

            target = (
                SemanticProposalStatus.APPROVED
                if sub == "approve"
                else SemanticProposalStatus.REJECTED
            )
            now = datetime.now(UTC)
            try:
                updated = proposal.transition_to(
                    target,
                    reviewed_by=f"telegram:{msg.sender_id}",
                    reviewed_at=now,
                )
            except ValueError as exc:
                return f"Cannot {sub} proposal {proposal_id}: {exc}"
            repo.update(updated)
            action_label_text = "Approved" if sub == "approve" else "Rejected"
            return f"{action_label_text} proposal {proposal_id}.\n{format_proposal_detail(updated)}"

        if sub == "diff" and len(args) >= 2:
            proposal_id = args[1]
            proposal = repo.get(proposal_id)
            if proposal is None:
                return f"Proposal {proposal_id} not found."
            return format_proposal_diff(proposal)

        if len(args) == 1 and sub not in {"list", "approve", "reject", "diff"}:
            proposal = repo.get(sub)
            if proposal is not None:
                return format_proposal_detail(proposal)

        return (
            "Usage: /semantic_proposal [list|approve|reject|diff] <id>\n"
            "  list             — pending proposals\n"
            "  approve <id>     — approve a proposal\n"
            "  reject <id>      — reject a proposal\n"
            "  diff <id>        — show payload diff\n"
            "  <id>             — show proposal detail"
        )

    def _get_semantic_proposal_repo(self) -> object:
        """Lazy-load the semantic proposal repository."""
        from ds_agent.memory.semantic.infrastructure import (
            SemanticSqliteDatabase,
            SqliteSemanticProposalRepository,
        )

        workspace = self._config.agent.workspace_dir
        db = SemanticSqliteDatabase(workspace)
        return SqliteSemanticProposalRepository(db)

    # ------------------------------------------------------------------
    # Inline actions (PLAN_13 Phase 01)
    # ------------------------------------------------------------------

    async def _handle_callback_query(self, inbound: object) -> None:
        """Resolve an inline keyboard button press via action token."""
        from ds_agent.channels.base import InboundMessage

        msg: InboundMessage = inbound  # type: ignore[assignment]
        token = msg.callback_data or ""
        query_id = msg.callback_query_id or ""

        if token.startswith(f"{CALLBACK_PREFIX}:"):
            await self._handle_approval_callback_query(msg)
            return

        ctx = self._action_tokens.resolve(token)
        if ctx is None:
            await self._plugin.answer_callback_query(
                query_id,
                text=(
                    "This action has expired. Use /approvals or /runs to inspect the current state."
                ),
                show_alert=True,
            )
            return

        scope_error = self._validate_callback_scope(msg, ctx.actor, ctx.chat_id, ctx.target_id)
        if scope_error is not None:
            await self._plugin.answer_callback_query(
                query_id,
                text=scope_error,
                show_alert=True,
            )
            return

        ctx = self._action_tokens.consume(token)
        if ctx is None:
            await self._plugin.answer_callback_query(
                query_id,
                text="This action was already used. Use text commands to inspect the latest state.",
                show_alert=True,
            )
            return

        await self._plugin.answer_callback_query(
            query_id,
            text=self._callback_processing_text(ctx.action),
        )

        reply_text: str | None = None
        if ctx.action == ACTION_APPROVE:
            resolved = self._approval_store.resolve(
                ctx.target_id,
                status=ApprovalStatus.APPROVED,
                response=None,
                source="telegram_inline",
                actor=msg.sender_id,
            )
            if resolved is not None:
                reply_text = self._format_approval_resolution_summary(resolved)
            else:
                existing = self._approval_store.get(ctx.target_id)
                status = "resolved" if existing is None else existing.status.value
                reply_text = (
                    f"Approval {ctx.target_id} is already {status}. "
                    f"Use /approval {ctx.target_id} to inspect the recorded response."
                )

        elif ctx.action == ACTION_REJECT:
            resolved = self._approval_store.resolve(
                ctx.target_id,
                status=ApprovalStatus.REJECTED,
                response=None,
                source="telegram_inline",
                actor=msg.sender_id,
            )
            if resolved is not None:
                reply_text = self._format_approval_resolution_summary(resolved)
            else:
                existing = self._approval_store.get(ctx.target_id)
                status = "resolved" if existing is None else existing.status.value
                reply_text = (
                    f"Approval {ctx.target_id} is already {status}. "
                    f"Use /approval {ctx.target_id} to inspect the recorded response."
                )

        elif ctx.action == ACTION_STOP:
            active = self._runs.get(ctx.target_id) if hasattr(self, "_runs") else None
            if active is None:
                reply_text = f"Unknown run id: {ctx.target_id}. Use /runs to inspect recent runs."
            elif active.status == RuntimeStatus.RUNNING:
                self._task_ledger.cancel_for_run(ctx.target_id)
                reply_text = f"Stopped run {ctx.target_id}."
            else:
                reply_text = (
                    f"Run {ctx.target_id} is {active.status.value}; nothing to stop. "
                    f"Use /run {ctx.target_id} to inspect the current state."
                )

        elif ctx.action == ACTION_INSPECT:
            run = self._runs.get(ctx.target_id) if hasattr(self, "_runs") else None
            if run is not None:
                reply_text = self._format_run_detail(
                    msg.conversation_id,
                    ctx.target_id,
                    thread_id=msg.thread_id,
                )
            else:
                reply_text = f"Unknown run id: {ctx.target_id}. Use /runs to inspect recent runs."

        elif ctx.action == ACTION_RESUME:
            reply_text = await self._handle_resume_callback(msg, ctx.target_id)

        elif ctx.action == ACTION_ACK:
            reply_text = self._handle_ack_command(msg, ctx.target_id)

        elif ctx.action == ACTION_MUTE:
            reply_text = self._handle_mute_command(msg, ctx.target_id)

        if ctx.action not in {ACTION_ACK, ACTION_MUTE, ACTION_RESUME}:
            self._record_operator_action(
                action=action_label(ctx.action),
                target_id=ctx.target_id,
                actor=msg.sender_id,
                chat_id=msg.conversation_id,
                thread_id=msg.thread_id,
                outcome=reply_text or "ok",
            )

        if msg.source_message_id:
            await self._plugin.edit_message_reply_markup(
                msg.conversation_id,
                msg.source_message_id,
                reply_markup=None,
            )

        if reply_text:
            await self._send_text(
                reply_text,
                msg.conversation_id,
                thread_id=msg.thread_id,
            )

    async def _handle_approval_callback_query(self, inbound: object) -> None:
        from ds_agent.channels.base import InboundMessage

        msg: InboundMessage = inbound  # type: ignore[assignment]
        token = msg.callback_data or ""
        query_id = msg.callback_query_id or ""

        try:
            parsed = parse_approval_callback(token)
        except CallbackParseError as exc:
            await self._plugin.answer_callback_query(
                query_id,
                text=f"Bad action: {exc}",
                show_alert=True,
            )
            return

        approval = self._approval_store.get(parsed.approval_id)
        if approval is None:
            await self._plugin.answer_callback_query(
                query_id,
                text=(
                    f"Unknown approval id: {parsed.approval_id}. "
                    "Use /approvals to inspect the queue."
                ),
                show_alert=True,
            )
            return

        scope_error = self._validate_approval_callback_scope(msg, approval)
        if scope_error is not None:
            await self._plugin.answer_callback_query(
                query_id,
                text=scope_error,
                show_alert=True,
            )
            return

        handler = TelegramApprovalCallbackHandler(_TelegramApprovalSubmitter(self))
        result = await handler.handle(
            callback_data=token,
            operator_id=msg.sender_id,
        )
        await self._plugin.answer_callback_query(
            query_id,
            text=result.user_visible_text,
            show_alert=not result.handled,
        )

        if msg.source_message_id and result.handled:
            await self._plugin.edit_message_reply_markup(
                msg.conversation_id,
                msg.source_message_id,
                reply_markup=None,
            )

        if result.outcome is None or not result.outcome.success:
            return

        resolved = self._approval_store.get(parsed.approval_id)
        if resolved is None:
            return
        reply_text = self._format_approval_resolution_summary(resolved)
        self._record_operator_action(
            action="Approve" if parsed.decision == "approve" else "Reject",
            target_id=resolved.approval_id,
            actor=msg.sender_id,
            chat_id=msg.conversation_id,
            thread_id=msg.thread_id,
            outcome=reply_text,
        )
        await self._send_text(
            reply_text,
            msg.conversation_id,
            thread_id=msg.thread_id,
        )

    async def _submit_approval_callback(
        self,
        *,
        approval_id: str,
        decision: str,
        operator_id: str,
        reason: str | None,
    ) -> ApprovalSubmitOutcome:
        from ds_agent.application.use_cases.submit_approval_usecase import (
            SubmitApprovalUseCase,
        )

        decision_value = "allow" if decision == "approve" else "deny"
        try:
            result = SubmitApprovalUseCase(self._approval_store).execute(
                {
                    "approvalId": approval_id,
                    "decision": decision_value,
                    "denyReason": reason if decision_value == "deny" else None,
                    "response": reason if decision_value == "allow" else None,
                    "actor": operator_id,
                    "source": "telegram_inline_callback",
                }
            )
        except ValueError as exc:
            return ApprovalSubmitOutcome(success=False, message=str(exc))

        approval = result.approval
        if approval is not None:
            self._finalize_submitted_approval(
                approval=approval,
                operator_id=operator_id,
            )

        return ApprovalSubmitOutcome(
            success=True,
            message=result.status,
            new_status=result.status,
        )

    def _finalize_submitted_approval(
        self,
        *,
        approval: ApprovalRequest,
        operator_id: str,
    ) -> None:
        if approval.kind != "semantic_proposal":
            return

        from ds_agent.runtime.semantic_proposal_router import (
            resolve_semantic_proposal_approval,
        )

        reviewer = operator_id.strip() or "operator"
        outcome = resolve_semantic_proposal_approval(
            approval,
            workspace_dir=self._config.agent.workspace_dir,
            reviewer=reviewer,
        )
        metadata = dict(approval.metadata or {})
        metadata["semanticProposalOutcome"] = {
            "proposalId": outcome.proposal_id,
            "proposalStatus": outcome.proposal_status,
            "action": outcome.action,
            "applied": outcome.applied,
            "appliedTarget": outcome.applied_target,
        }
        approval.metadata = metadata
        self._approval_store.replace(approval)
        self._runtime_event_log.record(
            category="approval",
            kind=("semantic.proposal.applied" if outcome.applied else "semantic.proposal.reviewed"),
            severity="success" if approval.status == ApprovalStatus.APPROVED else "warning",
            message=(
                f"Semantic proposal {outcome.action}d: {outcome.proposal_id}"
                if outcome.action != "apply"
                else f"Semantic proposal applied: {outcome.proposal_id}"
            ),
            session_id=approval.session_id,
            run_id=approval.run_id,
            surface=approval.surface,
            source="telegram_runner",
            metadata=metadata,
        )

    def _validate_approval_callback_scope(
        self,
        message: object,
        approval: ApprovalRequest,
    ) -> str | None:
        from ds_agent.channels.base import InboundMessage

        inbound: InboundMessage = message  # type: ignore[assignment]
        session_id = approval.session_id
        if not session_id.startswith("telegram:"):
            return None
        target_chat_id, target_thread = parse_telegram_session_id(session_id)
        if target_chat_id != inbound.conversation_id:
            return "This approval belongs to another chat. Use /approvals there instead."
        if target_thread is not None and target_thread != inbound.thread_id:
            return "This approval belongs to another topic. Use /approvals in that topic."
        return None

    def _validate_callback_scope(
        self,
        message: object,
        actor: str,
        chat_id: str,
        target_id: str,
    ) -> str | None:
        from ds_agent.channels.base import InboundMessage

        inbound: InboundMessage = message  # type: ignore[assignment]
        if chat_id and chat_id != inbound.conversation_id:
            return "This button belongs to another chat. Use commands in the current chat instead."
        if actor and actor != inbound.sender_id:
            return (
                "This button is limited to the original operator. Use a text command to take over."
            )
        if target_id.startswith("telegram:"):
            target_chat_id, target_thread = parse_telegram_session_id(target_id)
            if target_chat_id != inbound.conversation_id:
                return "This recovery action belongs to another chat. Use /session there first."
            if target_thread is not None and target_thread != inbound.thread_id:
                return (
                    "This recovery action belongs to another topic. "
                    "Use /session in that topic instead."
                )
        return None

    @staticmethod
    def _callback_processing_text(action: str) -> str:
        return {
            ACTION_APPROVE: "Approving...",
            ACTION_REJECT: "Rejecting...",
            ACTION_STOP: "Stopping...",
            ACTION_RESUME: "Resuming...",
            ACTION_INSPECT: "Inspecting...",
            ACTION_ACK: "Acknowledging...",
            ACTION_MUTE: "Muting...",
        }.get(action, "Processing...")

    async def _handle_resume_callback(
        self,
        message: object,
        target_session_id: str,
    ) -> str | None:
        from ds_agent.channels.base import InboundMessage

        inbound: InboundMessage = message  # type: ignore[assignment]
        if target_session_id.startswith("telegram:"):
            target_chat_id, target_thread = parse_telegram_session_id(target_session_id)
            if target_chat_id != inbound.conversation_id:
                return (
                    "Recovery state moved to another chat. Use /session in that chat to inspect it."
                )
            if target_thread is not None and target_thread != inbound.thread_id:
                return (
                    "Recovery state belongs to another topic. "
                    "Use /session in that topic to inspect it."
                )
        outcome = await self._handle_resume_command(inbound)
        if outcome is None:
            return "Resuming current session..."
        return outcome

    def _build_approval_markup(
        self,
        approval_id: str,
        *,
        actor: str = "",
        chat_id: str = "",
    ) -> dict:
        """Build an InlineKeyboardMarkup dict for an approval request."""
        _ = actor, chat_id
        return {
            "inline_keyboard": [
                [
                    {
                        "text": "Approve",
                        "callback_data": f"{CALLBACK_PREFIX}:approve:{approval_id}",
                    },
                    {
                        "text": "Reject",
                        "callback_data": f"{CALLBACK_PREFIX}:reject:{approval_id}",
                    },
                ],
            ],
        }

    def _build_run_markup(
        self,
        run_id: str,
        *,
        running: bool = False,
        actor: str = "",
        chat_id: str = "",
    ) -> dict:
        """Build an InlineKeyboardMarkup dict for a run summary."""
        buttons: list[dict] = []
        inspect_token = self._action_tokens.create(
            ACTION_INSPECT,
            run_id,
            actor=actor,
            chat_id=chat_id,
        )
        buttons.append({"text": "Inspect", "callback_data": inspect_token})
        if running:
            stop_token = self._action_tokens.create(
                ACTION_STOP,
                run_id,
                actor=actor,
                chat_id=chat_id,
            )
            buttons.append({"text": "Stop", "callback_data": stop_token})
        return {"inline_keyboard": [buttons]}

    def _build_alert_buttons(
        self,
        event: RuntimeEventRecord,
        *,
        chat_id: str,
    ) -> tuple[InlineButton, ...]:
        buttons: list[InlineButton] = []
        if event.kind == "recovery.resume_recommended" and event.session_id:
            resume_token = self._action_tokens.create(
                ACTION_RESUME,
                event.session_id,
                chat_id=chat_id,
            )
            buttons.append(InlineButton(text="Resume", callback_data=resume_token))
        if event.run_id:
            inspect_token = self._action_tokens.create(
                ACTION_INSPECT,
                event.run_id,
                chat_id=chat_id,
            )
            buttons.append(InlineButton(text="Inspect", callback_data=inspect_token))

        ack_token = self._action_tokens.create(
            ACTION_ACK,
            event.event_id,
            chat_id=chat_id,
        )
        mute_token = self._action_tokens.create(
            ACTION_MUTE,
            _ACK_ACTION_MUTE_WINDOW,
            chat_id=chat_id,
        )
        buttons.append(InlineButton(text="Ack", callback_data=ack_token))
        buttons.append(InlineButton(text="Mute 30m", callback_data=mute_token))
        return tuple(buttons)

    @staticmethod
    def _deep_link_workspace_id() -> str:
        return _DEFAULT_DEEP_LINK_WORKSPACE_ID

    def _deep_link_for_events(self, events: list[RuntimeEventRecord]) -> str | None:
        for event in events:
            link = self._deep_link_for_event(event)
            if link is not None:
                return link
        return None

    def _deep_link_for_event(self, event: RuntimeEventRecord) -> str | None:
        run_id = event.run_id
        if not run_id:
            return None
        try:
            from ds_agent.domain.value_objects.deep_link import DeepLink, build_deep_link_uri
        except ImportError:
            workspace_id = self._deep_link_workspace_id()
            return f"ds-agent://workspace/{workspace_id}/run/{run_id}"
        return build_deep_link_uri(
            DeepLink(
                workspace_id=self._deep_link_workspace_id(),
                resource_type="run",
                resource_id=run_id,
            )
        )

    # ------------------------------------------------------------------
    # Notification preference commands (PLAN_13 Phase 00)
    # ------------------------------------------------------------------

    def _handle_notify_command(self, inbound: object, args: list[str]) -> str:
        from ds_agent.channels.base import InboundMessage

        message: InboundMessage = inbound  # type: ignore[assignment]
        conversation_id = message.conversation_id
        if not args:
            return (
                "Usage: /notify approvals|all|off|on|reset\n"
                "Usage: /notify add|remove|only <categories>\n"
                f"Categories: {self._available_notification_categories_text()}"
            )

        mode = args[0].strip().lower()
        outcome: str
        if mode == "approvals":
            self._preferences.set_enabled(conversation_id, True)
            self._preferences.set_approvals_only(conversation_id, True)
            self._preferences.set_subscribed_categories(
                conversation_id,
                {"approval"},
            )
            outcome = (
                "Notification mode saved: approvals only.\n"
                "Recovery and health alerts are paused until you widen subscriptions."
            )
        elif mode == "all":
            self._preferences.set_enabled(conversation_id, True)
            self._preferences.set_approvals_only(conversation_id, False)
            self._preferences.set_subscribed_categories(
                conversation_id,
                set(DEFAULT_NOTIFICATION_CATEGORIES),
            )
            outcome = "Notification mode saved: all default alert categories."
        elif mode == "off":
            self._preferences.set_enabled(conversation_id, False)
            outcome = "Live notifications disabled for this chat. Use /notify on to restore them."
        elif mode == "on":
            self._preferences.set_enabled(conversation_id, True)
            outcome = "Live notifications enabled for this chat."
        elif mode == "reset":
            self._preferences.set_enabled(conversation_id, True)
            self._preferences.set_approvals_only(conversation_id, False)
            self._preferences.set_subscribed_categories(
                conversation_id,
                set(DEFAULT_NOTIFICATION_CATEGORIES),
            )
            outcome = "Notification preferences reset to the default alert profile."
        elif mode in {"add", "remove", "only"}:
            if len(args) < 2:
                return (
                    f"Usage: /notify {mode} <categories>\n"
                    f"Available: {self._available_notification_categories_text()}"
                )
            categories = self._parse_notification_categories(args[1:])
            if categories is None:
                return (
                    f"Unknown category. Available: {self._available_notification_categories_text()}"
                )
            pref = self._preferences.get(conversation_id)
            current = set(pref.subscribed_categories)
            if mode == "add":
                updated = current | categories
            elif mode == "remove":
                updated = current - categories
            else:
                updated = categories
            pref = self._preferences.set_enabled(conversation_id, True)
            pref = self._preferences.set_approvals_only(conversation_id, False)
            pref = self._preferences.set_subscribed_categories(conversation_id, updated)
            labels = self._format_category_labels(pref.subscribed_categories)
            outcome = f"Subscribed categories saved: {labels}."
        else:
            return (
                "Usage: /notify approvals|all|off|on|reset\n"
                "Usage: /notify add|remove|only <categories>"
            )

        self._record_operator_action(
            action="Notify",
            target_id=conversation_id,
            actor=message.sender_id,
            chat_id=conversation_id,
            thread_id=message.thread_id,
            outcome=outcome,
        )
        return f"{outcome}\n\n{self._format_subscriptions(conversation_id)}"

    def _format_subscriptions(self, conversation_id: str) -> str:
        pref = self._preferences.get(conversation_id)
        effective = self._effective_delivery_settings(conversation_id)
        muted_text = "no"
        if self._alert_state.is_muted(conversation_id):
            muted_until = self._alert_state.get(conversation_id).muted_until
            remaining = max(0, int(muted_until - time.time()))
            muted_text = f"yes ({self._interval_label(remaining)} remaining)"
        categories = self._format_category_labels(pref.subscribed_categories)
        suppressed = len(self._alert_state.list_suppressed(conversation_id, limit=200))
        digest_label = digest_cadence_label(
            effective.digest_cadence,
            effective.digest_interval_seconds,
        )
        return "\n".join(
            [
                "Notification preferences:",
                f"Enabled: {'yes' if pref.enabled else 'no'}",
                f"Mode: {'approvals only' if pref.approvals_only else 'all subscribed'}",
                f"Min severity: {pref.min_severity}",
                f"Categories: {categories}",
                f"Digest: {'on' if effective.digest_enabled else 'off'} ({digest_label})",
                f"Timezone: {effective.timezone}",
                f"Muted: {muted_text}",
                f"Suppressed waiting for digest: {suppressed}",
            ]
        )

    def _handle_severity_command(
        self,
        conversation_id: str,
        value: str | None,
    ) -> str:
        if value is None:
            pref = self._preferences.get(conversation_id)
            return f"Min severity: {pref.min_severity}"
        normalized = value.strip().lower()
        if normalized not in {"info", "warning", "error", "critical"}:
            return "Usage: /severity info|warning|error|critical"
        pref = self._preferences.set_min_severity(conversation_id, normalized)
        return f"Min severity saved: {pref.min_severity}"

    async def _handle_digest_command(
        self,
        inbound: object,
        args: list[str],
    ) -> str:
        from ds_agent.channels.base import InboundMessage

        message: InboundMessage = inbound  # type: ignore[assignment]
        conversation_id = message.conversation_id
        if not args:
            settings = self._effective_delivery_settings(conversation_id)
            state = "on" if settings.digest_enabled else "off"
            pending = len(self._alert_state.list_suppressed(conversation_id, limit=200))
            digest_label = digest_cadence_label(
                settings.digest_cadence,
                settings.digest_interval_seconds,
            )
            return (
                "Digest: "
                f"{state} ({digest_label})\n"
                f"Timezone: {settings.timezone}\n"
                f"Pending suppressed alerts: {pending}"
            )
        normalized = args[0].strip().lower()
        if normalized == "on":
            pref = self._preferences.set_digest_mode(conversation_id, True)
            digest_label = digest_cadence_label(
                pref.digest_cadence,
                pref.digest_interval_seconds,
            )
            outcome = f"Digest enabled ({digest_label}, {pref.timezone})."
            self._record_operator_action(
                action="Digest",
                target_id=conversation_id,
                actor=message.sender_id,
                chat_id=conversation_id,
                thread_id=message.thread_id,
                outcome=outcome,
            )
            return outcome
        if normalized == "off":
            self._preferences.set_digest_mode(conversation_id, False)
            outcome = "Digest disabled."
            self._record_operator_action(
                action="Digest",
                target_id=conversation_id,
                actor=message.sender_id,
                chat_id=conversation_id,
                thread_id=message.thread_id,
                outcome=outcome,
            )
            return outcome
        if normalized == "now":
            outcome = await self._send_digest_for_chat(
                conversation_id,
                thread_id=message.thread_id,
                force=True,
            )
            if outcome and outcome != "No digestible alerts remain.":
                result = "Digest sent above."
            else:
                result = outcome or "No suppressed alerts waiting for digest delivery."
            self._record_operator_action(
                action="Digest",
                target_id=conversation_id,
                actor=message.sender_id,
                chat_id=conversation_id,
                thread_id=message.thread_id,
                outcome=result,
            )
            return result
        if normalized in {"timezone", "tz"}:
            if len(args) < 2:
                return "Usage: /digest timezone <IANA>"
            timezone = args[1].strip()
            if not self._is_valid_timezone(timezone):
                return f"Unknown timezone: {timezone}"
            pref = self._preferences.set_timezone(conversation_id, timezone)
            outcome = f"Digest timezone saved: {pref.timezone}."
            self._record_operator_action(
                action="Digest",
                target_id=conversation_id,
                actor=message.sender_id,
                chat_id=conversation_id,
                thread_id=message.thread_id,
                outcome=outcome,
            )
            return outcome
        if normalized in {"hourly", "morning", "end-of-day", "end_of_day", "eod"}:
            pref = self._preferences.set_digest_mode(
                conversation_id,
                True,
                cadence=normalized,
            )
            digest_label = digest_cadence_label(
                pref.digest_cadence,
                pref.digest_interval_seconds,
            )
            outcome = f"Digest enabled ({digest_label}, {pref.timezone})."
            self._record_operator_action(
                action="Digest",
                target_id=conversation_id,
                actor=message.sender_id,
                chat_id=conversation_id,
                thread_id=message.thread_id,
                outcome=outcome,
            )
            return outcome
        try:
            minutes = int(normalized)
            if minutes < 1:
                return "Digest interval must be >= 1 minute."
            pref = self._preferences.set_digest_mode(
                conversation_id,
                True,
                interval_seconds=minutes * 60.0,
                cadence="interval",
            )
            digest_label = digest_cadence_label(
                pref.digest_cadence,
                pref.digest_interval_seconds,
            )
            outcome = f"Digest enabled ({digest_label}, {pref.timezone})."
            self._record_operator_action(
                action="Digest",
                target_id=conversation_id,
                actor=message.sender_id,
                chat_id=conversation_id,
                thread_id=message.thread_id,
                outcome=outcome,
            )
            return outcome
        except ValueError:
            return "Usage: /digest on|off|<minutes>|hourly|morning|end-of-day|timezone <IANA>|now"

    # ------------------------------------------------------------------
    # Alert lifecycle commands (PLAN_13 Phase 02)
    # ------------------------------------------------------------------

    _DURATION_SUFFIXES: typing.ClassVar[dict[str, float]] = {"m": 60.0, "h": 3600.0, "d": 86400.0}

    def _handle_mute_command(self, inbound: object, duration_arg: str | None) -> str:
        from ds_agent.channels.base import InboundMessage

        message: InboundMessage = inbound  # type: ignore[assignment]
        conversation_id = message.conversation_id
        if duration_arg is None:
            if self._alert_state.is_muted(conversation_id):
                muted_until = self._alert_state.get(conversation_id).muted_until
                remaining = max(0, int(muted_until - time.time()))
                return (
                    f"Already muted ({self._interval_label(remaining)} remaining). "
                    "/unmute to cancel."
                )
            return "Usage: /mute <duration>  (e.g. 30m, 2h, 1d)"

        seconds = self._parse_duration(duration_arg)
        if seconds is None or seconds <= 0:
            return "Usage: /mute <duration>  (e.g. 30m, 2h, 1d)"

        state = self._alert_state.set_muted(conversation_id, seconds)
        remaining = max(0, int(state.muted_until - time.time()))
        outcome = (
            f"Muted for {duration_arg} ({self._interval_label(remaining)}). "
            "Critical alerts still bypass mute."
        )
        self._record_operator_action(
            action="Mute",
            target_id=conversation_id,
            actor=message.sender_id,
            chat_id=conversation_id,
            thread_id=message.thread_id,
            outcome=outcome,
        )
        return outcome

    def _handle_ack_command(self, inbound: object, event_id: str | None) -> str:
        """Acknowledge an alert event for the current chat."""
        from ds_agent.channels.base import InboundMessage

        message: InboundMessage = inbound  # type: ignore[assignment]
        conversation_id = message.conversation_id
        if event_id is None:
            events = self._runtime_event_log.list(limit=20)
            if not events:
                return "No recent alerts to acknowledge."
            event_id = events[0].event_id
        event = self._runtime_event_log.get(event_id)
        if event is None:
            return f"Unknown alert id: {event_id}. Use /alerts to inspect recent alerts."

        self._seen_runtime_event_ids.add(event_id)
        self._alert_state.acknowledge(conversation_id, event_id)
        outcome = f"Acknowledged: {event_id} ({event.kind})."
        self._record_operator_action(
            action="Ack",
            target_id=event_id,
            actor=message.sender_id,
            chat_id=conversation_id,
            thread_id=message.thread_id,
            outcome=outcome,
        )
        return outcome

    @classmethod
    def _parse_duration(cls, text: str) -> float | None:
        """Parse a human duration like ``30m``, ``2h``, ``1d`` into seconds."""
        text = text.strip().lower()
        for suffix, multiplier in cls._DURATION_SUFFIXES.items():
            if text.endswith(suffix):
                try:
                    return float(text[: -len(suffix)]) * multiplier
                except ValueError:
                    return None
        try:
            return float(text) * 60.0  # bare number = minutes
        except ValueError:
            return None

    @staticmethod
    def _parse_notification_categories(args: list[str]) -> set[str] | None:
        if not args:
            return set(DEFAULT_NOTIFICATION_CATEGORIES)
        raw_items: list[str] = []
        for token in args:
            raw_items.extend(part.strip().lower() for part in token.split(","))
        categories: set[str] = set()
        for item in raw_items:
            if not item:
                continue
            normalized = _NOTIFICATION_CATEGORY_ALIASES.get(item)
            if normalized is None:
                return None
            categories.add(normalized)
        return categories

    @staticmethod
    def _format_category_labels(categories: set[str]) -> str:
        if not categories:
            return "none"
        labels = [
            _NOTIFICATION_CATEGORY_LABELS.get(category, category.title()) for category in categories
        ]
        labels.sort()
        return ", ".join(labels)

    @staticmethod
    def _available_notification_categories_text() -> str:
        keys = sorted(
            category for category in _NOTIFICATION_CATEGORY_LABELS if category != "operator_action"
        )
        return ", ".join(keys)

    @staticmethod
    def _severity_index(severity: str) -> int:
        try:
            return _SEVERITY_ORDER.index(severity)
        except ValueError:
            return 0

    @staticmethod
    def _suppression_reason_label(reason: str) -> str:
        return {
            "digest": "digest mode",
            "muted": "temporary mute",
            "acknowledged": "acknowledged",
            "quiet_hours": "quiet hours",
            "rate_limited": "rate limited",
            "policy_disabled": "policy disabled",
            "disabled": "disabled",
        }.get(reason, reason.replace("_", " "))

    # ------------------------------------------------------------------
    # Compact command surface (PLAN_13 Phase 03)
    # ------------------------------------------------------------------

    def _format_ops_menu(self, conversation_id: str, *, thread_id: str | None = None) -> str:
        """Context-aware quick actions menu."""
        session_id = self._session_id(conversation_id, thread_id)
        sections: list[str] = ["Quick actions:"]

        pending = self._approval_store.list(
            session_id=session_id,
            status=ApprovalStatus.PENDING,
            limit=1,
        )
        if pending:
            sections.append(f"Approval pending: /approve {pending[0].approval_id} <response>")

        latest_run = self._runs.latest_for_session(session_id) if hasattr(self, "_runs") else None
        if latest_run is not None and latest_run.status == RuntimeStatus.RUNNING:
            sections.append(f"Running: /stop {latest_run.run_id}")
        elif latest_run is not None:
            sections.append(f"Last run: /run {latest_run.run_id}")

        checkpoint = self._load_checkpoint(session_id)
        if checkpoint is not None:
            sections.append("Checkpoint available: /resume")

        sections.append("")
        sections.append(
            "Read: /status /contract /certification /verdict /runs /approvals /alerts /sessions\n"
            "Control: /stop /resume /approve /reject\n"
            "Policy: /policy /autonomy /profile /goals\n"
            "Notifications: /subscriptions /notify /severity /mute /digest\n"
            "Artifacts: /projects /artifacts"
        )
        return "\n".join(sections)

    # ------------------------------------------------------------------
    # Operator audit (PLAN_13 Phase 04)
    # ------------------------------------------------------------------

    def _record_operator_action(
        self,
        action: str,
        target_id: str,
        actor: str,
        chat_id: str,
        thread_id: str | None,
        outcome: str,
    ) -> None:
        """Log a Telegram operator action to RuntimeEventLog for auditability."""
        self._runtime_event_log.record(
            category="operator_action",
            kind=f"operator.{action.lower()}",
            severity="info",
            message=f"{action} on {target_id}: {self._truncate(outcome, 80)}",
            session_id=self._session_id(chat_id, thread_id),
            surface="telegram",
            source="telegram_runner",
            metadata={
                "actor": actor,
                "chat_id": chat_id,
                "thread_id": thread_id,
                "target_id": target_id,
                "action": action,
            },
        )

    def _format_runtime_alert(self, event: RuntimeEventRecord) -> str:
        header = "Runtime alert"
        if event.category == "recovery":
            header = "Recovery notice"
        if event.kind.startswith("run.outcome."):
            header = "Run outcome"
        elif event.kind == "system.resource.normal" or event.severity == "success":
            header = "Runtime recovered"

        lines = [header, event.message]
        if event.session_id:
            lines.append(f"Session: {self._display_session(event.session_id)}")
        if event.run_id:
            lines.append(f"Run: {event.run_id}")
        policy_reason = str(event.metadata.get("policyReason", "")).strip()
        if policy_reason:
            lines.append(f"Reason: {policy_reason.replace('_', ' ')}")
        if event.kind == "recovery.resume_recommended":
            lines.append("Next: /resume or /session")
        elif event.run_id:
            lines.append(f"Next: /run {event.run_id}")
        else:
            lines.append("Next: /alerts or /status")
        lines.append("Use /alerts 10 to inspect full history.")
        lines.append(f"Alert ID: {event.event_id}")
        return "\n".join(lines)

    def _build_runtime_event_notification(
        self,
        event: RuntimeEventRecord,
        *,
        classified: ClassifiedEvent,
        chat_id: str,
    ) -> Notification:
        title, body = self._split_notification_text(self._format_runtime_alert(event))
        return Notification(
            category=self._notification_category_for_event(event, classified),
            title=title,
            body=body,
            deep_link=self._deep_link_for_event(event),
            inline_keyboard=self._build_alert_buttons(event, chat_id=chat_id),
            workspace_id=self._deep_link_workspace_id(),
            run_id=event.run_id,
        )

    @staticmethod
    def _split_notification_text(text: str) -> tuple[str, str]:
        stripped = text.strip()
        if not stripped:
            return ("Notification", "")
        title, separator, body = stripped.partition("\n")
        if not separator:
            return (title, "")
        return (title, body.lstrip())

    @staticmethod
    def _notification_category_for_event(
        event: RuntimeEventRecord,
        classified: ClassifiedEvent,
    ) -> NotificationCategory:
        if classified.category == "approval" or event.kind == "recovery.awaiting_approval":
            return NotificationCategory.APPROVAL
        if event.kind == "run.outcome.succeeded" or event.kind == "system.resource.normal":
            return NotificationCategory.MILESTONE
        if classified.severity in {"error", "critical"}:
            return NotificationCategory.ERROR
        return NotificationCategory.INFO

    def _format_alert_digest_line(self, conversation_id: str, event: RuntimeEventRecord) -> str:
        status = "new"
        if self._alert_state.is_acknowledged(conversation_id, event.event_id):
            status = "acked"
        else:
            reason = self._alert_state.suppression_reason(conversation_id, event.event_id)
            if reason:
                status = f"suppressed:{self._suppression_reason_label(reason)}"
        target = self._display_session(event.session_id) if event.session_id else event.kind
        return (
            f"- {event.event_id} | {status} | {event.severity} | {event.kind} | "
            f"{self._truncate(target, 28)} | {self._relative_age(event.created_at)}"
        )

    def _resolve_run_for_control(
        self,
        conversation_id: str,
        run_id: str | None,
        *,
        thread_id: str | None = None,
        allow_any_status: bool = False,
    ) -> object | None:
        runs = getattr(self, "_runs", None)
        if runs is None:
            return None
        if run_id:
            return runs.get(run_id)

        statuses = None if allow_any_status else {RuntimeStatus.RUNNING}
        return runs.latest_for_session(
            self._session_id(conversation_id, thread_id),
            statuses=statuses,
        )

    def _load_checkpoint(self, session_id: str) -> SessionCheckpoint | None:
        checkpoint_store = getattr(self, "_checkpoint_store", None)
        if checkpoint_store is None:
            return None
        return checkpoint_store.load(session_id)

    def _load_session_messages(
        self,
        session_id: str,
        *,
        limit: int | None = None,
    ) -> list[ChatMessage]:
        checkpoint = self._load_checkpoint(session_id)
        if checkpoint is not None and checkpoint.messages:
            messages = list(checkpoint.messages)
        else:
            transcript_store = getattr(self, "_transcript_store", None)
            if transcript_store is None:
                return []
            messages = transcript_store.load_messages(session_id, limit=limit)
        if limit is None:
            return messages
        return messages[-limit:]

    def _runtime_session_registry(self) -> RuntimeSessionRegistry | None:
        registry = getattr(self, "_runtime_sessions", None)
        return registry if isinstance(registry, RuntimeSessionRegistry) else None

    def _runtime_active_count(self) -> int:
        registry = self._runtime_session_registry()
        runtime_count = registry.active_count if registry is not None else 0
        sessions = getattr(self, "_sessions", None)
        if sessions is None:
            return runtime_count
        return max(runtime_count, int(sessions.active_count()))

    def _remember_delivery_target(self, inbound: object) -> None:
        from ds_agent.channels.base import InboundMessage

        message: InboundMessage = inbound  # type: ignore[assignment]
        self._delivery_targets[message.conversation_id] = TelegramDeliveryTarget(
            conversation_id=message.conversation_id,
            thread_id=message.thread_id,
        )

    def _delivery_target_for_conversation(self, conversation_id: str) -> TelegramDeliveryTarget:
        return self._delivery_targets.get(
            conversation_id,
            TelegramDeliveryTarget(conversation_id=conversation_id),
        )

    def _delivery_target_for_event(
        self,
        conversation_id: str,
        event: RuntimeEventRecord,
    ) -> TelegramDeliveryTarget:
        session_id = event.session_id
        if session_id and session_id.startswith("telegram:"):
            target_chat_id, target_thread_id = parse_telegram_session_id(session_id)
            if target_chat_id == conversation_id and target_thread_id is not None:
                return TelegramDeliveryTarget(
                    conversation_id=conversation_id,
                    thread_id=target_thread_id,
                )
        return self._delivery_target_for_conversation(conversation_id)

    async def _send_text(
        self,
        text: str,
        conversation_id: str,
        *,
        thread_id: str | None = None,
        reply_to_id: str | None = None,
        reply_markup: object | None = None,
    ) -> object:
        target = self._delivery_target_for_conversation(conversation_id)
        return await self._plugin.send_text(
            OutboundMessage(
                text=text,
                conversation_id=conversation_id,
                thread_id=thread_id if thread_id is not None else target.thread_id,
                reply_to_id=reply_to_id,
                parse_mode="",
                reply_markup=reply_markup,
            )
        )

    async def _send_chunks(
        self,
        text: str,
        conversation_id: str,
        *,
        thread_id: str | None = None,
    ) -> None:
        target = self._delivery_target_for_conversation(conversation_id)
        resolved_thread = thread_id if thread_id is not None else target.thread_id
        for chunk in self._plugin.chunk_text(text):
            await self._plugin.send_text(
                OutboundMessage(
                    text=chunk,
                    conversation_id=conversation_id,
                    thread_id=resolved_thread,
                    parse_mode="",
                )
            )

    async def dispatch_notification(
        self,
        notification: object,
        conversation_id: str,
        *,
        thread_id: str | None = None,
    ) -> BuiltMessage:
        """Render *notification* via the PLAN_04 message builder and send it.

        Domain :class:`Notification` flows through the boundary (truncation,
        PII masking, deep-link insertion) before reaching Telegram.  Returns
        the :class:`BuiltMessage` for callers that want to inspect the
        truncation / masking outcome.

        Quiet-hours suppression is enforced via
        :class:`SendNotificationUseCase`; suppressed notifications are
        persisted by :class:`JsonDeferredNotificationStore` so they survive
        process restarts.
        """
        from datetime import UTC, datetime

        from ds_agent.domain.notification import Notification as _Notification

        if not isinstance(notification, _Notification):
            raise TypeError("notification must be a domain Notification")

        builder = getattr(self, "_message_builder", None)
        if not isinstance(builder, TelegramMessageBuilder):
            builder = TelegramMessageBuilder()
            self._message_builder = builder

        built = builder.build(notification)

        send_uc = getattr(self, "_send_notification_use_case", None)
        # DIGEST itself is the quiet-hours release mechanism, so we don't
        # re-suppress it.  All other categories flow through the use case
        # so quiet-hours-suppressed alerts get persisted to disk and
        # survive process restarts.
        if (
            isinstance(send_uc, SendNotificationUseCase)
            and notification.category is not NotificationCategory.DIGEST
        ):
            decision = send_uc.execute(
                operator_id=conversation_id,
                notification=notification,
                now=datetime.now(tz=UTC),
            )
            if decision.deferred:
                logger.info(
                    "telegram_notification_deferred_persisted",
                    conversation_id=conversation_id,
                    category=notification.category.value,
                    reason=decision.reason,
                )
                return built

        await self._send_text(
            built.text,
            conversation_id,
            thread_id=thread_id,
            reply_markup=built.reply_markup,
        )
        return built

    def _persist_runtime_config(self) -> None:
        config_path = getattr(self, "_config_path", None)
        path = config_path if isinstance(config_path, Path) else get_default_config_path()
        save_config(self._config, path)

    def _autonomous_runtime_enabled(self) -> bool:
        gateway = getattr(self._config, "gateway", None)
        enabled = getattr(gateway, "autonomous_runtime_enabled", False)
        return enabled if isinstance(enabled, bool) else False

    def _automation_profile(self) -> str:
        gateway = getattr(self._config, "gateway", None)
        profile = getattr(gateway, "automation_profile", "")
        if isinstance(profile, str) and profile in _AUTOMATION_PROFILES:
            return profile
        return "unknown"

    @staticmethod
    def _session_id(conversation_id: str, thread_id: str | None = None) -> str:
        return telegram_session_id(conversation_id, thread_id)

    @staticmethod
    def _display_session(session_id: str) -> str:
        if session_id.startswith("telegram:"):
            conv_id, thread_id = parse_telegram_session_id(session_id)
            if thread_id is not None:
                return f"chat {conv_id} / topic {thread_id}"
            return f"chat {conv_id}"
        return session_id

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        stripped = text.strip()
        if len(stripped) <= limit:
            return stripped
        return stripped[: limit - 3].rstrip() + "..."

    @staticmethod
    def _interval_label(interval_seconds: float) -> str:
        interval = max(1, int(interval_seconds))
        if interval < 60:
            return f"{interval}s"
        if interval % 3600 == 0:
            return f"{interval // 3600}h"
        if interval % 60 == 0:
            return f"{interval // 60}m"
        if interval < 3600:
            minutes, seconds = divmod(interval, 60)
            return f"{minutes}m {seconds}s"
        hours, remainder = divmod(interval, 3600)
        minutes = remainder // 60
        return f"{hours}h" if minutes == 0 else f"{hours}h {minutes}m"

    @staticmethod
    def _relative_age(timestamp: float) -> str:
        delta_seconds = max(0, int(time.time() - timestamp))
        if delta_seconds < 60:
            return f"{delta_seconds}s ago"
        if delta_seconds < 3600:
            return f"{delta_seconds // 60}m ago"
        return f"{delta_seconds // 3600}h ago"

    def _create_agent(self, chat_id: str, thread_id: str | None = None) -> DSAgent:
        """Create a new DSAgent for a Telegram conversation."""
        from ds_agent.runtime.authority_overlay import resolve_authority_overlay
        from ds_agent.runtime.provider_factory import create_provider_router

        callbacks = TelegramCallbacks(
            self._plugin,
            chat_id,
            thread_id=thread_id,
            approval_store=self._approval_store,
            action_tokens=self._action_tokens,
            workspace_dir=str(self._config.agent.workspace_dir),
        )
        model_str = self._config.provider.default_model
        provider = create_provider_router(
            model_str,
            self._config,
            token_store=self._token_store,
        )
        overlay = resolve_authority_overlay(
            getattr(self._config.gateway, "authority_overlay", None),
            getattr(self._config.gateway, "authority_overlay_started_at", None),
        )

        return create_agent(
            provider=provider,
            callbacks=callbacks,
            max_iterations=self._config.agent.max_iterations,
            max_cost_usd=self._config.provider.max_budget_usd,
            mode=self._config.agent.mode,
            authority_mode=None if overlay.mode is None else overlay.mode.value,
            model_name=model_str,
            workspace_dir=str(self._config.agent.workspace_dir),
            session_id=telegram_session_id(chat_id, thread_id),
            transcript_store=self._transcript_store,
            checkpoint_store=self._checkpoint_store,
            approval_store=self._approval_store,
            sandbox_config=self._config.sandbox,
        )

    def _task_contract_container(self) -> TaskContractContainer:
        return build_task_contract_container(str(self._config.agent.workspace_dir))

    def _verifier_container(self) -> VerifierContainer:
        return build_verifier_container(str(self._config.agent.workspace_dir))

    def _list_project_files(self, project_id: str) -> list[dict]:
        files = self._workspace.list_files(project_id)
        return [item for item in files if item.get("path") != "meta.json"]

    @staticmethod
    def _import_tools() -> None:
        import importlib

        for module_name in [
            "ds_agent.tools.code_execution",
            "ds_agent.tools.data_loader",
            "ds_agent.tools.data_profiler",
            "ds_agent.tools.deployment",
            "ds_agent.tools.eda",
            "ds_agent.tools.evaluation",
            "ds_agent.tools.feature_eng",
            "ds_agent.tools.file_ops",
            "ds_agent.tools.memory_tools",
            "ds_agent.tools.modeling",
            "ds_agent.tools.reporting",
            "ds_agent.tools.schema_tools",
            "ds_agent.tools.skill_tools",
            "ds_agent.tools.sql_tools",
            "ds_agent.tools.user_interaction",
            "ds_agent.tools.web_search",
        ]:
            importlib.import_module(module_name)
