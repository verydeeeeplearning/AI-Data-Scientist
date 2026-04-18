from __future__ import annotations

from io import StringIO

from rich.console import Console

from ds_agent.application.dtos.task_contract import TaskContractDraftDTO
from ds_agent.cli.task_contract_cli import run_contract_command
from ds_agent.infrastructure.task_contract_container import build_task_contract_container


def _create_contract(workspace_dir: str, session_id: str = "session-1") -> str:
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
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"}
            ],
        )
    )
    return str(result["task_id"])


def test_contract_list_renders_existing_contract(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    task_id = _create_contract(workspace_dir)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=120)

    exit_code = run_contract_command(
        ["list"],
        console=console,
        workspace_dir=workspace_dir,
    )

    assert exit_code == 0
    assert task_id in out.getvalue()
    assert "Task contracts:" in out.getvalue()


def test_contract_active_uses_default_session_id(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    task_id = _create_contract(workspace_dir, session_id="cli-session-1")
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=120)

    exit_code = run_contract_command(
        [],
        console=console,
        workspace_dir=workspace_dir,
        default_session_id="cli-session-1",
    )

    assert exit_code == 0
    assert task_id in out.getvalue()
    assert "Business goal: Reduce churn by one point" in out.getvalue()


def test_contract_export_json_prints_payload(tmp_path, capsys) -> None:
    workspace_dir = str(tmp_path)
    task_id = _create_contract(workspace_dir)
    console = Console(file=StringIO(), force_terminal=False, width=120)

    exit_code = run_contract_command(
        ["export", task_id, "--format", "json"],
        console=console,
        workspace_dir=workspace_dir,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert task_id in captured.out
    assert '"contract"' in captured.out
