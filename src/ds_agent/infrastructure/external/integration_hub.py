"""Shared dispatch hub for workflow integration connectors."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from ds_agent.application.ports.work_object_support import (
    PolicyActionSpec,
    PolicyCheckResult,
    WorkflowIntegrationPolicyPort,
)
from ds_agent.domain.entities.approval_policy import DataSensitivity, PolicyDecisionType
from ds_agent.domain.entities.external_reference import (
    build_integration_idempotency_key,
    build_request_payload_hash,
)
from ds_agent.domain.entities.integration_event import IntegrationEvent, IntegrationEventStatus
from ds_agent.domain.entities.work_object import WorkObject
from ds_agent.domain.errors.work_object_errors import WorkObjectNotFoundError
from ds_agent.domain.interfaces.work_object import WorkObjectStore
from ds_agent.infrastructure.external.calendar_connector import (
    CalendarConnector,
    CalendarEventRequest,
)
from ds_agent.infrastructure.external.confluence_connector import (
    ConfluenceConnector,
    ConfluencePageRequest,
)
from ds_agent.infrastructure.external.connector_models import ConnectorHealthResult, ConnectorResult
from ds_agent.infrastructure.external.email_connector import (
    EmailConnector,
    EmailRequest,
)
from ds_agent.infrastructure.external.git_connector import GitConnector, GitPRRequest
from ds_agent.infrastructure.external.jira_connector import JiraConnector, JiraIssueRequest
from ds_agent.infrastructure.external.notion_connector import NotionConnector, NotionPageRequest
from ds_agent.infrastructure.external.slack_connector import SlackConnector, SlackMessageRequest


class Clock(Protocol):
    def now(self) -> datetime: ...


class IntegrationHub:
    """Minimal idempotent dispatch layer for workflow integration connectors."""

    def __init__(
        self,
        *,
        store: WorkObjectStore,
        clock: Clock,
        slack: SlackConnector | None = None,
        jira: JiraConnector | None = None,
        confluence: ConfluenceConnector | None = None,
        notion: NotionConnector | None = None,
        git: GitConnector | None = None,
        email: EmailConnector | None = None,
        calendar: CalendarConnector | None = None,
        policy: WorkflowIntegrationPolicyPort | None = None,
        rate_limiter: Any = None,
    ) -> None:
        self._store = store
        self._clock = clock
        self._slack = slack or SlackConnector()
        self._jira = jira or JiraConnector()
        self._confluence = confluence or ConfluenceConnector()
        self._notion = notion or NotionConnector()
        self._git = git or GitConnector()
        self._email = email or EmailConnector()
        self._calendar = calendar or CalendarConnector()
        self._policy = policy
        if rate_limiter is None:
            from ds_agent.infrastructure.external.rate_limiter import (
                TokenBucketRateLimiter,
            )
            rate_limiter = TokenBucketRateLimiter()
        self._rate_limiter = rate_limiter

    def health_check_all(self) -> list[ConnectorHealthResult]:
        """Run health checks across all registered connectors."""
        results: list[ConnectorHealthResult] = []
        connectors = [
            self._slack, self._jira, self._confluence,
            self._notion, self._git, self._email, self._calendar,
        ]
        for connector in connectors:
            try:
                results.append(connector.health_check())  # type: ignore[union-attr,attr-defined]
            except Exception as exc:
                results.append(ConnectorHealthResult(
                    system=getattr(connector, "system_name", "unknown"),
                    healthy=False,
                    message=f"Health check failed: {exc}",
                ))
        return results

    def replay_event(self, event_id: str) -> dict[str, Any]:
        """Replay a failed or DLQ event using its stored payload."""
        import json as _json

        event = self._store.get_event(event_id)
        if event is None:
            raise ValueError(f"Event not found: {event_id}")
        if event.status not in {
            IntegrationEventStatus.FAILED,
            IntegrationEventStatus.DLQ,
        }:
            raise ValueError(
                f"Cannot replay event in status {event.status.value}. "
                "Only FAILED or DLQ events can be replayed.",
            )
        if not event.request_payload_json:
            raise ValueError(
                f"Event {event_id} has no stored payload. "
                "Cannot replay events recorded before payload storage.",
            )
        payload = _json.loads(event.request_payload_json)
        connector_map: dict[str, Any] = {
            "slack": self._slack,
            "jira": self._jira,
            "confluence": self._confluence,
            "notion": self._notion,
            "github": self._git,
            "gitlab": self._git,
            "git": self._git,
            "email": self._email,
            "calendar": self._calendar,
        }
        connector = connector_map.get(event.system)
        if connector is None:
            raise ValueError(f"No connector for system: {event.system}")

        new_attempt = event.attempt + 1
        started_at = self._clock.now()
        try:
            result = _replay_dispatch(
                connector, event.system, payload, event.idempotency_key,
            )
        except Exception as exc:
            finished_at = self._clock.now()
            result = ConnectorResult(
                success=False,
                error_code=type(exc).__name__.upper(),
                error_message=str(exc),
                retriable=True,
            )
        else:
            finished_at = self._clock.now()

        new_event = self._build_event(
            work_object_id=event.work_object_id,
            system=event.system,
            action=event.action,
            payload=payload,
            idempotency_key=event.idempotency_key,
            result=result,
            started_at=started_at,
            finished_at=finished_at,
            attempt=new_attempt,
        )
        self._store.record_event(new_event)

        if not result.success and new_attempt >= 3:
            self._store.update_event_status(
                event_id,
                IntegrationEventStatus.DLQ,
                error_code="MAX_RETRIES_EXCEEDED",
                error_message=(
                    f"Moved to DLQ after {new_attempt} attempts. "
                    f"Last error: {result.error_message}"
                ),
            )

        return {
            "replay_event_id": new_event.event_id,
            "original_event_id": event_id,
            "status": new_event.status.value,
            "attempt": new_attempt,
            "success": result.success,
            "error_code": result.error_code,
            "error_message": result.error_message,
        }

    def post_to_slack(
        self,
        *,
        work_object_id: str,
        request: SlackMessageRequest,
        location: Literal["request", "documentation", "follow_up"] = "documentation",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        payload = request.model_dump(mode="json")
        idempotency_key = build_integration_idempotency_key(
            work_object_id=work_object_id,
            system="slack",
            action="post_message",
            discriminator=build_request_payload_hash(payload)[:16],
        )
        return self._dispatch(
            work_object_id=work_object_id,
            system="slack",
            action="post_message",
            payload=payload,
            location=location,
            dry_run=dry_run,
            dispatch=lambda: self._slack.dispatch(
                request,
                idempotency_key=idempotency_key,
                dry_run=dry_run,
            ),
            idempotency_key=idempotency_key,
            action_type="message",
            description=request.text_fallback[:120],
        )

    def create_jira_ticket(
        self,
        *,
        work_object_id: str,
        request: JiraIssueRequest,
        location: Literal["request", "documentation", "follow_up"] = "follow_up",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        payload = request.model_dump(mode="json")
        idempotency_key = build_integration_idempotency_key(
            work_object_id=work_object_id,
            system="jira",
            action="create_issue",
            discriminator=build_request_payload_hash(payload)[:16],
        )
        return self._dispatch(
            work_object_id=work_object_id,
            system="jira",
            action="create_issue",
            payload=payload,
            location=location,
            dry_run=dry_run,
            dispatch=lambda: self._jira.dispatch(
                request,
                idempotency_key=idempotency_key,
                dry_run=dry_run,
            ),
            idempotency_key=idempotency_key,
            action_type="ticket",
            description=request.summary,
        )

    def publish_confluence_page(
        self,
        *,
        work_object_id: str,
        request: ConfluencePageRequest,
        location: Literal["request", "documentation", "follow_up"] = "documentation",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        payload = request.model_dump(mode="json")
        idempotency_key = build_integration_idempotency_key(
            work_object_id=work_object_id,
            system="confluence",
            action="publish_page",
            discriminator=build_request_payload_hash(payload)[:16],
        )
        return self._dispatch(
            work_object_id=work_object_id,
            system="confluence",
            action="publish_page",
            payload=payload,
            location=location,
            dry_run=dry_run,
            dispatch=lambda: self._confluence.dispatch(
                request,
                idempotency_key=idempotency_key,
                dry_run=dry_run,
            ),
            idempotency_key=idempotency_key,
            action_type="message",
            description=request.title,
        )

    def publish_notion_page(
        self,
        *,
        work_object_id: str,
        request: NotionPageRequest,
        location: Literal["request", "documentation", "follow_up"] = "documentation",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        payload = request.model_dump(mode="json")
        idempotency_key = build_integration_idempotency_key(
            work_object_id=work_object_id,
            system="notion",
            action="publish_page",
            discriminator=build_request_payload_hash(payload)[:16],
        )
        return self._dispatch(
            work_object_id=work_object_id,
            system="notion",
            action="publish_page",
            payload=payload,
            location=location,
            dry_run=dry_run,
            dispatch=lambda: self._notion.dispatch(
                request,
                idempotency_key=idempotency_key,
                dry_run=dry_run,
            ),
            idempotency_key=idempotency_key,
            action_type="message",
            description=request.title,
        )

    def open_git_pr(
        self,
        *,
        work_object_id: str,
        request: GitPRRequest,
        location: Literal["request", "documentation", "follow_up"] = "documentation",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        payload = request.model_dump(mode="json")
        idempotency_key = build_integration_idempotency_key(
            work_object_id=work_object_id,
            system=request.provider,
            action="open_pull_request",
            discriminator=build_request_payload_hash(payload)[:16],
        )
        return self._dispatch(
            work_object_id=work_object_id,
            system=request.provider,
            action="open_pull_request",
            payload=payload,
            location=location,
            dry_run=dry_run,
            dispatch=lambda: self._git.dispatch(
                request,
                idempotency_key=idempotency_key,
                dry_run=dry_run,
            ),
            idempotency_key=idempotency_key,
            action_type="message",
            description=request.pr_title,
        )

    def send_email(
        self,
        *,
        work_object_id: str,
        request: EmailRequest,
        location: Literal["request", "documentation", "follow_up"] = "follow_up",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        payload = request.model_dump(mode="json")
        idempotency_key = build_integration_idempotency_key(
            work_object_id=work_object_id,
            system="email",
            action="send_message",
            discriminator=build_request_payload_hash(payload)[:16],
        )
        return self._dispatch(
            work_object_id=work_object_id,
            system="email",
            action="send_message",
            payload=payload,
            location=location,
            dry_run=dry_run,
            dispatch=lambda: self._email.dispatch(
                request,
                idempotency_key=idempotency_key,
                dry_run=dry_run,
            ),
            idempotency_key=idempotency_key,
            action_type="message",
            description=f"Email to {', '.join(request.to[:2])}: {request.subject[:80]}",
        )

    def create_calendar_event(
        self,
        *,
        work_object_id: str,
        request: CalendarEventRequest,
        location: Literal["request", "documentation", "follow_up"] = "follow_up",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        payload = request.model_dump(mode="json")
        idempotency_key = build_integration_idempotency_key(
            work_object_id=work_object_id,
            system="calendar",
            action="create_event",
            discriminator=build_request_payload_hash(payload)[:16],
        )
        return self._dispatch(
            work_object_id=work_object_id,
            system="calendar",
            action="create_event",
            payload=payload,
            location=location,
            dry_run=dry_run,
            dispatch=lambda: self._calendar.dispatch(
                request,
                idempotency_key=idempotency_key,
                dry_run=dry_run,
            ),
            idempotency_key=idempotency_key,
            action_type="calendar",
            description=f"Calendar: {request.summary[:80]}",
        )

    def _dispatch(
        self,
        *,
        work_object_id: str,
        system: str,
        action: str,
        payload: dict[str, Any],
        location: Literal["request", "documentation", "follow_up"],
        dry_run: bool,
        dispatch: Callable[[], ConnectorResult],
        idempotency_key: str,
        action_type: Literal["ticket", "calendar", "message", "dashboard_update"],
        description: str,
    ) -> dict[str, Any]:
        work_object = self._store.get(work_object_id)
        if work_object is None:
            raise WorkObjectNotFoundError(f"Work object not found: {work_object_id}")
        existing = self._store.find_event_by_idempotency_key(idempotency_key)
        if existing is not None and existing.external_ref is not None:
            return {
                "work_object_id": work_object_id,
                "duplicate": True,
                "status": existing.status.value,
                "external_ref": existing.external_ref.model_dump(mode="json"),
                "event_id": existing.event_id,
            }
        policy_result = self._check_policy(
            work_object=work_object,
            system=system,
            action=action,
            payload=payload,
        )
        if policy_result is not None and policy_result.decision != PolicyDecisionType.AUTO:
            return self._record_policy_block(
                work_object=work_object,
                system=system,
                action=action,
                payload=payload,
                location=location,
                idempotency_key=idempotency_key,
                action_type=action_type,
                description=description,
                policy_result=policy_result,
                dry_run=dry_run,
            )
        if not self._rate_limiter.acquire(system):
            now = self._clock.now()
            event = self._build_event(
                work_object_id=work_object_id,
                system=system,
                action=action,
                payload=payload,
                idempotency_key=idempotency_key,
                result=ConnectorResult(
                    success=False,
                    error_code="RATE_LIMITED",
                    error_message=f"Rate limit exceeded for {system}.",
                    retriable=True,
                ),
                started_at=now,
                finished_at=now,
            )
            self._store.record_event(event)
            return {
                "work_object_id": work_object_id,
                "duplicate": False,
                "dry_run": dry_run,
                "status": event.status.value,
                "event_id": event.event_id,
                "external_ref": None,
                "error_code": "RATE_LIMITED",
                "error_message": f"Rate limit exceeded for {system}.",
            }
        started_at = self._clock.now()
        result = dispatch()
        finished_at = self._clock.now()
        event = self._build_event(
            work_object_id=work_object_id,
            system=system,
            action=action,
            payload=payload,
            idempotency_key=idempotency_key,
            result=result,
            started_at=started_at,
            finished_at=finished_at,
        )
        self._store.record_event(event)
        if result.success and result.external_ref is not None:
            work_object.attach_reference(
                result.external_ref,
                location=location,
                when=finished_at,
                action_type=action_type,
                description=description,
            )
            self._store.save(work_object)
        return {
            "work_object_id": work_object_id,
            "duplicate": False,
            "dry_run": dry_run,
            "status": event.status.value,
            "external_ref": (
                None if result.external_ref is None else result.external_ref.model_dump(mode="json")
            ),
            "event_id": event.event_id,
            "error_code": result.error_code,
            "error_message": result.error_message,
        }

    def _check_policy(
        self,
        *,
        work_object: WorkObject,
        system: str,
        action: str,
        payload: dict[str, Any],
    ) -> PolicyCheckResult | None:
        if self._policy is None:
            return None
        sensitivity_raw = (
            payload.get("data_sensitivity")
            or payload.get("metadata", {}).get("data_sensitivity")
            or work_object.request.metadata.get("data_sensitivity")
            or "internal"
        )
        environment = str(
            payload.get("environment")
            or payload.get("metadata", {}).get("environment")
            or work_object.request.metadata.get("environment")
            or "dev"
        )
        confidence = float(
            payload.get("confidence")
            or payload.get("metadata", {}).get("confidence")
            or 1.0
        )
        try:
            sensitivity = DataSensitivity(str(sensitivity_raw))
        except ValueError:
            sensitivity = DataSensitivity.INTERNAL
        tool_action = {
            "slack": "post_to_slack",
            "jira": "create_jira_ticket",
            "confluence": "publish_confluence_page",
            "notion": "publish_notion_page",
            "github": "open_git_pr",
            "gitlab": "open_git_pr",
        }.get(system, action)
        return self._policy.check(
            PolicyActionSpec(
                action=tool_action,
                data_sensitivity=sensitivity,
                environment=environment,
                confidence=confidence,
                metadata={
                    "system": system,
                    "hub_action": action,
                    "work_object_id": work_object.work_object_id,
                },
            )
        )

    def _record_policy_block(
        self,
        *,
        work_object: WorkObject,
        system: str,
        action: str,
        payload: dict[str, Any],
        location: Literal["request", "documentation", "follow_up"],
        idempotency_key: str,
        action_type: Literal["ticket", "calendar", "message", "dashboard_update"],
        description: str,
        policy_result: PolicyCheckResult,
        dry_run: bool,
    ) -> dict[str, Any]:
        now = self._clock.now()
        blocked_status = (
            IntegrationEventStatus.FAILED
            if policy_result.decision == PolicyDecisionType.DENY
            else IntegrationEventStatus.PENDING
        )
        error_code = (
            "POLICY_DENIED"
            if policy_result.decision == PolicyDecisionType.DENY
            else "POLICY_APPROVAL_REQUIRED"
        )
        event = IntegrationEvent(
            event_id=f"IE-{int(datetime.now(UTC).timestamp() * 1000000)}",
            work_object_id=work_object.work_object_id,
            system=system,
            action=action,
            request_payload_hash=build_request_payload_hash(payload),
            idempotency_key=idempotency_key,
            status=blocked_status,
            external_ref=None,
            attempt=1,
            latency_ms=0,
            started_at=now,
            finished_at=now,
            error_code=error_code,
            error_message=policy_result.reason,
            policy_decision_id=policy_result.decision_id,
        )
        self._store.record_event(event)
        work_object.queue_pending_policy_action(
            system=system,
            action=action_type,
            location=location,
            description=description,
            idempotency_key=idempotency_key,
            policy_decision_id=policy_result.decision_id,
            reason=policy_result.reason,
            when=now,
        )
        self._store.save(work_object)
        return {
            "work_object_id": work_object.work_object_id,
            "duplicate": False,
            "dry_run": dry_run,
            "status": event.status.value,
            "external_ref": None,
            "event_id": event.event_id,
            "error_code": error_code,
            "error_message": policy_result.reason,
            "policy_decision_id": policy_result.decision_id,
        }

    @staticmethod
    def _build_event(
        *,
        work_object_id: str,
        system: str,
        action: str,
        payload: dict[str, Any],
        idempotency_key: str,
        result: ConnectorResult,
        started_at: datetime,
        finished_at: datetime,
        attempt: int = 1,
    ) -> IntegrationEvent:
        import json as _json

        status = (
            IntegrationEventStatus.SUCCESS
            if result.success
            else IntegrationEventStatus.FAILED
        )
        latency_ms = max(
            int((finished_at - started_at).total_seconds() * 1000), 0,
        )
        return IntegrationEvent(
            event_id=f"IE-{int(datetime.now(UTC).timestamp() * 1000000)}",
            work_object_id=work_object_id,
            system=system,
            action=action,
            request_payload_hash=build_request_payload_hash(payload),
            idempotency_key=idempotency_key,
            status=status,
            external_ref=result.external_ref,
            attempt=attempt,
            latency_ms=latency_ms,
            started_at=started_at,
            finished_at=finished_at,
            error_code=result.error_code,
            error_message=result.error_message,
            request_payload_json=_json.dumps(
                payload, default=str, ensure_ascii=False,
            ),
        )


_REPLAY_REQUEST_TYPES: dict[str, type] = {
    "slack": SlackMessageRequest,
    "jira": JiraIssueRequest,
    "confluence": ConfluencePageRequest,
    "notion": NotionPageRequest,
    "github": GitPRRequest,
    "gitlab": GitPRRequest,
    "git": GitPRRequest,
    "email": EmailRequest,
    "calendar": CalendarEventRequest,
}


def _replay_dispatch(
    connector: Any,
    system: str,
    payload: dict[str, Any],
    idempotency_key: str,
) -> ConnectorResult:
    """Replay: reconstruct the request model from stored payload."""
    request_cls = _REPLAY_REQUEST_TYPES.get(system)
    if request_cls is None:
        raise ValueError(f"No request model for system: {system}")
    request = request_cls.model_validate(payload)  # type: ignore[attr-defined]
    result: ConnectorResult = connector.dispatch(
        request,
        idempotency_key=idempotency_key,
        dry_run=False,
    )
    return result
