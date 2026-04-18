"""Organization integration tools for external workflow systems."""

from __future__ import annotations

import json
import os
import re
from typing import Literal

from ds_agent.application.dtos.work_object import (
    AdvanceWorkObjectPhaseDTO,
    CloseWorkObjectDTO,
    CreateWorkObjectDTO,
    LinkExternalReferenceDTO,
    ListWorkObjectsDTO,
)
from ds_agent.domain.entities.work_object import WorkObjectPhase
from ds_agent.domain.errors.work_object_errors import WorkObjectError
from ds_agent.infrastructure.external.confluence_connector import ConfluencePageRequest
from ds_agent.infrastructure.external.git_client import GitClient
from ds_agent.infrastructure.external.git_connector import GitFileChange, GitPRRequest
from ds_agent.infrastructure.external.jira_client import JiraClient
from ds_agent.infrastructure.external.jira_connector import JiraIssueRequest
from ds_agent.infrastructure.external.notion_connector import NotionPageRequest
from ds_agent.infrastructure.external.slack_client import SlackClient
from ds_agent.infrastructure.external.slack_connector import SlackMessageRequest
from ds_agent.infrastructure.work_object_container import (
    WorkObjectContainer,
    build_work_object_container,
)
from ds_agent.tools.registry import tool

_work_object_container: WorkObjectContainer | None = None


def set_work_object_container(container: WorkObjectContainer) -> None:
    """Wire a work-object container into the tool module."""

    global _work_object_container
    _work_object_container = container


def _get_work_object_container() -> WorkObjectContainer:
    global _work_object_container
    if _work_object_container is not None:
        return _work_object_container
    from ds_agent.tools.path_utils import get_active_workspace

    workspace = get_active_workspace()
    _work_object_container = build_work_object_container(
        str(workspace) if workspace is not None else None
    )
    return _work_object_container


def _ok_response(**payload: object) -> str:
    return json.dumps({"ok": True, **payload}, ensure_ascii=False)


def _error_response(code: str, message: str, **payload: object) -> str:
    return json.dumps(
        {"ok": False, "error": {"code": code, "message": message}, **payload},
        ensure_ascii=False,
    )


def _handle_error(exc: Exception) -> str:
    if isinstance(exc, WorkObjectError):
        return _error_response(exc.error_code, str(exc))
    if isinstance(exc, ValueError):
        return _error_response("VALIDATION_ERROR", str(exc))
    return _error_response(type(exc).__name__.upper(), str(exc))


def _dedupe_strings(values: list[str]) -> list[str]:
    return [value for value in dict.fromkeys(values) if value]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "artifact"


def _default_git_head_branch(work_object_id: str, title: str) -> str:
    normalized_id = work_object_id.lower().replace("_", "-")
    return f"ds-agent/{normalized_id}-{_slugify(title)}"


