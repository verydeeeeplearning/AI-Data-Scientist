"""Tests for artifact engines, audience adaptation, and reporting clients."""

from __future__ import annotations

import json

from ds_agent.application.services.artifact_generator import ArtifactGenerator
from ds_agent.domain.value_objects.artifact import ArtifactSpec, ArtifactType
from ds_agent.infrastructure.artifact.dashboard_engine import DashboardSpecEngine
from ds_agent.infrastructure.artifact.notebook_engine import NotebookEngine
from ds_agent.infrastructure.external.git_client import GitClient
from ds_agent.infrastructure.external.jira_client import JiraClient
from ds_agent.infrastructure.external.slack_client import SlackClient


class TestNotebookEngine:
    def test_generates_valid_notebook_structure(self, tmp_path):
        engine = NotebookEngine()
        notebook = engine.write(
            str(tmp_path / "analysis.ipynb"),
            markdown_blocks=["# Title", "Some explanation"],
            code_blocks=["print(1)", "print(2)"],
            output_blocks=["1\n", "2\n"],
        )

        assert notebook["nbformat"] == 4
        assert len(notebook["cells"]) == 4
        on_disk = json.loads((tmp_path / "analysis.ipynb").read_text(encoding="utf-8"))
        assert on_disk["cells"][0]["cell_type"] == "markdown"


class TestArtifactGenerator:
    def test_generates_executive_memo_and_sql_artifact(self):
        generator = ArtifactGenerator()
        memo = generator.generate(
            ArtifactSpec(artifact_type=ArtifactType.MEMO),
            {
                "summary": "Revenue is up.",
                "key_findings": ["Retention improved 5%"],
                "recommendations": ["Roll out segment experiment"],
                "risks": ["Attribution may drift"],
                "next_steps": ["Validate next month"],
            },
        )
        sql = generator.generate(
            ArtifactSpec(artifact_type=ArtifactType.SQL),
            {
                "sql": "select * from users;",
                "description": "User base extract",
                "schema_yml": "version: 2",
                "tests": ["not_null: user_id"],
            },
        )
        assert "## Summary" in memo.content
        assert "-- SQL Artifact" in sql.content
        assert "not_null: user_id" in sql.content


class TestDashboardEngine:
    def test_generates_json_and_yaml_specs(self):
        engine = DashboardSpecEngine()
        metrics = [{"name": "revenue", "sql": "sum(revenue)", "type": "number"}]

        json_spec = engine.build(metrics=metrics, output_format="json")
        yaml_spec = engine.build(metrics=metrics, output_format="yaml")

        assert '"name": "revenue"' in json_spec
        assert "metrics:" in yaml_spec
        assert "name: revenue" in yaml_spec


class TestExternalClientPayloads:
    def test_slack_payload_builder(self):
        payload = SlackClient.build_payload("hello", blocks=[{"type": "section"}])
        assert payload["text"] == "hello"
        assert payload["blocks"][0]["type"] == "section"

    def test_jira_payload_builder(self):
        payload = JiraClient.build_issue_payload(
            project="DS",
            summary="Investigate drift",
            description="Need follow-up",
            issue_type="Task",
            labels=["ml", "drift"],
        )
        assert payload["fields"]["project"]["key"] == "DS"
        assert payload["fields"]["labels"] == ["ml", "drift"]

    def test_git_pr_payload_builder(self):
        payload = GitClient.build_pr_payload(
            title="Model update",
            body="Details",
            head="feature/model-update",
            base="main",
        )
        assert payload["head"] == "feature/model-update"
