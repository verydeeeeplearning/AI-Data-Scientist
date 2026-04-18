from io import StringIO

from rich.console import Console

from ds_agent.cli.certification_cli import run_certification_command
from ds_agent.domain.entities.certification import AutonomyRunStat
from ds_agent.infrastructure.persistence.certification_store import SqliteCertificationStore


def _seed_ready_stats(workspace_dir: str) -> None:
    store = SqliteCertificationStore.for_workspace(workspace_dir)
    for index in range(10):
        store.record_run_stat(
            AutonomyRunStat(
                mission_name="weekly-kpi-triage",
                mission_version=1,
                run_id=f"run-{index}",
                authority="shadow",
                audience="senior_staff",
                started_at="2026-04-01T00:00:00Z",
                ended_at="2026-04-01T00:10:00Z",
                outcome="success",
                verifier_score=0.90,
                rollback_rehearsal=index == 0,
            )
        )


def test_certification_status_renders_summary(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    _seed_ready_stats(workspace_dir)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=120)

    exit_code = run_certification_command(
        ["status", "weekly-kpi-triage"],
        console=console,
        workspace_dir=workspace_dir,
    )

    assert exit_code == 0
    output = out.getvalue()
    assert "weekly-kpi-triage v1" in output
    assert "shadow_runs=10" in output


def test_certification_submit_persists_autopilot_record(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    _seed_ready_stats(workspace_dir)
    out = StringIO()
    console = Console(file=out, force_terminal=False, width=120)

    exit_code = run_certification_command(
        [
            "submit",
            "weekly-kpi-triage",
            "--to",
            "autopilot",
            "--approved-by",
            "owner-park",
            "--approved-by",
            "owner-cho",
        ],
        console=console,
        workspace_dir=workspace_dir,
    )

    assert exit_code == 0
    assert "certified" in out.getvalue()
    store = SqliteCertificationStore.for_workspace(workspace_dir)
    assert store.is_certified("weekly-kpi-triage", "autopilot", mission_version=1) is True
