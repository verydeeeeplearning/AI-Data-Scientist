from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from rich.console import Console

from ds_agent.application.dtos.task_contract import BuildDeliveryPackDTO, TaskContractDraftDTO
from ds_agent.cli.delivery_cli import run_delivery_command
from ds_agent.config.schema import AgentConfig, DSAgentConfig, ProviderConfig
from ds_agent.domain.entities.messages import LLMResponse, Usage
from ds_agent.domain.entities.provider_models import ModelInfo
from ds_agent.infrastructure.task_contract_container import build_task_contract_container


@dataclass
class FakeProvider:
    response_text: str
    model_id: str = "gpt-5.4"
    provider_name: str = "openai"
    last_messages: list | None = None
    last_kwargs: dict[str, object] | None = None

    async def chat(self, messages, **kwargs):
        self.last_messages = messages
        self.last_kwargs = kwargs
        return LLMResponse(content=self.response_text, model=self.model_id, usage=Usage())

    async def count_tokens(self, messages) -> int:
        return 0

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            model_id=self.model_id,
            provider=self.provider_name,
            display_name="CLI Test Model",
            max_context_tokens=128_000,
            max_output_tokens=4096,
        )


def _create_contract(workspace_dir: str, session_id: str = "delivery-session-1") -> str:
    return _create_contract_with_deliverables(
        workspace_dir,
        session_id=session_id,
        required_deliverables=[
            {"type": "exec_brief", "audience": "executive", "format": "pptx"}
        ],
    )


def _create_contract_with_deliverables(
    workspace_dir: str,
    *,
    session_id: str = "delivery-session-1",
    required_deliverables: list[dict[str, str]],
) -> str:
    container = build_task_contract_container(workspace_dir)
    result = container.create.execute(
        TaskContractDraftDTO(
            session_id=session_id,
            contract_type="churn_analysis",
            business_goal="Reduce churn by one point",
            goal_brief={
                "business_question": "What drives churn?",
                "ds_problem_statement": "Binary classification",
                "comparison_baseline": "last quarter",
                "decision_to_make": "prioritize interventions",
                "expected_effort": "M",
            },
            required_deliverables=required_deliverables,
        )
    )
    return str(result["task_id"])


def test_delivery_build_renders_pack_summary(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    task_id = _create_contract(workspace_dir)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=120)

    exit_code = run_delivery_command(
        [
            "build",
            task_id,
            "--audience",
            "executive",
            "--source-analysis-id",
            "FA-CLI-1",
            "--context",
            "project=churn_q2",
        ],
        console=console,
        workspace_dir=workspace_dir,
    )

    bundle = build_task_contract_container(workspace_dir).store.get_bundle(task_id)
    assert exit_code == 0
    assert bundle is not None
    assert bundle.delivery_pack is not None
    assert bundle.delivery_pack.source_analysis_id == "FA-CLI-1"
    assert bundle.delivery_pack.global_context["project"] == "churn_q2"
    rendered = out.getvalue()
    assert "Delivery pack:" in rendered
    assert "Audiences: executive" in rendered


