from __future__ import annotations

from io import StringIO

from rich.console import Console

from ds_agent.application.dtos.task_contract import ReviewVerdictInputDTO, TaskContractDraftDTO
from ds_agent.cli.verdict_cli import run_verdict_command
from ds_agent.domain.entities.review_verdict import ConfidenceBand, Issue
from ds_agent.domain.entities.shadow_comparison import ShadowComparisonItem, ShadowComparisonRecord
from ds_agent.infrastructure.task_contract_container import build_task_contract_container
from ds_agent.infrastructure.verifier_container import build_verifier_container


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


def _record_verdict(workspace_dir: str, task_id: str) -> str:
    contract_container = build_task_contract_container(workspace_dir)
    contract_container.record_review_verdict.execute(
        ReviewVerdictInputDTO(
            task_id=task_id,
            verdict_id="RV-20269001",
            category="orchestrator",
            result="warn",
            reviewer="verifier",
            summary="Need owner sign-off before close.",
            confidence=ConfidenceBand(score=0.65),
            blocking_issues=[Issue(message="Needs owner sign-off", layer="policy", blocking=True)],
            metadata={"judge_mode": "llm"},
        )
    )
    verdict_view = contract_container.get.execute(task_id, include=["review_verdicts"])
    verdict = verdict_view.review_verdicts[0]
    build_verifier_container(workspace_dir).repo.save(verdict)
    return verdict.verdict_id


def _record_shadow_comparison(workspace_dir: str, verdict_id: str, task_id: str) -> str:
    verdict = build_verifier_container(workspace_dir).repo.get(verdict_id)
    assert verdict is not None
    record = ShadowComparisonRecord(
        comparison_id="SC-20269001",
        verdict_id=verdict_id,
        task_id=task_id,
        run_id="run-1",
        session_id="cli-session-1",
        created_at=verdict.created_at,
        items=[
            ShadowComparisonItem(
                comparison_key="baseline_guard",
                legacy_source="baseline_guard_hook",
                verifier_targets=["baseline_comparison"],
                applicable=True,
                legacy_state="clear",
                verifier_state="triggered",
                note="verifier flagged an issue that the legacy hook missed",
            )
        ],
    )
    build_verifier_container(workspace_dir).shadow_repo.save(record)
    return record.comparison_id


def test_verdict_active_renders_latest_contract_verdict(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    task_id = _create_contract(workspace_dir, session_id="cli-session-1")
    _record_verdict(workspace_dir, task_id)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=120)

    exit_code = run_verdict_command(
        [],
        console=console,
        workspace_dir=workspace_dir,
        default_session_id="cli-session-1",
    )

    assert exit_code == 0
    rendered = out.getvalue()
    assert "Review verdict: RV-20269001" in rendered
    assert "judge=llm" in rendered


def test_verdict_show_loads_persisted_verdict_by_id(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    task_id = _create_contract(workspace_dir)
    verdict_id = _record_verdict(workspace_dir, task_id)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=120)

    exit_code = run_verdict_command(
        ["show", verdict_id],
        console=console,
        workspace_dir=workspace_dir,
    )

    assert exit_code == 0
    rendered = out.getvalue()
    assert f"Review verdict: {verdict_id}" in rendered
    assert "Blocking issues:" in rendered


def test_verdict_shadow_active_renders_latest_shadow_comparison(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    task_id = _create_contract(workspace_dir, session_id="cli-session-1")
    verdict_id = _record_verdict(workspace_dir, task_id)
    _record_shadow_comparison(workspace_dir, verdict_id, task_id)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=120)

    exit_code = run_verdict_command(
        ["shadow-active"],
        console=console,
        workspace_dir=workspace_dir,
        default_session_id="cli-session-1",
    )

    assert exit_code == 0
    rendered = out.getvalue()
    assert "Shadow comparison: SC-20269001" in rendered
    assert "baseline_guard" in rendered


def test_verdict_shadow_show_loads_persisted_comparison_by_id(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    task_id = _create_contract(workspace_dir)
    verdict_id = _record_verdict(workspace_dir, task_id)
    comparison_id = _record_shadow_comparison(workspace_dir, verdict_id, task_id)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=120)

    exit_code = run_verdict_command(
        ["shadow-show", comparison_id],
        console=console,
        workspace_dir=workspace_dir,
    )

    assert exit_code == 0
    rendered = out.getvalue()
    assert comparison_id in rendered
    assert "Match:" in rendered