@tool(
    name="create_work_object",
    description="Create a WorkObject that tracks request, execution, documentation, and follow-up for one task contract.",
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "task_contract_id": {"type": "string"},
            "title": {"type": "string"},
            "request_source": {
                "type": "string",
                "enum": ["slack", "email", "jira", "cli", "telegram", "electron", "api"],
            },
            "requestor_id": {"type": "string"},
            "requestor_display": {"type": "string"},
            "original_text": {"type": "string"},
            "channel": {"type": "string"},
            "request_metadata": {"type": "object"},
            "external_reference": {"type": "object"},
            "delivery_pack_id": {"type": "string"},
            "owner_agent": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "parent_work_object_id": {"type": "string"},
        },
        "required": [
            "task_contract_id",
            "title",
            "request_source",
            "requestor_id",
            "requestor_display",
            "original_text",
        ],
    },
)
def create_work_object(
    task_contract_id: str,
    title: str,
    request_source: Literal["slack", "email", "jira", "cli", "telegram", "electron", "api"],
    requestor_id: str,
    requestor_display: str,
    original_text: str,
    channel: str | None = None,
    request_metadata: dict | None = None,
    external_reference: dict | None = None,
    delivery_pack_id: str | None = None,
    owner_agent: str = "ds-agent",
    tags: list[str] | None = None,
    parent_work_object_id: str | None = None,
) -> str:
    try:
        dto = CreateWorkObjectDTO.model_validate(
            {
                "task_contract_id": task_contract_id,
                "title": title,
                "request_source": request_source,
                "requestor_id": requestor_id,
                "requestor_display": requestor_display,
                "original_text": original_text,
                "channel": channel,
                "request_metadata": request_metadata or {},
                "external_reference": external_reference,
                "delivery_pack_id": delivery_pack_id,
                "owner_agent": owner_agent,
                "tags": tags or [],
                "parent_work_object_id": parent_work_object_id,
            }
        )
        result = _get_work_object_container().create.execute(dto)
        return _ok_response(**result.model_dump(mode="json"))
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="get_work_object",
    description="Fetch one WorkObject with its persisted integration timeline.",
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "work_object_id": {"type": "string"},
            "timeline_limit": {"type": "integer", "default": 50},
        },
        "required": ["work_object_id"],
    },
)
def get_work_object(work_object_id: str, timeline_limit: int = 50) -> str:
    try:
        result = _get_work_object_container().get.execute(
            work_object_id,
            timeline_limit=timeline_limit,
        )
        return _ok_response(**result.model_dump(mode="json"))
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="list_work_objects",
    description="List persisted WorkObjects by session, task contract, or phase.",
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "task_contract_id": {"type": "string"},
            "phase_filter": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [phase.value for phase in WorkObjectPhase],
                },
            },
            "limit": {"type": "integer", "default": 20},
        },
    },
)
def list_work_objects(
    session_id: str | None = None,
    task_contract_id: str | None = None,
    phase_filter: list[str] | None = None,
    limit: int = 20,
) -> str:
    try:
        dto = ListWorkObjectsDTO.model_validate(
            {
                "session_id": session_id,
                "task_contract_id": task_contract_id,
                "phase_filter": phase_filter or [],
                "limit": limit,
            }
        )
        items = _get_work_object_container().list_work_objects.execute(dto)
        return _ok_response(work_objects=[item.model_dump(mode="json") for item in items])
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="link_external_resource",
    description="Attach a typed external reference to a WorkObject request, documentation, or follow-up section.",
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "work_object_id": {"type": "string"},
            "system": {"type": "string"},
            "resource_type": {"type": "string"},
            "resource_id": {"type": "string"},
            "url": {"type": "string"},
            "metadata": {"type": "object"},
            "idempotency_key": {"type": "string"},
            "location": {
                "type": "string",
                "enum": ["request", "documentation", "follow_up"],
            },
            "action_type": {
                "type": "string",
                "enum": ["ticket", "calendar", "message", "dashboard_update"],
            },
            "description": {"type": "string"},
            "policy_decision_id": {"type": "string"},
        },
        "required": ["work_object_id", "system", "resource_type", "resource_id"],
    },
)
def link_external_resource(
    work_object_id: str,
    system: str,
    resource_type: str,
    resource_id: str,
    url: str | None = None,
    metadata: dict | None = None,
    idempotency_key: str | None = None,
    location: Literal["request", "documentation", "follow_up"] = "documentation",
    action_type: Literal["ticket", "calendar", "message", "dashboard_update"] = "message",
    description: str | None = None,
    policy_decision_id: str | None = None,
) -> str:
    try:
        dto = LinkExternalReferenceDTO.model_validate(
            {
                "work_object_id": work_object_id,
                "system": system,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "url": url,
                "metadata": metadata or {},
                "idempotency_key": idempotency_key,
                "location": location,
                "action_type": action_type,
                "description": description,
                "policy_decision_id": policy_decision_id,
            }
        )
        result = _get_work_object_container().attach_reference.execute(dto)
        return _ok_response(**result)
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="advance_work_object_phase",
    description="Advance a WorkObject lifecycle phase and optionally attach a run id.",
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "work_object_id": {"type": "string"},
            "to_phase": {
                "type": "string",
                "enum": [phase.value for phase in WorkObjectPhase],
            },
            "run_id": {"type": "string"},
        },
        "required": ["work_object_id", "to_phase"],
    },
)
def advance_work_object_phase(
    work_object_id: str,
    to_phase: Literal[
        "intake",
        "executing",
        "review",
        "documenting",
        "followup",
        "closed",
        "failed",
    ],
    run_id: str | None = None,
) -> str:
    try:
        dto = AdvanceWorkObjectPhaseDTO.model_validate(
            {
                "work_object_id": work_object_id,
                "to_phase": to_phase,
                "run_id": run_id,
            }
        )
        result = _get_work_object_container().advance_phase.execute(dto)
        return _ok_response(**result)
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="close_work_object",
    description="Close a WorkObject after all required follow-up actions have been resolved.",
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "work_object_id": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["work_object_id", "reason"],
    },
)
def close_work_object(work_object_id: str, reason: str) -> str:
    try:
        dto = CloseWorkObjectDTO.model_validate(
            {"work_object_id": work_object_id, "reason": reason}
        )
        result = _get_work_object_container().close.execute(dto)
        return _ok_response(**result)
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="get_work_object_timeline",
    description="Return the persisted integration event timeline for one WorkObject.",
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "work_object_id": {"type": "string"},
            "limit": {"type": "integer", "default": 100},
        },
        "required": ["work_object_id"],
    },
)
def get_work_object_timeline(work_object_id: str, limit: int = 100) -> str:
    try:
        events = _get_work_object_container().timeline.execute(work_object_id, limit=limit)
        return _ok_response(events=[event.model_dump(mode="json") for event in events])
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="send_to_slack",
    description="Send a summary message to Slack through a configured webhook URL.",
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Slack message text."},
            "blocks": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Optional Slack Block Kit payload.",
            },
            "webhook_url": {
                "type": "string",
                "description": "Optional webhook URL; defaults to DS_AGENT_SLACK_WEBHOOK_URL.",
            },
        },
        "required": ["message"],
    },
    timeout=30,
    safety_level="caution",
)
def send_to_slack(
    message: str,
    blocks: list[dict[str, object]] | None = None,
    webhook_url: str | None = None,
) -> str:
    url = webhook_url or os.environ.get("DS_AGENT_SLACK_WEBHOOK_URL")
    if not url:
        return json.dumps({"error": "Slack webhook URL is not configured"})
    client = SlackClient()
    return json.dumps(client.send(url, text=message, blocks=blocks))


