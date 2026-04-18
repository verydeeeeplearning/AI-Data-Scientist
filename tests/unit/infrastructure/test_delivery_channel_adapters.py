from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import pytest

from ds_agent.domain.entities.delivery_pack import (
    ArtifactFormat,
    ArtifactType,
    AudienceKind,
    ContentPolicy,
    DeliveryArtifact,
    DeliveryChannel,
    DeliveryDispatchMode,
    DeliveryPack,
)
from ds_agent.infrastructure.delivery import (
    ComplianceAdapter,
    ConfluenceAdapter,
    JiraAdapter,
    NotionPageAdapter,
    SimulatedChannelAdapter,
    SlackChannelAdapter,
    SlackDmAdapter,
    SmtpEmailAdapter,
    build_default_channel_adapters,
)
from ds_agent.infrastructure.delivery.channel_adapters import (
    ComplianceConfig,
    ConfluenceConfig,
    JiraConfig,
    NotionConfig,
    SlackConfig,
    SmtpEmailConfig,
)


@dataclass
class FakeEmailTransport:
    config: SmtpEmailConfig | None = None
    message: EmailMessage | None = None

    def send_message(self, config: SmtpEmailConfig, message: EmailMessage) -> str:
        self.config = config
        self.message = message
        return "message-id-1"


@dataclass
class FakeSlackTransport:
    calls: list[dict[str, Any]]

    def post_message(self, **kwargs) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"ok": True, "channel": kwargs["channel"], "ts": "123.45"}


@dataclass
class FakeNotionTransport:
    last_kwargs: dict[str, Any] | None = None

    def create_page(self, **kwargs) -> dict[str, Any]:
        self.last_kwargs = kwargs
        return {"id": "notion-page-1", "url": "https://notion.so/page-1"}


@dataclass
class FakeConfluenceTransport:
    last_kwargs: dict[str, Any] | None = None

    def create_page(self, **kwargs) -> dict[str, Any]:
        self.last_kwargs = kwargs
        return {"id": "42", "_links": {"webui": "/wiki/spaces/DS/pages/42"}}


@dataclass
class FakeJiraTransport:
    create_kwargs: dict[str, Any] | None = None
    attachment_kwargs: dict[str, Any] | None = None

    def create_issue(self, **kwargs) -> dict[str, Any]:
        self.create_kwargs = kwargs
        return {"id": "10001", "key": "DS-101"}

    def attach_file(self, **kwargs) -> dict[str, Any]:
        self.attachment_kwargs = kwargs
        return {"ok": True}


@dataclass
class FakeComplianceTransport:
    last_kwargs: dict[str, Any] | None = None

    def submit(self, **kwargs) -> dict[str, Any]:
        self.last_kwargs = kwargs
        return {"submission_id": "cmp-1"}


def test_build_default_channel_adapters_prefers_real_adapters_when_env_present() -> None:
    adapters = build_default_channel_adapters(
        {
            "DS_AGENT_EMAIL_SMTP_HOST": "smtp.example.com",
            "DS_AGENT_EMAIL_SMTP_PORT": "587",
            "DS_AGENT_EMAIL_FROM": "bot@example.com",
            "DS_AGENT_SLACK_BOT_TOKEN": "xoxb-test",
            "DS_AGENT_NOTION_TOKEN": "secret-notion",
            "DS_AGENT_CONFLUENCE_BASE_URL": "https://conf.example.com/wiki",
            "DS_AGENT_CONFLUENCE_EMAIL": "conf@example.com",
            "DS_AGENT_CONFLUENCE_API_TOKEN": "conf-token",
            "DS_AGENT_CONFLUENCE_ENABLED": "true",
            "DS_AGENT_JIRA_BASE_URL": "https://jira.example.com",
            "DS_AGENT_JIRA_EMAIL": "jira@example.com",
            "DS_AGENT_JIRA_API_TOKEN": "jira-token",
            "DS_AGENT_JIRA_ENABLED": "true",
            "DS_AGENT_COMPLIANCE_ENDPOINT": "https://compliance.example.com/ingest",
            "DS_AGENT_COMPLIANCE_ENABLED": "true",
        }
    )

    assert isinstance(adapters[DeliveryChannel.EMAIL], SmtpEmailAdapter)
    assert isinstance(adapters[DeliveryChannel.SLACK_DM], SlackDmAdapter)
    assert isinstance(adapters[DeliveryChannel.SLACK_CHANNEL], SlackChannelAdapter)
    assert isinstance(adapters[DeliveryChannel.NOTION_PAGE], NotionPageAdapter)
    assert isinstance(adapters[DeliveryChannel.CONFLUENCE], ConfluenceAdapter)
    assert isinstance(adapters[DeliveryChannel.JIRA_TICKET], JiraAdapter)
    assert isinstance(adapters[DeliveryChannel.COMPLIANCE_SYSTEM], ComplianceAdapter)
    assert adapters[DeliveryChannel.GIT_PR].name == "simulated:git_pr"