def test_delivery_render_and_dispatch_round_trip(tmp_path: Path) -> None:
    workspace_dir = str(tmp_path / "workspace")
    task_id = _create_contract_with_deliverables(
        workspace_dir,
        required_deliverables=[
            {"type": "pm_action_memo", "audience": "pm", "format": "markdown"}
        ],
    )
    container = build_task_contract_container(workspace_dir)
    build_result = container.build_delivery_pack.execute(BuildDeliveryPackDTO(task_id=task_id))
    artifact_id = build_result["artifact_ids"][0]
    analysis_path = tmp_path / "analysis.json"
    analysis_path.write_text(
        json.dumps(
            {
                "summary": "Churn increased in premium cohorts.",
                "recommendation": "Launch a retention pilot.",
            }
        ),
        encoding="utf-8",
    )

    render_out = StringIO()
    render_console = Console(file=render_out, force_terminal=False, width=120)
    render_exit = run_delivery_command(
        [
            "render",
            task_id,
            artifact_id,
            "--analysis-file",
            str(analysis_path),
            "--output-dir",
            str(tmp_path / "artifacts"),
        ],
        console=render_console,
        workspace_dir=workspace_dir,
    )

    dispatch_out = StringIO()
    dispatch_console = Console(file=dispatch_out, force_terminal=False, width=120)
    dispatch_exit = run_delivery_command(
        [
            "dispatch",
            task_id,
            "--artifact-id",
            artifact_id,
            "--approve-manual-review",
        ],
        console=dispatch_console,
        workspace_dir=workspace_dir,
    )

    log_out = StringIO()
    log_console = Console(file=log_out, force_terminal=False, width=120)
    log_exit = run_delivery_command(
        [
            "log",
            task_id,
            "--artifact-id",
            artifact_id,
            "--limit",
            "10",
        ],
        console=log_console,
        workspace_dir=workspace_dir,
    )

    bundle = build_task_contract_container(workspace_dir).store.get_bundle(task_id)
    assert render_exit == 0
    assert dispatch_exit == 0
    assert log_exit == 0
    assert bundle is not None
    assert bundle.delivery_pack is not None
    assert bundle.delivery_pack.status == "dispatched"
    assert Path(bundle.delivery_pack.artifacts[0].rendered_uri or "").exists()
    assert "Rendered artifact:" in render_out.getvalue()
    assert "Status: dispatched | Pack: dispatched" in dispatch_out.getvalue()
    assert "Delivery log:" in log_out.getvalue()
    assert "Summary: pack=" in log_out.getvalue()
    assert "Counts: sent=2 blocked=0 failed=0 duplicates=0 dry_runs=0" in log_out.getvalue()
    assert artifact_id in log_out.getvalue()


def test_delivery_render_supports_provider_backed_opt_in(tmp_path: Path) -> None:
    workspace_dir = str(tmp_path / "workspace-provider")
    task_id = _create_contract_with_deliverables(
        workspace_dir,
        required_deliverables=[
            {"type": "pm_action_memo", "audience": "pm", "format": "markdown"}
        ],
    )
    container = build_task_contract_container(workspace_dir)
    build_result = container.build_delivery_pack.execute(
        BuildDeliveryPackDTO(task_id=task_id, audiences=["pm"])
    )
    artifact_id = build_result["artifact_ids"][0]
    analysis_path = tmp_path / "provider-analysis.json"
    analysis_path.write_text(
        json.dumps(
            {
                "summary": "Premium cohorts drove the churn spike.",
                "recommendation": "Launch a retention pilot.",
            }
        ),
        encoding="utf-8",
    )
    config = DSAgentConfig(
        agent=AgentConfig(workspace_dir=workspace_dir),
        provider=ProviderConfig(default_model="openai/gpt-5.4"),
    )
    token_store = object()
    provider = FakeProvider(
        """
        {
          "blocks": [
            {
              "section": "summary",
              "title": "Summary",
              "body_md": "Premium cohorts drove the churn spike.",
              "citations": ["lineage-1"]
            }
          ],
          "overall_tone": "actionable",
          "flagged_claims": []
        }
        """
    )

    render_out = StringIO()
    render_console = Console(file=render_out, force_terminal=False, width=120)
    with (
        patch(
            "ds_agent.cli.delivery_cli.create_auth_profile_store",
            return_value=token_store,
        ),
        patch(
            "ds_agent.cli.delivery_cli.create_provider_router",
            return_value=provider,
        ) as mock_router,
    ):
        render_exit = run_delivery_command(
            [
                "render",
                task_id,
                artifact_id,
                "--analysis-file",
                str(analysis_path),
                "--output-dir",
                str(tmp_path / "provider-artifacts"),
                "--provider-backed",
            ],
            console=render_console,
            workspace_dir=workspace_dir,
            config=config,
        )

    assert render_exit == 0
    mock_router.assert_called_once_with(
        "openai/gpt-5.4",
        config,
        token_store=token_store,
    )
    assert provider.last_kwargs is not None
    assert provider.last_kwargs["response_format"] == {"type": "json_object"}
    rendered = render_out.getvalue()
    assert "Renderer: provider-backed | Model: openai/gpt-5.4" in rendered
