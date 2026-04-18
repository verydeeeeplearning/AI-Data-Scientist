from __future__ import annotations

from io import StringIO

from rich.console import Console

from ds_agent.application.dtos.task_contract import TaskContractDraftDTO
from ds_agent.application.dtos.work_object import CreateWorkObjectDTO
from ds_agent.cli.work_cli import run_work_command
from ds_agent.domain.entities.work_object import WorkObjectPhase
from ds_agent.infrastructure.task_contract_container import build_task_contract_container
from ds_agent.infrastructure.work_object_container import build_work_object_container


def _create_task_contract(workspace_dir: str, session_id: str = "workflow-session-1") -> str:
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


def _create_work_object(workspace_dir: str, *, session_id: str = "workflow-session-1") -> str:
    task_id = _create_task_contract(workspace_dir, session_id=session_id)
    container = build_work_object_container(workspace_dir)
    view = container.create.execute(
        CreateWorkObjectDTO(
            task_contract_id=task_id,
            title="Retention workflow",
            request_source="slack",
            requestor_id="U123",
            requestor_display="Kim",
            original_text="Investigate churn and open follow-ups.",
            channel="growth-ds",
            tags=["retention"],
        )
    )
    return view.work_object.work_object_id


def test_work_list_renders_existing_items(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    work_object_id = _create_work_object(workspace_dir)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=120)

    exit_code = run_work_command(
        ["list", "--session-id", "workflow-session-1"],
        console=console,
        workspace_dir=workspace_dir,
    )

    assert exit_code == 0
    assert "Work objects:" in out.getvalue()
    assert work_object_id in out.getvalue()


def test_work_show_renders_request_and_timeline(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    work_object_id = _create_work_object(workspace_dir)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=140)

    exit_code = run_work_command(
        ["show", work_object_id],
        console=console,
        workspace_dir=workspace_dir,
    )

    rendered = out.getvalue()
    assert exit_code == 0
    assert f"Work object: {work_object_id}" in rendered
    assert "Original request: Investigate churn and open follow-ups." in rendered
    assert "Timeline:" in rendered


def test_work_intake_renders_metadata_and_external_reference(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    task_id = _create_task_contract(workspace_dir, session_id="jira-session")
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=160)

    exit_code = run_work_command(
        [
            "intake",
            task_id,
            "--title",
            "Pricing escalation",
            "--source",
            "jira",
            "--requestor-id",
            "analyst@example.com",
            "--requestor-display",
            "Analyst Kim",
            "--text",
            "Investigate churn spikes and prepare a follow-up.",
            "--channel",
            "DS-18",
            "--metadata",
            "priority=high",
            "--metadata",
            "segment=enterprise",
            "--external-system",
            "jira",
            "--external-resource-type",
            "issue",
            "--external-resource-id",
            "DS-18",
        ],
        console=console,
        workspace_dir=workspace_dir,
    )

    rendered = out.getvalue()
    assert exit_code == 0
    assert "Source: jira" in rendered
    assert "Requestor: Analyst Kim (analyst@example.com)" in rendered
    assert "priority: high" in rendered
    assert "segment: enterprise" in rendered
    assert "jira:issue:DS-18" in rendered


def test_work_advance_and_timeline_commands_render_updates(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    work_object_id = _create_work_object(workspace_dir)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=160)

    exit_code = run_work_command(
        ["advance", work_object_id, "--to-phase", "executing", "--run-id", "run-17"],
        console=console,
        workspace_dir=workspace_dir,
    )

    rendered = out.getvalue()
    assert exit_code == 0
    assert f"Work object: {work_object_id}" in rendered
    assert f"Phase: {WorkObjectPhase.EXECUTING.value}" in rendered
    assert "Runs: run-17" in rendered

    out = StringIO()
    console = Console(file=out, force_terminal=False, width=160)
    exit_code = run_work_command(
        ["timeline", work_object_id, "--limit", "10"],
        console=console,
        workspace_dir=workspace_dir,
    )

    timeline = out.getvalue()
    assert exit_code == 0
    assert "Timeline:" in timeline
    assert "internal.advance_phase" in timeline