@tool(
    name="post_to_slack",
    description="Post a Slack message and record the resulting external reference against a WorkObject.",
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "work_object_id": {"type": "string"},
            "message": {"type": "string"},
            "blocks": {"type": "array", "items": {"type": "object"}},
            "webhook_url": {"type": "string"},
            "channel": {"type": "string"},
            "thread_ts": {"type": "string"},
            "location": {
                "type": "string",
                "enum": ["request", "documentation", "follow_up"],
                "default": "documentation",
            },
            "dry_run": {"type": "boolean", "default": False},
        },
        "required": ["work_object_id", "message"],
    },
    timeout=30,
    safety_level="caution",
)
def post_to_slack(
    work_object_id: str,
    message: str,
    blocks: list[dict[str, object]] | None = None,
    webhook_url: str | None = None,
    channel: str | None = None,
    thread_ts: str | None = None,
    location: Literal["request", "documentation", "follow_up"] = "documentation",
    dry_run: bool = False,
) -> str:
    try:
        resolved_url = webhook_url or os.environ.get("DS_AGENT_SLACK_WEBHOOK_URL")
        if not resolved_url and not dry_run:
            return json.dumps({"error": "Slack webhook URL is not configured"})
        request = SlackMessageRequest(
            webhook_url=resolved_url or "https://dry-run.invalid/slack",
            text_fallback=message,
            blocks=blocks or [],
            channel=channel,
            thread_ts=thread_ts,
        )
        result = _get_work_object_container().hub.post_to_slack(
            work_object_id=work_object_id,
            request=request,
            location=location,
            dry_run=dry_run,
        )
        return _ok_response(**result)
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="publish_confluence_page",
    description="Publish a markdown brief to Confluence and attach the resulting page reference to a WorkObject.",
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "work_object_id": {"type": "string"},
            "title": {"type": "string"},
            "body_markdown": {"type": "string"},
            "space_key": {"type": "string"},
            "parent_page_id": {"type": "string"},
            "labels": {"type": "array", "items": {"type": "string"}},
            "version_comment": {"type": "string"},
            "overwrite_page_id": {"type": "string"},
            "base_url": {"type": "string"},
            "email": {"type": "string"},
            "api_token": {"type": "string"},
            "location": {
                "type": "string",
                "enum": ["request", "documentation", "follow_up"],
                "default": "documentation",
            },
            "dry_run": {"type": "boolean", "default": False},
        },
        "required": ["work_object_id", "title", "body_markdown"],
    },
    timeout=30,
    safety_level="caution",
)
def publish_confluence_page(
    work_object_id: str,
    title: str,
    body_markdown: str,
    space_key: str | None = None,
    parent_page_id: str | None = None,
    labels: list[str] | None = None,
    version_comment: str | None = None,
    overwrite_page_id: str | None = None,
    base_url: str | None = None,
    email: str | None = None,
    api_token: str | None = None,
    location: Literal["request", "documentation", "follow_up"] = "documentation",
    dry_run: bool = False,
) -> str:
    try:
        resolved_base_url = base_url or os.environ.get("DS_AGENT_CONFLUENCE_BASE_URL")
        resolved_email = email or os.environ.get("DS_AGENT_CONFLUENCE_EMAIL")
        resolved_api_token = api_token or os.environ.get("DS_AGENT_CONFLUENCE_API_TOKEN")
        resolved_space_key = space_key or os.environ.get("DS_AGENT_CONFLUENCE_SPACE_KEY")
        if not resolved_space_key and not dry_run:
            return json.dumps({"error": "Confluence space key is not configured"})
        if not resolved_base_url and not dry_run:
            return json.dumps({"error": "Confluence credentials are not fully configured"})
        if not resolved_email and not dry_run:
            return json.dumps({"error": "Confluence credentials are not fully configured"})
        if not resolved_api_token and not dry_run:
            return json.dumps({"error": "Confluence credentials are not fully configured"})
        request_model = ConfluencePageRequest(
            base_url=resolved_base_url or "https://dry-run.invalid/confluence",
            email=resolved_email or "dry-run@invalid.local",
            api_token=resolved_api_token or "dry-run",
            space_key=resolved_space_key or "DRYRUN",
            title=title,
            markdown_body=body_markdown,
            parent_page_id=parent_page_id,
            labels=_dedupe_strings(
                [*(labels or []), "ds-agent", f"wo-{work_object_id.lower()}"]
            ),
            version_comment=version_comment,
            overwrite_page_id=overwrite_page_id,
        )
        result = _get_work_object_container().hub.publish_confluence_page(
            work_object_id=work_object_id,
            request=request_model,
            location=location,
            dry_run=dry_run,
        )
        return _ok_response(**result)
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="publish_notion_page",
    description="Publish a markdown brief to Notion and attach the resulting page reference to a WorkObject.",
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "work_object_id": {"type": "string"},
            "title": {"type": "string"},
            "body_markdown": {"type": "string"},
            "parent_page_id": {"type": "string"},
            "database_id": {"type": "string"},
            "title_property": {"type": "string", "default": "title"},
            "status": {"type": "string"},
            "owner": {"type": "string"},
            "quarter": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "token": {"type": "string"},
            "api_base_url": {"type": "string"},
            "location": {
                "type": "string",
                "enum": ["request", "documentation", "follow_up"],
                "default": "documentation",
            },
            "dry_run": {"type": "boolean", "default": False},
        },
        "required": ["work_object_id", "title", "body_markdown"],
    },
    timeout=30,
    safety_level="caution",
)
def publish_notion_page(
    work_object_id: str,
    title: str,
    body_markdown: str,
    parent_page_id: str | None = None,
    database_id: str | None = None,
    title_property: str = "title",
    status: str | None = None,
    owner: str | None = None,
    quarter: str | None = None,
    tags: list[str] | None = None,
    token: str | None = None,
    api_base_url: str | None = None,
    location: Literal["request", "documentation", "follow_up"] = "documentation",
    dry_run: bool = False,
) -> str:
    try:
        resolved_token = token or os.environ.get("DS_AGENT_NOTION_TOKEN")
        resolved_parent = parent_page_id or os.environ.get("DS_AGENT_NOTION_PARENT_PAGE_ID")
        resolved_database = database_id or os.environ.get("DS_AGENT_NOTION_DATABASE_ID")
        resolved_api_base_url = api_base_url or os.environ.get("DS_AGENT_NOTION_API_BASE_URL")
        if not resolved_token and not dry_run:
            return json.dumps({"error": "Notion token is not configured"})
        if not resolved_parent and not resolved_database and not dry_run:
            return json.dumps({"error": "Notion parent page or database is not configured"})
        request_model = NotionPageRequest(
            token=resolved_token or "dry-run",
            api_base_url=resolved_api_base_url or "https://dry-run.invalid/notion/v1",
            title=title,
            markdown_body=body_markdown,
            parent_page_id=resolved_parent,
            database_id=resolved_database,
            title_property=title_property,
            status=status,
            owner=owner,
            quarter=quarter,
            tags=_dedupe_strings(
                [*(tags or []), "ds-agent", f"wo-{work_object_id.lower()}"]
            ),
        )
        result = _get_work_object_container().hub.publish_notion_page(
            work_object_id=work_object_id,
            request=request_model,
            location=location,
            dry_run=dry_run,
        )
        return _ok_response(**result)
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="create_jira_ticket",
    description="Create a Jira issue using configured Jira credentials.",
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "description": {"type": "string"},
            "project": {"type": "string"},
            "issue_type": {"type": "string", "default": "Task"},
            "assignee": {"type": "string"},
            "priority": {"type": "string"},
            "labels": {"type": "array", "items": {"type": "string"}},
            "base_url": {"type": "string"},
            "work_object_id": {"type": "string"},
            "location": {
                "type": "string",
                "enum": ["request", "documentation", "follow_up"],
                "default": "follow_up",
            },
            "dry_run": {"type": "boolean", "default": False},
        },
        "required": ["summary", "description", "project"],
    },
    timeout=30,
    safety_level="caution",
)
def create_jira_ticket(
    summary: str,
    description: str,
    project: str,
    issue_type: str = "Task",
    assignee: str | None = None,
    priority: str | None = None,
    labels: list[str] | None = None,
    base_url: str | None = None,
    work_object_id: str | None = None,
    location: Literal["request", "documentation", "follow_up"] = "follow_up",
    dry_run: bool = False,
) -> str:
    resolved_base_url = base_url or os.environ.get("DS_AGENT_JIRA_BASE_URL")
    email = os.environ.get("DS_AGENT_JIRA_EMAIL")
    api_token = os.environ.get("DS_AGENT_JIRA_API_TOKEN")
    if work_object_id:
        try:
            normalized_labels = list(labels or [])
            normalized_labels.extend(["ds-agent", f"wo-{work_object_id.lower()}"])
            request = JiraIssueRequest(
                base_url=resolved_base_url or "https://dry-run.invalid/jira",
                email=email or "dry-run@invalid.local",
                api_token=api_token or "dry-run",
                project_key=project,
                summary=summary,
                description=description,
                issue_type=issue_type,
                assignee=assignee,
                priority=priority,
                labels=list(dict.fromkeys(normalized_labels)),
            )
            if not resolved_base_url and not dry_run:
                return json.dumps({"error": "Jira credentials are not fully configured"})
            if not email and not dry_run:
                return json.dumps({"error": "Jira credentials are not fully configured"})
            if not api_token and not dry_run:
                return json.dumps({"error": "Jira credentials are not fully configured"})
            result = _get_work_object_container().hub.create_jira_ticket(
                work_object_id=work_object_id,
                request=request,
                location=location,
                dry_run=dry_run,
            )
            return _ok_response(**result)
        except Exception as exc:
            return _handle_error(exc)
    if not resolved_base_url or not email or not api_token:
        return json.dumps({"error": "Jira credentials are not fully configured"})
    client = JiraClient()
    payload = client.create_issue(
        base_url=resolved_base_url,
        email=email,
        api_token=api_token,
        project=project,
        summary=summary,
        description=description,
        issue_type=issue_type,
        assignee=assignee,
        priority=priority,
        labels=labels,
    )
    return json.dumps(payload)


