"""Real channel adapters for stakeholder delivery."""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import smtplib
import ssl
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path
from typing import Any, Protocol
from urllib import request
from urllib.parse import urlsplit

from ds_agent.domain.entities.delivery_pack import (
    AudienceKind,
    DeliveryArtifact,
    DeliveryChannel,
    DeliveryPack,
    SpeculativeClaimsPolicy,
)
from ds_agent.infrastructure.delivery.delivery_router import (
    ChannelAdapter,
    SimulatedChannelAdapter,
)
from ds_agent.infrastructure.external.document_converters import (
    markdown_to_confluence_storage,
    markdown_to_notion_blocks,
)
from ds_agent.infrastructure.external.jira_client import JiraClient
from ds_agent.infrastructure.external.slack_client import SlackClient


@dataclass(frozen=True)
class SmtpEmailConfig:
    host: str
    port: int
    from_address: str
    username: str | None = None
    password: str | None = None
    use_ssl: bool = False
    use_starttls: bool = True
    default_to: tuple[str, ...] = ()


@dataclass(frozen=True)
class SlackConfig:
    bot_token: str | None = None
    webhook_url: str | None = None
    api_base_url: str = "https://slack.com/api"
    default_channel_id: str | None = None
    default_dm_user_id: str | None = None


@dataclass(frozen=True)
class NotionConfig:
    token: str
    parent_page_id: str | None = None
    database_id: str | None = None
    title_property: str = "title"
    api_base_url: str = "https://api.notion.com/v1"
    notion_version: str = "2022-06-28"


@dataclass(frozen=True)
class ConfluenceConfig:
    base_url: str
    email: str
    api_token: str
    space_key: str | None = None
    parent_page_id: str | None = None


@dataclass(frozen=True)
class JiraConfig:
    base_url: str
    email: str
    api_token: str
    project_key: str | None = None
    issue_type: str = "Task"


@dataclass(frozen=True)
class ComplianceConfig:
    endpoint_url: str
    api_token: str | None = None
    api_key: str | None = None


class EmailTransport(Protocol):
    def send_message(self, config: SmtpEmailConfig, message: EmailMessage) -> str: ...


class SlackApiTransport(Protocol):
    def post_message(
        self,
        *,
        api_base_url: str,
        bot_token: str,
        channel: str,
        text: str,
        thread_ts: str | None = None,
    ) -> dict[str, Any]: ...


class NotionTransport(Protocol):
    def create_page(
        self,
        *,
        config: NotionConfig,
        title: str,
        markdown: str,
        parent_page_id: str | None,
        database_id: str | None,
    ) -> dict[str, Any]: ...


class ConfluenceTransport(Protocol):
    def create_page(
        self,
        *,
        config: ConfluenceConfig,
        title: str,
        html: str,
        space_key: str,
        parent_page_id: str | None,
    ) -> dict[str, Any]: ...


class JiraTransport(Protocol):
    def create_issue(
        self,
        *,
        config: JiraConfig,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str,
        labels: Sequence[str] = (),
    ) -> dict[str, Any]: ...

    def attach_file(
        self,
        *,
        config: JiraConfig,
        issue_key: str,
        file_path: Path,
    ) -> dict[str, Any]: ...


class ComplianceTransport(Protocol):
    def submit(
        self,
        *,
        config: ComplianceConfig,
        payload: dict[str, Any],
    ) -> dict[str, Any]: ...


class DefaultEmailTransport:
    def send_message(self, config: SmtpEmailConfig, message: EmailMessage) -> str:
        if "Message-ID" not in message:
            message["Message-ID"] = make_msgid()
        smtp_client: smtplib.SMTP
        if config.use_ssl:
            smtp_client = smtplib.SMTP_SSL(config.host, config.port, timeout=10)
        else:
            smtp_client = smtplib.SMTP(config.host, config.port, timeout=10)
        with smtp_client as smtp:
            if config.use_starttls and not config.use_ssl:
                smtp.starttls(context=ssl.create_default_context())
            if config.username and config.password:
                smtp.login(config.username, config.password)
            smtp.send_message(message)
        return str(message["Message-ID"])


