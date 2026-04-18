from __future__ import annotations

from rich.console import Console

from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.evaluation.infrastructure.cli.eval_cli import run_eval_command
from ds_agent.evaluation.infrastructure.persistence.jsonl_human_rubric_store import (
    JsonlHumanRubricStore,
)
from ds_agent.runtime.organization_store import JsonOrganizationStore
from ds_agent.runtime.transcript_store import JsonTranscriptStore


def test_eval_cli_ingest_human_scores_and_persists_rubric(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    session_id = "session-human"
    run_id = "run-human"

    transcript_store = JsonTranscriptStore(workspace_dir=workspace_dir)
    transcript_store.replace_messages(
        session_id,
        [
            ChatMessage(
                role=Role.USER,
                content="Review premium churn risk and recommend next steps.",
            ),
            ChatMessage(
                role=Role.ASSISTANT,
                content=(
                    "Core finding: premium churn is concentrated in the newest cohort. "
                    "Confidence: medium. "
                    "Limitations: no uplift experiment yet. "
                    "Recommended action: launch a focused save offer pilot."
                ),
            ),
        ],
    )
    JsonOrganizationStore(workspace_dir=workspace_dir).record_usage(
        actor_id="local-user",
        provider="anthropic",
        cost_usd=0.6,
        model="anthropic/claude-sonnet-4-6",
        session_id=session_id,
        run_id=run_id,
    )

    console = Console(record=True, width=140)
    exit_code = run_eval_command(
        [
            "ingest-human",
            "--session-id",
            session_id,
            "--run-id",
            run_id,
            "--reviewer-id",
            "reviewer-1",
            "--dimension",
            "scoping_accuracy=0.35",
            "--dimension",
            "operator_satisfaction=0.90",
            "--comment",
            "Scope was weaker than the summary quality.",
            "--output",
            "json",
        ],
        console=console,
        workspace_dir=workspace_dir,
    )

    output = console.export_text()
    rubric_store = JsonlHumanRubricStore.for_workspace(workspace_dir)
    latest = rubric_store.latest(session_id=session_id, run_id=run_id)

    assert exit_code == 0
    assert latest is not None
    assert latest.rubric.reviewer_id == "reviewer-1"
    assert latest.rubric.dimensions["scoping_accuracy"] == 0.35
    assert '"humanRubricReviewerId": "reviewer-1"' in output
    assert '"weighted_score":' in output