def test_build_default_channel_adapters_feature_flags_phase3_channels() -> None:
    base_env = {
        "DS_AGENT_CONFLUENCE_BASE_URL": "https://conf.example.com/wiki",
        "DS_AGENT_CONFLUENCE_EMAIL": "conf@example.com",
        "DS_AGENT_CONFLUENCE_API_TOKEN": "conf-token",
        "DS_AGENT_JIRA_BASE_URL": "https://jira.example.com",
        "DS_AGENT_JIRA_EMAIL": "jira@example.com",
        "DS_AGENT_JIRA_API_TOKEN": "jira-token",
        "DS_AGENT_COMPLIANCE_ENDPOINT": "https://compliance.example.com/ingest",
    }

    disabled = build_default_channel_adapters(base_env)
    enabled = build_default_channel_adapters(
        {
            **base_env,
            "DS_AGENT_CONFLUENCE_ENABLED": "true",
            "DS_AGENT_JIRA_ENABLED": "1",
            "DS_AGENT_COMPLIANCE_ENABLED": "yes",
        }
    )

    assert isinstance(disabled[DeliveryChannel.CONFLUENCE], SimulatedChannelAdapter)
    assert isinstance(disabled[DeliveryChannel.JIRA_TICKET], SimulatedChannelAdapter)
    assert isinstance(disabled[DeliveryChannel.COMPLIANCE_SYSTEM], SimulatedChannelAdapter)
    assert (
        disabled[DeliveryChannel.CONFLUENCE].name
        == "simulated:confluence:feature_flag_disabled"
    )
    assert (
        disabled[DeliveryChannel.JIRA_TICKET].name
        == "simulated:jira_ticket:feature_flag_disabled"
    )
    assert (
        disabled[DeliveryChannel.COMPLIANCE_SYSTEM].name
        == "simulated:compliance_system:feature_flag_disabled"
    )
    assert isinstance(enabled[DeliveryChannel.CONFLUENCE], ConfluenceAdapter)
    assert isinstance(enabled[DeliveryChannel.JIRA_TICKET], JiraAdapter)
    assert isinstance(enabled[DeliveryChannel.COMPLIANCE_SYSTEM], ComplianceAdapter)