class DefaultSlackApiTransport:
    def post_message(
        self,
        *,
        api_base_url: str,
        bot_token: str,
        channel: str,
        text: str,
        thread_ts: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"channel": channel, "text": text}
        if thread_ts:
            payload["thread_ts"] = thread_ts
        req = request.Request(
            f"{api_base_url.rstrip('/')}/chat.postMessage",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body)
        if not isinstance(parsed, dict) or not parsed.get("ok"):
            raise ValueError(f"Slack API error: {parsed}")
        return parsed


class DefaultNotionTransport:
    def create_page(
        self,
        *,
        config: NotionConfig,
        title: str,
        markdown: str,
        parent_page_id: str | None,
        database_id: str | None,
    ) -> dict[str, Any]:
        resolved_page_id = parent_page_id or config.parent_page_id
        resolved_database_id = database_id or config.database_id
        if not resolved_page_id and not resolved_database_id:
            raise ValueError("Notion parent page or database is not configured")

        payload: dict[str, Any] = {
            "parent": (
                {"page_id": resolved_page_id}
                if resolved_page_id
                else {"database_id": resolved_database_id}
            ),
            "properties": {
                config.title_property: {
                    "title": [{"type": "text", "text": {"content": title[:2000]}}]
                }
            },
            "children": _markdown_to_notion_blocks(markdown),
        }
        req = request.Request(
            f"{config.api_base_url.rstrip('/')}/pages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {config.token}",
                "Content-Type": "application/json",
                "Notion-Version": config.notion_version,
            },
            method="POST",
        )
        with request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body)
        if not isinstance(parsed, dict) or parsed.get("object") == "error":
            raise ValueError(f"Notion API error: {parsed}")
        return parsed