@tool(
    name="open_git_pr",
    description="Create a GitHub pull request or GitLab merge request and attach it to a WorkObject.",
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "work_object_id": {"type": "string"},
            "provider": {"type": "string", "enum": ["github", "gitlab"], "default": "github"},
            "repo": {"type": "string"},
            "base_branch": {"type": "string"},
            "head_branch": {"type": "string"},
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content_base64": {"type": "string"},
                        "mode": {"type": "string", "enum": ["add", "update", "delete"]},
                    },
                    "required": ["path", "mode"],
                },
            },
            "title": {"type": "string"},
            "body_md": {"type": "string"},
            "reviewers": {"type": "array", "items": {"type": "string"}},
            "labels": {"type": "array", "items": {"type": "string"}},
            "draft": {"type": "boolean", "default": False},
            "api_base_url": {"type": "string"},
            "token": {"type": "string"},
            "location": {
                "type": "string",
                "enum": ["request", "documentation", "follow_up"],
                "default": "documentation",
            },
            "dry_run": {"type": "boolean", "default": False},
        },
        "required": ["work_object_id", "repo", "base_branch", "files", "title", "body_md"],
    },
    timeout=60,
    safety_level="caution",
)
def open_git_pr(
    work_object_id: str,
    repo: str,
    base_branch: str,
    files: list[dict],
    title: str,
    body_md: str,
    provider: Literal["github", "gitlab"] = "github",
    head_branch: str | None = None,
    reviewers: list[str] | None = None,
    labels: list[str] | None = None,
    draft: bool = False,
    api_base_url: str | None = None,
    token: str | None = None,
    location: Literal["request", "documentation", "follow_up"] = "documentation",
    dry_run: bool = False,
) -> str:
    try:
        env_prefix = "GITHUB" if provider == "github" else "GITLAB"
        resolved_token = token or os.environ.get(f"DS_AGENT_{env_prefix}_TOKEN")
        resolved_api_base_url = api_base_url or os.environ.get(
            f"DS_AGENT_{env_prefix}_API_BASE_URL"
        )
        if not resolved_token and not dry_run:
            return json.dumps({"error": f"{provider.title()} token is not configured"})
        request_model = GitPRRequest(
            provider=provider,
            api_base_url=resolved_api_base_url,
            repository=repo,
            token=resolved_token or "dry-run",
            base_branch=base_branch,
            head_branch=head_branch or _default_git_head_branch(work_object_id, title),
            pr_title=title,
            pr_body_markdown=body_md,
            files=[GitFileChange.model_validate(item) for item in files],
            reviewers=list(reviewers or []),
            labels=_dedupe_strings(
                [*(labels or []), "ds-agent", f"wo-{work_object_id.lower()}"]
            ),
            draft=draft,
            commit_message=f"feat(ds): {title}\n\nWO: {work_object_id}",
        )
        result = _get_work_object_container().hub.open_git_pr(
            work_object_id=work_object_id,
            request=request_model,
            location=location,
            dry_run=dry_run,
        )
        return _ok_response(**result)
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="create_git_pr",
    description="Create a GitHub pull request using a configured repository token.",
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "body": {"type": "string"},
            "head": {"type": "string"},
            "base": {"type": "string", "default": "main"},
            "repository": {"type": "string"},
        },
        "required": ["title", "body", "head"],
    },
    timeout=30,
    safety_level="caution",
)
def create_git_pr(
    title: str,
    body: str,
    head: str,
    base: str = "main",
    repository: str | None = None,
) -> str:
    resolved_repo = repository or os.environ.get("DS_AGENT_GITHUB_REPO")
    token = os.environ.get("DS_AGENT_GITHUB_TOKEN")
    if not resolved_repo or not token:
        return json.dumps({"error": "GitHub repository/token is not configured"})
    client = GitClient()
    payload = client.create_pull_request(
        repository=resolved_repo,
        token=token,
        title=title,
        body=body,
        head=head,
        base=base,
    )
    return json.dumps(payload)