def test_smtp_email_adapter_sends_attachment_and_resolves_recipients(tmp_path: Path) -> None:
    pack, artifact = _markdown_pack(tmp_path)
    transport = FakeEmailTransport()
    adapter = SmtpEmailAdapter(
        SmtpEmailConfig(
            host="smtp.example.com",
            port=587,
            from_address="bot@example.com",
        ),
        transport=transport,
    )

    receipt_id = adapter.send(
        pack=pack.model_copy(update={"global_context": {"email_to": "pm@example.com"}}),
        artifact=artifact,
        channel=DeliveryChannel.EMAIL,
    )

    assert receipt_id == "message-id-1"
    assert transport.message is not None
    assert transport.message["To"] == "pm@example.com"
    assert transport.message["Subject"] == "pm_action_memo for TC-2026-001"
    attachments = list(transport.message.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "memo.md"


def test_slack_adapters_post_to_channel_and_dm(tmp_path: Path) -> None:
    pack, artifact = _markdown_pack(tmp_path)
    calls: list[dict[str, Any]] = []
    transport = FakeSlackTransport(calls=calls)
    channel_adapter = SlackChannelAdapter(
        SlackConfig(bot_token="xoxb-test", default_channel_id="C123"),
        api_transport=transport,
    )
    dm_adapter = SlackDmAdapter(
        SlackConfig(bot_token="xoxb-test", default_dm_user_id="U123"),
        api_transport=transport,
    )

    channel_receipt = channel_adapter.send(
        pack=pack,
        artifact=artifact,
        channel=DeliveryChannel.SLACK_CHANNEL,
    )
    dm_receipt = dm_adapter.send(
        pack=pack,
        artifact=artifact,
        channel=DeliveryChannel.SLACK_DM,
    )

    assert channel_receipt == "C123:123.45"
    assert dm_receipt == "U123:123.45"
    assert calls[0]["channel"] == "C123"
    assert calls[1]["channel"] == "U123"


def test_notion_and_confluence_adapters_render_delivery_content(tmp_path: Path) -> None:
    pack, artifact = _markdown_pack(tmp_path)
    notion_transport = FakeNotionTransport()
    confluence_transport = FakeConfluenceTransport()
    notion_adapter = NotionPageAdapter(
        NotionConfig(token="ntn", parent_page_id="page-1"),
        transport=notion_transport,
    )
    confluence_adapter = ConfluenceAdapter(
        ConfluenceConfig(
            base_url="https://conf.example.com/wiki",
            email="conf@example.com",
            api_token="token",
            space_key="DS",
        ),
        transport=confluence_transport,
    )

    notion_receipt = notion_adapter.send(
        pack=pack,
        artifact=artifact,
        channel=DeliveryChannel.NOTION_PAGE,
    )
    confluence_receipt = confluence_adapter.send(
        pack=pack,
        artifact=artifact,
        channel=DeliveryChannel.CONFLUENCE,
    )

    assert notion_receipt == "https://notion.so/page-1"
    assert notion_transport.last_kwargs is not None
    assert notion_transport.last_kwargs["title"] == "pm_action_memo for TC-2026-001"
    assert "# pm_action_memo for TC-2026-001" in notion_transport.last_kwargs["markdown"]
    assert confluence_receipt == "https://conf.example.com/wiki/spaces/DS/pages/42"
    assert confluence_transport.last_kwargs is not None
    assert "<h1>" in confluence_transport.last_kwargs["html"]
    assert confluence_transport.last_kwargs["space_key"] == "DS"


def test_jira_adapter_creates_issue_and_attaches_rendered_artifact(tmp_path: Path) -> None:
    pack, artifact = _markdown_pack(tmp_path)
    transport = FakeJiraTransport()
    adapter = JiraAdapter(
        JiraConfig(
            base_url="https://jira.example.com",
            email="jira@example.com",
            api_token="token",
            project_key="DS",
        ),
        transport=transport,
    )

    receipt = adapter.send(
        pack=pack,
        artifact=artifact,
        channel=DeliveryChannel.JIRA_TICKET,
    )

    assert receipt == "DS-101"
    assert transport.create_kwargs is not None
    assert transport.create_kwargs["project_key"] == "DS"
    assert transport.attachment_kwargs is not None
    assert transport.attachment_kwargs["issue_key"] == "DS-101"
    assert transport.attachment_kwargs["file_path"].name == "memo.md"


def test_compliance_adapter_submits_richer_signed_pdf_payload(tmp_path: Path) -> None:
    pack, artifact = _pdf_pack(tmp_path)
    transport = FakeComplianceTransport()
    adapter = ComplianceAdapter(
        ComplianceConfig(endpoint_url="https://compliance.example.com/ingest"),
        transport=transport,
    )

    receipt = adapter.send(
        pack=pack,
        artifact=artifact,
        channel=DeliveryChannel.COMPLIANCE_SYSTEM,
    )

    assert receipt == "cmp-1"
    assert transport.last_kwargs is not None
    payload = transport.last_kwargs["payload"]
    assert payload["signature"] == "signed-blob"
    assert payload["file_name"] == "audit.pdf"
    assert base64.b64decode(payload["content_base64"]) == b"%PDF-1.7\n"
    assert payload["artifact_format"] == "pdf"
    assert payload["dispatch_mode"] == "auto_with_signature"
    assert payload["read_only"] is True
    assert payload["policy"]["speculative_claims"] == "forbidden"
    assert payload["policy"]["structure"] == ["data_provenance", "policy_compliance"]
    assert payload["audit_context"]["approval_chain"] == ["risk_review", "owner_signoff"]
    assert payload["audit_context"]["policy_compliance"] == [
        "retention label verified",
        "warehouse access approved",
    ]
    assert payload["audit_context"]["lineage"] == ["lineage-1", "lineage-2"]
    assert payload["audit_context"]["access_log"] == ["etl-run-1", "audit-log-2"]
    assert payload["file"]["name"] == "audit.pdf"
    assert payload["file"]["mime_type"] == "application/pdf"
    assert payload["file"]["size_bytes"] == len(b"%PDF-1.7\n")
    assert payload["file"]["sha256"]


def test_compliance_adapter_rejects_unsigned_or_non_auditor_payloads(tmp_path: Path) -> None:
    pack, artifact = _pdf_pack(tmp_path)
    adapter = ComplianceAdapter(ComplianceConfig(endpoint_url="https://compliance.example.com/ingest"))

    unsigned_pack = pack.model_copy(update={"signed_by": None})
    non_auditor = artifact.model_copy(update={"audience": AudienceKind.EXECUTIVE})

    with pytest.raises(ValueError, match="signed_by"):
        adapter.send(
            pack=unsigned_pack,
            artifact=artifact,
            channel=DeliveryChannel.COMPLIANCE_SYSTEM,
        )

    with pytest.raises(ValueError, match="auditor"):
        adapter.send(
            pack=pack,
            artifact=non_auditor,
            channel=DeliveryChannel.COMPLIANCE_SYSTEM,
        )


def _markdown_pack(tmp_path: Path) -> tuple[DeliveryPack, DeliveryArtifact]:
    path = tmp_path / "memo.md"
    path.write_text("# Summary\n\n- Revenue risk increased.\n", encoding="utf-8")
    artifact = DeliveryArtifact(
        artifact_id="art-pm",
        type=ArtifactType.PM_ACTION_MEMO,
        audience=AudienceKind.PM,
        format=ArtifactFormat.MARKDOWN,
        content_policy=ContentPolicy(
            structure=["summary", "next_actions"],
            tone="actionable",
        ),
        template_ref="tpl/pm_memo/v2",
        delivery_channel=[
            DeliveryChannel.EMAIL,
            DeliveryChannel.SLACK_CHANNEL,
            DeliveryChannel.SLACK_DM,
            DeliveryChannel.NOTION_PAGE,
            DeliveryChannel.CONFLUENCE,
            DeliveryChannel.JIRA_TICKET,
        ],
        dispatch_mode=DeliveryDispatchMode.MANUAL_REVIEW,
        rendered_uri=str(path),
    )
    pack = DeliveryPack(
        pack_id="DP-1",
        task_id="TC-2026-001",
        generated_at=datetime(2026, 4, 16, tzinfo=UTC),
        artifacts=[artifact],
        global_context={"slack_thread_ts": "111.22"},
        signed_by="ds-agent@test",
        signature="signed-blob",
    )
    return pack, artifact


def _pdf_pack(tmp_path: Path) -> tuple[DeliveryPack, DeliveryArtifact]:
    path = tmp_path / "audit.pdf"
    path.write_bytes(b"%PDF-1.7\n")
    artifact = DeliveryArtifact(
        artifact_id="art-audit",
        type=ArtifactType.AUDIT_TRAIL,
        audience=AudienceKind.AUDITOR,
        format=ArtifactFormat.PDF,
        content_policy=ContentPolicy(
            structure=["data_provenance", "policy_compliance"],
            tone="neutral",
            speculative_claims="forbidden",
        ),
        template_ref="tpl/audit/v1",
        delivery_channel=[DeliveryChannel.COMPLIANCE_SYSTEM],
        dispatch_mode=DeliveryDispatchMode.AUTO_WITH_SIGNATURE,
        rendered_uri=str(path),
    )
    pack = DeliveryPack(
        pack_id="DP-2",
        task_id="TC-2026-002",
        generated_at=datetime(2026, 4, 16, tzinfo=UTC),
        artifacts=[artifact],
        global_context={
            "compliance_case_id": "CASE-2026-001",
            "approval_chain": "risk_review, owner_signoff",
            "policy_compliance": '["retention label verified", "warehouse access approved"]',
            "lineage": "lineage-1,lineage-2",
            "access_log": '["etl-run-1", "audit-log-2"]',
        },
        signed_by="auditor@test",
        signature="signed-blob",
    )
    return pack, artifact