class DefaultConfluenceTransport:
    def create_page(
        self,
        *,
        config: ConfluenceConfig,
        title: str,
        html: str,
        space_key: str,
        parent_page_id: str | None,
    ) -> dict[str, Any]:
        token = base64.b64encode(f"{config.email}:{config.api_token}".encode()).decode("ascii")
        payload: dict[str, Any] = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": html,
                    "representation": "storage",
                }
            },
        }
        resolved_parent = parent_page_id or config.parent_page_id
        if resolved_parent:
            payload["ancestors"] = [{"id": resolved_parent}]
        req = request.Request(
            f"{config.base_url.rstrip('/')}/rest/api/content",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Basic {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body)
        if not isinstance(parsed, dict) or "id" not in parsed:
            raise ValueError(f"Confluence API error: {parsed}")
        return parsed


class DefaultJiraTransport:
    def __init__(self) -> None:
        self._client = JiraClient()

    def create_issue(
        self,
        *,
        config: JiraConfig,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str,
        labels: Sequence[str] = (),
    ) -> dict[str, Any]:
        payload = self._client.create_issue(
            base_url=config.base_url,
            email=config.email,
            api_token=config.api_token,
            project=project_key,
            summary=summary,
            description=description,
            issue_type=issue_type,
            labels=list(labels),
        )
        if not isinstance(payload, dict) or not any(key in payload for key in ("id", "key")):
            raise ValueError(f"Jira API error: {payload}")
        return payload

    def attach_file(
        self,
        *,
        config: JiraConfig,
        issue_key: str,
        file_path: Path,
    ) -> dict[str, Any]:
        token = base64.b64encode(f"{config.email}:{config.api_token}".encode()).decode("ascii")
        file_bytes = file_path.read_bytes()
        boundary = "----DSAgentJiraAttachmentBoundary"
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        disposition = (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode()
        ending = f"\r\n--{boundary}--\r\n".encode()
        payload = disposition + file_bytes + ending
        req = request.Request(
            f"{config.base_url.rstrip('/')}/rest/api/3/issue/{issue_key}/attachments",
            data=payload,
            headers={
                "Authorization": f"Basic {token}",
                "X-Atlassian-Token": "no-check",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body)
        if isinstance(parsed, list):
            return {"attachments": parsed}
        if isinstance(parsed, dict):
            return parsed
        return {"response": body}


class DefaultComplianceTransport:
    def submit(
        self,
        *,
        config: ComplianceConfig,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if config.api_token:
            headers["Authorization"] = f"Bearer {config.api_token}"
        elif config.api_key:
            headers["X-API-Key"] = config.api_key
        req = request.Request(
            config.endpoint_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with request.urlopen(req, timeout=15) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise ValueError(f"Compliance API error: {parsed}")
        return parsed


@dataclass
class SmtpEmailAdapter:
    config: SmtpEmailConfig
    transport: EmailTransport | None = None
    name: str = "smtp:email"

    def send(
        self,
        *,
        pack: DeliveryPack,
        artifact: DeliveryArtifact,
        channel: DeliveryChannel,
    ) -> str:
        del channel
        recipients = _resolve_targets(
            pack=pack,
            artifact=artifact,
            context_key="email_to",
            fallback=self.config.default_to,
        )
        if not recipients:
            raise ValueError("email recipients are not configured")

        message = EmailMessage()
        message["From"] = self.config.from_address
        message["To"] = ", ".join(recipients)
        cc = _split_csv(pack.global_context.get("email_cc"))
        bcc = _split_csv(pack.global_context.get("email_bcc"))
        if cc:
            message["Cc"] = ", ".join(cc)
        message["Subject"] = _resolve_title(
            pack=pack,
            artifact=artifact,
            override=pack.global_context.get("email_subject"),
        )
        message.set_content(_compose_delivery_body(pack=pack, artifact=artifact))
        if bcc:
            message["Bcc"] = ", ".join(bcc)

        attachment = _artifact_path(artifact)
        if attachment is not None and attachment.exists():
            maintype, subtype = _guess_mime_parts(attachment)
            message.add_attachment(
                attachment.read_bytes(),
                maintype=maintype,
                subtype=subtype,
                filename=attachment.name,
            )
        transport = self.transport or DefaultEmailTransport()
        return transport.send_message(self.config, message)


@dataclass
class SlackChannelAdapter:
    config: SlackConfig
    api_transport: SlackApiTransport | None = None
    webhook_client: SlackClient | None = None
    name: str = "slack:channel"

    def send(
        self,
        *,
        pack: DeliveryPack,
        artifact: DeliveryArtifact,
        channel: DeliveryChannel,
    ) -> str:
        del channel
        target = _resolve_first_target(
            pack=pack,
            artifact=artifact,
            context_key="slack_channel_id",
            fallback=self.config.default_channel_id,
        )
        text = _compose_slack_text(pack=pack, artifact=artifact)
        if self.config.bot_token and target:
            transport = self.api_transport or DefaultSlackApiTransport()
            payload = transport.post_message(
                api_base_url=self.config.api_base_url,
                bot_token=self.config.bot_token,
                channel=target,
                text=text,
                thread_ts=pack.global_context.get("slack_thread_ts"),
            )
            return f"{payload.get('channel', target)}:{payload.get('ts', 'sent')}"
        if self.config.webhook_url:
            client = self.webhook_client or SlackClient()
            payload = client.send(self.config.webhook_url, text=text)
            return str(payload.get("response", "webhook"))
        raise ValueError("Slack channel target or credentials are not configured")


@dataclass
class SlackDmAdapter:
    config: SlackConfig
    api_transport: SlackApiTransport | None = None
    name: str = "slack:dm"

    def send(
        self,
        *,
        pack: DeliveryPack,
        artifact: DeliveryArtifact,
        channel: DeliveryChannel,
    ) -> str:
        del channel
        if not self.config.bot_token:
            raise ValueError("Slack bot token is not configured for direct messages")
        target = _resolve_first_target(
            pack=pack,
            artifact=artifact,
            context_key="slack_dm_user_id",
            fallback=self.config.default_dm_user_id,
        )
        if not target:
            raise ValueError("Slack DM user id is not configured")
        transport = self.api_transport or DefaultSlackApiTransport()
        payload = transport.post_message(
            api_base_url=self.config.api_base_url,
            bot_token=self.config.bot_token,
            channel=target,
            text=_compose_slack_text(pack=pack, artifact=artifact),
            thread_ts=pack.global_context.get("slack_thread_ts"),
        )
        return f"{payload.get('channel', target)}:{payload.get('ts', 'sent')}"


@dataclass
class NotionPageAdapter:
    config: NotionConfig
    transport: NotionTransport | None = None
    name: str = "notion:page"

    def send(
        self,
        *,
        pack: DeliveryPack,
        artifact: DeliveryArtifact,
        channel: DeliveryChannel,
    ) -> str:
        del channel
        transport = self.transport or DefaultNotionTransport()
        payload = transport.create_page(
            config=self.config,
            title=_resolve_title(
                pack=pack,
                artifact=artifact,
                override=pack.global_context.get("notion_title"),
            ),
            markdown=_artifact_markdown(pack=pack, artifact=artifact),
            parent_page_id=pack.global_context.get("notion_parent_page_id"),
            database_id=pack.global_context.get("notion_database_id"),
        )
        return str(payload.get("url") or payload.get("id") or "notion-page")


@dataclass
class ConfluenceAdapter:
    config: ConfluenceConfig
    transport: ConfluenceTransport | None = None
    name: str = "confluence:page"

    def send(
        self,
        *,
        pack: DeliveryPack,
        artifact: DeliveryArtifact,
        channel: DeliveryChannel,
    ) -> str:
        del channel
        space_key = pack.global_context.get("confluence_space_key") or self.config.space_key
        if not space_key:
            raise ValueError("Confluence space key is not configured")
        payload = (self.transport or DefaultConfluenceTransport()).create_page(
            config=self.config,
            title=_resolve_title(
                pack=pack,
                artifact=artifact,
                override=pack.global_context.get("confluence_title"),
            ),
            html=_markdown_to_confluence_storage(_artifact_markdown(pack=pack, artifact=artifact)),
            space_key=space_key,
            parent_page_id=pack.global_context.get("confluence_parent_page_id"),
        )
        links = payload.get("_links")
        if isinstance(links, dict) and links.get("webui"):
            return _join_base_url(self.config.base_url, str(links["webui"]))
        return str(payload.get("id") or "confluence-page")


@dataclass
class JiraAdapter:
    config: JiraConfig
    transport: JiraTransport | None = None
    name: str = "jira:ticket"

    def send(
        self,
        *,
        pack: DeliveryPack,
        artifact: DeliveryArtifact,
        channel: DeliveryChannel,
    ) -> str:
        del channel
        project_key = pack.global_context.get("jira_project_key") or self.config.project_key
        if not project_key:
            raise ValueError("Jira project key is not configured")
        transport = self.transport or DefaultJiraTransport()
        labels = _split_csv(pack.global_context.get("jira_labels"))
        issue = transport.create_issue(
            config=self.config,
            project_key=project_key,
            summary=_resolve_title(
                pack=pack,
                artifact=artifact,
                override=pack.global_context.get("jira_summary"),
            ),
            description=_artifact_markdown(pack=pack, artifact=artifact),
            issue_type=pack.global_context.get("jira_issue_type") or self.config.issue_type,
            labels=labels,
        )
        issue_key = str(issue.get("key") or issue.get("id") or "jira-issue")
        attachment = _artifact_path(artifact)
        if attachment is not None and attachment.exists():
            transport.attach_file(
                config=self.config,
                issue_key=issue_key,
                file_path=attachment,
            )
        return issue_key


@dataclass
class ComplianceAdapter:
    config: ComplianceConfig
    transport: ComplianceTransport | None = None
    name: str = "compliance:system"

    def send(
        self,
        *,
        pack: DeliveryPack,
        artifact: DeliveryArtifact,
        channel: DeliveryChannel,
    ) -> str:
        del channel
        artifact_path = _artifact_path(artifact)
        if artifact_path is None or artifact_path.suffix.lower() != ".pdf":
            raise ValueError("Compliance adapter only accepts rendered PDF artifacts")
        if not artifact_path.exists():
            raise ValueError(f"Compliance artifact file does not exist: {artifact_path}")
        if artifact.audience != AudienceKind.AUDITOR:
            raise ValueError("Compliance adapter only accepts auditor artifacts")
        if artifact.content_policy.speculative_claims != SpeculativeClaimsPolicy.FORBIDDEN:
            raise ValueError("Compliance submission requires speculative_claims=forbidden")
        if not pack.signature:
            raise ValueError("Compliance submission requires a pack signature")
        if not pack.signed_by:
            raise ValueError("Compliance submission requires signed_by metadata")
        file_bytes = artifact_path.read_bytes()
        file_sha256 = hashlib.sha256(file_bytes).hexdigest()
        payload = {
            "task_id": pack.task_id,
            "pack_id": pack.pack_id,
            "artifact_id": artifact.artifact_id,
            "artifact_type": artifact.type.value,
            "artifact_format": artifact.format.value,
            "dispatch_mode": artifact.dispatch_mode.value,
            "read_only": True,
            "generated_at": pack.generated_at.isoformat(),
            "signed_by": pack.signed_by,
            "signature": pack.signature,
            "file_name": artifact_path.name,
            "content_base64": base64.b64encode(file_bytes).decode("ascii"),
            "case_id": pack.global_context.get("compliance_case_id"),
            "tenant": pack.tenant,
            "source_analysis_id": pack.source_analysis_id,
            "file": {
                "name": artifact_path.name,
                "mime_type": "application/pdf",
                "size_bytes": len(file_bytes),
                "sha256": file_sha256,
            },
            "policy": {
                "speculative_claims": artifact.content_policy.speculative_claims.value,
                "structure": list(artifact.content_policy.structure),
                "technical_detail": artifact.content_policy.technical_detail,
                "tone": artifact.content_policy.tone,
            },
            "verification": {
                "report_id": artifact.verifier_report_id,
            },
            "audit_context": {
                "approval_chain": _structured_list_context(
                    pack.global_context.get("approval_chain")
                ),
                "policy_compliance": _structured_list_context(
                    pack.global_context.get("policy_compliance")
                ),
                "lineage": _structured_list_context(pack.global_context.get("lineage")),
                "access_log": _structured_list_context(pack.global_context.get("access_log")),
            },
        }
        response = (self.transport or DefaultComplianceTransport()).submit(
            config=self.config,
            payload=payload,
        )
        return str(
            response.get("submission_id")
            or response.get("id")
            or response.get("url")
            or "compliance-submission"
        )


def build_configured_channel_adapters(
    environment: Mapping[str, str] | None = None,
) -> dict[DeliveryChannel, ChannelAdapter]:
    env = dict(os.environ if environment is None else environment)
    real_adapters_enabled = _env_bool(
        env.get("DS_AGENT_DELIVERY_REAL_ADAPTERS_ENABLED"),
        default=True,
    )
    slack_config = _slack_config_from_env(env)
    adapters: dict[DeliveryChannel, ChannelAdapter] = {
        DeliveryChannel.EMAIL: _configured_or_simulated_adapter(
            channel_name=DeliveryChannel.EMAIL.value,
            configured=(
                SmtpEmailAdapter(email_config)
                if (email_config := _email_config_from_env(env)) is not None
                else None
            ),
            global_enabled=real_adapters_enabled,
            channel_enabled=_env_bool(env.get("DS_AGENT_EMAIL_ENABLED"), default=True),
        ),
        DeliveryChannel.SLACK_DM: _configured_or_simulated_adapter(
            channel_name=DeliveryChannel.SLACK_DM.value,
            configured=(
                SlackDmAdapter(slack_config)
                if slack_config is not None and slack_config.bot_token
                else None
            ),
            global_enabled=real_adapters_enabled,
            channel_enabled=_env_bool(env.get("DS_AGENT_SLACK_ENABLED"), default=True),
        ),
        DeliveryChannel.SLACK_CHANNEL: _configured_or_simulated_adapter(
            channel_name=DeliveryChannel.SLACK_CHANNEL.value,
            configured=(
                SlackChannelAdapter(slack_config)
                if slack_config is not None
                and (slack_config.bot_token or slack_config.webhook_url)
                else None
            ),
            global_enabled=real_adapters_enabled,
            channel_enabled=_env_bool(env.get("DS_AGENT_SLACK_ENABLED"), default=True),
        ),
        DeliveryChannel.NOTION_PAGE: _configured_or_simulated_adapter(
            channel_name=DeliveryChannel.NOTION_PAGE.value,
            configured=(
                NotionPageAdapter(notion_config)
                if (notion_config := _notion_config_from_env(env)) is not None
                else None
            ),
            global_enabled=real_adapters_enabled,
            channel_enabled=_env_bool(env.get("DS_AGENT_NOTION_ENABLED"), default=True),
        ),
        DeliveryChannel.CONFLUENCE: _configured_or_simulated_adapter(
            channel_name=DeliveryChannel.CONFLUENCE.value,
            configured=(
                ConfluenceAdapter(confluence_config)
                if (confluence_config := _confluence_config_from_env(env)) is not None
                else None
            ),
            global_enabled=real_adapters_enabled,
            channel_enabled=_env_bool(env.get("DS_AGENT_CONFLUENCE_ENABLED"), default=False),
        ),
        DeliveryChannel.JIRA_TICKET: _configured_or_simulated_adapter(
            channel_name=DeliveryChannel.JIRA_TICKET.value,
            configured=(
                JiraAdapter(jira_config)
                if (jira_config := _jira_config_from_env(env)) is not None
                else None
            ),
            global_enabled=real_adapters_enabled,
            channel_enabled=_env_bool(env.get("DS_AGENT_JIRA_ENABLED"), default=False),
        ),
        DeliveryChannel.GIT_PR: SimulatedChannelAdapter(name="simulated:git_pr"),
        DeliveryChannel.COMPLIANCE_SYSTEM: _configured_or_simulated_adapter(
            channel_name=DeliveryChannel.COMPLIANCE_SYSTEM.value,
            configured=(
                ComplianceAdapter(compliance_config)
                if (compliance_config := _compliance_config_from_env(env)) is not None
                else None
            ),
            global_enabled=real_adapters_enabled,
            channel_enabled=_env_bool(env.get("DS_AGENT_COMPLIANCE_ENABLED"), default=False),
        ),
    }
    return adapters


def _configured_or_simulated_adapter(
    *,
    channel_name: str,
    configured: ChannelAdapter | None,
    global_enabled: bool,
    channel_enabled: bool,
) -> ChannelAdapter:
    if configured is None:
        return _simulated_adapter(channel_name)
    if not global_enabled:
        return _simulated_adapter(channel_name, reason="global_flag_disabled")
    if not channel_enabled:
        return _simulated_adapter(channel_name, reason="feature_flag_disabled")
    return configured


def _simulated_adapter(channel_name: str, *, reason: str | None = None) -> SimulatedChannelAdapter:
    suffix = f":{reason}" if reason else ""
    return SimulatedChannelAdapter(name=f"simulated:{channel_name}{suffix}")


def _email_config_from_env(environment: Mapping[str, str]) -> SmtpEmailConfig | None:
    host = environment.get("DS_AGENT_EMAIL_SMTP_HOST")
    port = environment.get("DS_AGENT_EMAIL_SMTP_PORT")
    from_address = environment.get("DS_AGENT_EMAIL_FROM")
    if not host or not port or not from_address:
        return None
    return SmtpEmailConfig(
        host=host,
        port=int(port),
        from_address=from_address,
        username=environment.get("DS_AGENT_EMAIL_SMTP_USERNAME"),
        password=environment.get("DS_AGENT_EMAIL_SMTP_PASSWORD"),
        use_ssl=_env_bool(environment.get("DS_AGENT_EMAIL_SMTP_SSL")),
        use_starttls=_env_bool(environment.get("DS_AGENT_EMAIL_SMTP_STARTTLS"), default=True),
        default_to=tuple(_split_csv(environment.get("DS_AGENT_EMAIL_TO"))),
    )


def _slack_config_from_env(environment: Mapping[str, str]) -> SlackConfig | None:
    bot_token = environment.get("DS_AGENT_SLACK_BOT_TOKEN")
    webhook_url = environment.get("DS_AGENT_SLACK_WEBHOOK_URL")
    if not bot_token and not webhook_url:
        return None
    return SlackConfig(
        bot_token=bot_token,
        webhook_url=webhook_url,
        api_base_url=environment.get("DS_AGENT_SLACK_API_BASE_URL", "https://slack.com/api"),
        default_channel_id=environment.get("DS_AGENT_SLACK_CHANNEL_ID"),
        default_dm_user_id=environment.get("DS_AGENT_SLACK_DM_USER_ID"),
    )


def _notion_config_from_env(environment: Mapping[str, str]) -> NotionConfig | None:
    token = environment.get("DS_AGENT_NOTION_TOKEN")
    if not token:
        return None
    return NotionConfig(
        token=token,
        parent_page_id=environment.get("DS_AGENT_NOTION_PARENT_PAGE_ID"),
        database_id=environment.get("DS_AGENT_NOTION_DATABASE_ID"),
        title_property=environment.get("DS_AGENT_NOTION_TITLE_PROPERTY", "title"),
        api_base_url=environment.get("DS_AGENT_NOTION_API_BASE_URL", "https://api.notion.com/v1"),
        notion_version=environment.get("DS_AGENT_NOTION_VERSION", "2022-06-28"),
    )


def _confluence_config_from_env(environment: Mapping[str, str]) -> ConfluenceConfig | None:
    base_url = environment.get("DS_AGENT_CONFLUENCE_BASE_URL")
    email = environment.get("DS_AGENT_CONFLUENCE_EMAIL")
    api_token = environment.get("DS_AGENT_CONFLUENCE_API_TOKEN")
    if not base_url or not email or not api_token:
        return None
    return ConfluenceConfig(
        base_url=base_url,
        email=email,
        api_token=api_token,
        space_key=environment.get("DS_AGENT_CONFLUENCE_SPACE_KEY"),
        parent_page_id=environment.get("DS_AGENT_CONFLUENCE_PARENT_PAGE_ID"),
    )


def _jira_config_from_env(environment: Mapping[str, str]) -> JiraConfig | None:
    base_url = environment.get("DS_AGENT_JIRA_BASE_URL")
    email = environment.get("DS_AGENT_JIRA_EMAIL")
    api_token = environment.get("DS_AGENT_JIRA_API_TOKEN")
    if not base_url or not email or not api_token:
        return None
    return JiraConfig(
        base_url=base_url,
        email=email,
        api_token=api_token,
        project_key=environment.get("DS_AGENT_JIRA_PROJECT_KEY"),
        issue_type=environment.get("DS_AGENT_JIRA_ISSUE_TYPE", "Task"),
    )


def _compliance_config_from_env(environment: Mapping[str, str]) -> ComplianceConfig | None:
    endpoint_url = environment.get("DS_AGENT_COMPLIANCE_ENDPOINT")
    if not endpoint_url:
        return None
    return ComplianceConfig(
        endpoint_url=endpoint_url,
        api_token=environment.get("DS_AGENT_COMPLIANCE_API_TOKEN"),
        api_key=environment.get("DS_AGENT_COMPLIANCE_API_KEY"),
    )


def _artifact_path(artifact: DeliveryArtifact) -> Path | None:
    if not artifact.rendered_uri:
        return None
    return Path(artifact.rendered_uri)


def _artifact_markdown(*, pack: DeliveryPack, artifact: DeliveryArtifact) -> str:
    artifact_path = _artifact_path(artifact)
    excerpt = _read_artifact_excerpt(artifact_path)
    lines = [
        f"# {_resolve_title(pack=pack, artifact=artifact)}",
        "",
        f"- Task ID: {pack.task_id}",
        f"- Pack ID: {pack.pack_id}",
        f"- Artifact ID: {artifact.artifact_id}",
        f"- Audience: {artifact.audience.value}",
        f"- Format: {artifact.format.value}",
    ]
    if artifact.verifier_report_id:
        lines.append(f"- Verifier report: {artifact.verifier_report_id}")
    if pack.signature:
        lines.append(f"- Signature: {pack.signature}")
    if artifact_path is not None:
        lines.append(f"- File: {artifact_path}")
    lines.extend(["", excerpt])
    return "\n".join(lines)


def _compose_delivery_body(*, pack: DeliveryPack, artifact: DeliveryArtifact) -> str:
    body = _artifact_markdown(pack=pack, artifact=artifact)
    return body if len(body) <= 10_000 else body[:9_500] + "\n\n[truncated]"


def _compose_slack_text(*, pack: DeliveryPack, artifact: DeliveryArtifact) -> str:
    body = _compose_delivery_body(pack=pack, artifact=artifact)
    if len(body) <= 300:
        return body
    return body[:297] + "..."


def _resolve_title(
    *,
    pack: DeliveryPack,
    artifact: DeliveryArtifact,
    override: str | None = None,
) -> str:
    if override:
        return override
    return f"{artifact.type.value} for {pack.task_id}"


def _resolve_targets(
    *,
    pack: DeliveryPack,
    artifact: DeliveryArtifact,
    context_key: str,
    fallback: Sequence[str] = (),
) -> list[str]:
    if context_value := pack.global_context.get(context_key):
        return _split_csv(context_value)
    static_addresses = [
        address
        for receiver in artifact.receivers
        for address in receiver.static_addresses
        if address
    ]
    if static_addresses:
        return static_addresses
    return [str(item) for item in fallback if str(item).strip()]


def _resolve_first_target(
    *,
    pack: DeliveryPack,
    artifact: DeliveryArtifact,
    context_key: str,
    fallback: str | None = None,
) -> str | None:
    targets = _resolve_targets(
        pack=pack,
        artifact=artifact,
        context_key=context_key,
        fallback=[fallback] if fallback else (),
    )
    return targets[0] if targets else None


def _split_csv(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _env_bool(raw_value: str | None, *, default: bool = False) -> bool:
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _guess_mime_parts(path: Path) -> tuple[str, str]:
    guessed = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    maintype, _, subtype = guessed.partition("/")
    return maintype or "application", subtype or "octet-stream"


def _join_base_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    stripped_base = base_url.rstrip("/")
    if stripped_base.endswith("/wiki") and path.startswith("/wiki/"):
        stripped_base = stripped_base[: -len("/wiki")]
    if stripped_base.startswith("http://") or stripped_base.startswith("https://"):
        return stripped_base + path
    parts = urlsplit(f"https://{stripped_base}")
    origin = f"{parts.scheme}://{parts.netloc}"
    return origin + path


def _structured_list_context(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    if isinstance(parsed, str) and parsed.strip():
        return [parsed.strip()]
    return _split_csv(raw_value) if "," in raw_value else [raw_value.strip()]


def _read_artifact_excerpt(path: Path | None) -> str:
    if path is None:
        return "Rendered artifact file is not available."
    if not path.exists():
        return f"Rendered artifact file is missing: {path}"
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown", ".txt", ".html"}:
        return path.read_text(encoding="utf-8")
    if suffix == ".ipynb":
        notebook = json.loads(path.read_text(encoding="utf-8"))
        cells = notebook.get("cells", []) if isinstance(notebook, dict) else []
        rendered_cells: list[str] = []
        for cell in cells[:20]:
            if not isinstance(cell, dict):
                continue
            source = cell.get("source")
            if isinstance(source, list):
                rendered_cells.append("".join(str(part) for part in source))
            elif isinstance(source, str):
                rendered_cells.append(source)
        return "\n\n".join(rendered_cells)
    return f"Artifact file generated at {path}"


def _markdown_to_notion_blocks(markdown: str) -> list[dict[str, Any]]:
    return markdown_to_notion_blocks(markdown)


def _markdown_to_confluence_storage(markdown: str) -> str:
    return markdown_to_confluence_storage(markdown)