@tool(
    name="send_email",
    description=(
        "Send an email via SMTP. Requires DS_AGENT_EMAIL_SMTP_HOST and "
        "DS_AGENT_EMAIL_FROM_ADDRESS environment variables (or explicit parameters). "
        "When SMTP is not configured, the email is simulated and logged."
    ),
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "work_object_id": {
                "type": "string",
                "description": "WorkObject to track this email against.",
            },
            "to": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Recipient email addresses.",
            },
            "subject": {"type": "string"},
            "body_html": {"type": "string", "default": ""},
            "body_text": {"type": "string", "default": ""},
            "cc": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
            },
            "reply_to": {"type": "string"},
            "dry_run": {"type": "boolean", "default": False},
        },
        "required": ["work_object_id", "to", "subject"],
    },
    timeout=30,
    safety_level="caution",
)
def send_email(
    work_object_id: str,
    to: list[str],
    subject: str,
    body_html: str = "",
    body_text: str = "",
    cc: list[str] | None = None,
    reply_to: str | None = None,
    dry_run: bool = False,
) -> str:
    """Send an email tracked against a work object."""
    from ds_agent.infrastructure.external.email_connector import EmailRequest

    try:
        request = EmailRequest(
            to=to,
            cc=cc or [],
            subject=subject,
            body_html=body_html,
            body_text=body_text or subject,
            reply_to=reply_to,
        )
        result = _get_work_object_container().hub.send_email(
            work_object_id=work_object_id,
            request=request,
            location="follow_up",
            dry_run=dry_run,
        )
        return _ok_response(**result)
    except Exception as exc:
        return _handle_error(exc)


