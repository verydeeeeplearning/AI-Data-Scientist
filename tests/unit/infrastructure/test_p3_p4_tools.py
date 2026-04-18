"""Tests for new governance and artifact tools."""

from __future__ import annotations

import json

import pytest

from ds_agent.application.services.lineage_capture_service import (
    LineageCaptureService,
    set_lineage_service,
)
from ds_agent.application.services.policy_evaluator import PolicyEvaluator, set_policy_evaluator
from ds_agent.domain.entities.approval_policy import ApprovalPolicy, PolicyDecisionType, PolicyRule
from ds_agent.infrastructure.persistence.lineage_store import SqliteLineageStore


class TestGovernanceTools:
    @pytest.mark.asyncio
    async def test_policy_check_returns_decision(self, tmp_path):
        from ds_agent.tools.governance_tools import policy_check

        evaluator = PolicyEvaluator(
            policy=ApprovalPolicy(
                rules=[
                    PolicyRule(
                        action_pattern="file_write",
                        environment="prod",
                        decision=PolicyDecisionType.APPROVAL,
                    )
                ]
            ),
            storage_path=str(tmp_path / "approvals.json"),
        )
        set_policy_evaluator(evaluator)

        parsed = json.loads(
            await policy_check("file_write", data_sensitivity="internal", environment="prod")
        )
        assert parsed["decision"] == "approval"

    @pytest.mark.asyncio
    async def test_lineage_capture_traces_record(self, tmp_path):
        from ds_agent.tools.governance_tools import lineage_capture

        service = LineageCaptureService(SqliteLineageStore(str(tmp_path / "lineage.db")))
        dataset = service.capture_dataset("data/train.csv", ["x"], 10, session_id="s1")
        model = service.capture_model(
            hyperparams={"max_depth": 4},
            seed=42,
            env_info={"python": "3.11"},
            feature_id=dataset.id,
            session_id="s1",
        )
        set_lineage_service(service)

        parsed = json.loads(await lineage_capture("trace", record_id=model.id))
        assert [record["type"] for record in parsed] == ["dataset", "model"]


class TestArtifactTools:
    @pytest.mark.asyncio
    async def test_notebook_generate_writes_ipynb(self, tmp_path):
        from ds_agent.tools.artifact_tools import notebook_generate

        output_path = tmp_path / "analysis.ipynb"
        parsed = json.loads(
            await notebook_generate(
                ["print(1)"], output_path=str(output_path), descriptions=["# Title"]
            )
        )
        assert parsed["output_path"] == str(output_path)
        assert output_path.exists()

    @pytest.mark.asyncio
    async def test_dashboard_spec_writes_json(self, tmp_path):
        from ds_agent.tools.artifact_tools import dashboard_spec

        output_path = tmp_path / "dashboard.json"
        parsed = json.loads(
            await dashboard_spec(
                metrics=[{"name": "revenue", "sql": "sum(revenue)", "type": "number"}],
                output_path=str(output_path),
            )
        )
        assert parsed["format"] == "json"
        assert output_path.exists()


class TestIntegrationTools:
    @pytest.mark.asyncio
    async def test_send_to_slack_requires_configuration(self, monkeypatch):
        from ds_agent.tools.integration_tools import send_to_slack

        monkeypatch.delenv("DS_AGENT_SLACK_WEBHOOK_URL", raising=False)
        parsed = json.loads(await send_to_slack("hello"))
        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_create_jira_ticket_requires_configuration(self, monkeypatch):
        from ds_agent.tools.integration_tools import create_jira_ticket

        monkeypatch.delenv("DS_AGENT_JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("DS_AGENT_JIRA_EMAIL", raising=False)
        monkeypatch.delenv("DS_AGENT_JIRA_API_TOKEN", raising=False)
        parsed = json.loads(await create_jira_ticket("Summary", "Desc", "DS"))
        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_create_git_pr_requires_configuration(self, monkeypatch):
        from ds_agent.tools.integration_tools import create_git_pr

        monkeypatch.delenv("DS_AGENT_GITHUB_REPO", raising=False)
        monkeypatch.delenv("DS_AGENT_GITHUB_TOKEN", raising=False)
        parsed = json.loads(await create_git_pr("Title", "Body", "feature/branch"))
        assert "error" in parsed