@tool(
    name="create_calendar_event",
    description=(
        "Create a calendar event via Google Calendar API. "
        "Requires DS_AGENT_CALENDAR_CREDENTIALS_JSON. "
        "When credentials are absent, the event is simulated and logged."
    ),
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "work_object_id": {
                "type": "string",
                "description": "WorkObject to track this event against.",
            },
            "summary": {"type": "string"},
            "description": {"type": "string", "default": ""},
            "start": {
                "type": "string",
                "description": "ISO-8601 datetime for event start.",
            },
            "end": {
                "type": "string",
                "description": "ISO-8601 datetime for event end.",
            },
            "timezone": {"type": "string", "default": "UTC"},
            "attendees": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
            },
            "calendar_id": {"type": "string", "default": "primary"},
            "conference_tool": {
                "type": "string",
                "enum": ["meet", "zoom", "teams"],
            },
            "dry_run": {"type": "boolean", "default": False},
        },
        "required": ["work_object_id", "summary", "start", "end"],
    },
    timeout=30,
    safety_level="caution",
)
def create_calendar_event(
    work_object_id: str,
    summary: str,
    start: str,
    end: str,
    description: str = "",
    timezone: str = "UTC",
    attendees: list[str] | None = None,
    calendar_id: str = "primary",
    conference_tool: str | None = None,
    dry_run: bool = False,
) -> str:
    """Create a calendar event tracked against a work object."""
    from ds_agent.infrastructure.external.calendar_connector import (
        CalendarEventRequest,
    )

    try:
        request = CalendarEventRequest(
            calendar_id=calendar_id,
            summary=summary,
            description=description,
            start=start,
            end=end,
            timezone=timezone,
            attendees_email=attendees or [],
            conference_tool=conference_tool,  # type: ignore[arg-type]
        )
        result = _get_work_object_container().hub.create_calendar_event(
            work_object_id=work_object_id,
            request=request,
            location="follow_up",
            dry_run=dry_run,
        )
        return _ok_response(**result)
    except Exception as exc:
        return _handle_error(exc)
