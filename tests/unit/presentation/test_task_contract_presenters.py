from datetime import UTC, datetime

from ds_agent.application.dtos.task_contract import TaskContractViewDTO
from ds_agent.domain.entities.delivery_pack import DeliveryPack
from ds_agent.domain.entities.review_verdict import ConfidenceBand, Issue, ReviewVerdict
from ds_agent.domain.entities.task_contract import TaskContract
from ds_agent.presentation.task_contract_presenters import (
    render_task_contract_markdown,
    render_task_contract_summary,
)


def _view() -> TaskContractViewDTO:
    now = datetime(2026, 4, 16, tzinfo=UTC)
    contract = TaskContract(
        task_id="TC-2026-001",
        session_id="session-1",
        type="churn_analysis",
        business_goal="Reduce churn",
        required_deliverables=[{"type": "exec_brief", "audience": "executive", "format": "pptx"}],
        created_at=now,
        updated_at=now,
    )
    verdict = ReviewVerdict(
        verdict_id="RV-1",
        task_id=contract.task_id,
        category="orchestrator",
        result="warn",
        reviewer="verifier",
        summary="Review before close",
        created_at=now,
        confidence=ConfidenceBand(score=0.65),
        blocking_issues=[Issue(message="Needs owner sign-off", layer="policy", blocking=True)],
    )
    return TaskContractViewDTO(
        contract=contract,
        review_verdicts=[verdict],
        delivery_pack=DeliveryPack(
            pack_id="DP-1",
            task_id=contract.task_id,
            generated_at=now,
            artifacts=[
                {
                    "artifact_id": "DA-1",
                    "type": "exec_brief",
                    "audience": "executive",
                    "format": "pptx",
                    "content_policy": {
                        "structure": ["situation", "finding", "recommendation"],
                        "chart_count_range": [2, 3],
                        "technical_detail": "minimal",
                        "tone": "decisive",
                    },
                    "template_ref": "tpl/exec_brief/v1",
                    "delivery_channel": ["email"],
                }
            ],
        ),
        dod_summary=["Latest verifier=warn | confidence=medium | blocking_issues=1"],
    )


def test_render_summary_includes_latest_verifier_snapshot() -> None:
    rendered = render_task_contract_summary(_view())

    assert "Latest verifier: warn | confidence=medium | blockers=1" in rendered
    assert "Delivery pack: rendered | 1 artifacts" in rendered


def test_render_markdown_includes_verifier_confidence_and_blockers() -> None:
    rendered = render_task_contract_markdown(_view())

    assert "orchestrator: warn | confidence=medium | blockers=1" in rendered
    assert "## Delivery Pack" in rendered
    assert "- Status: `draft`" in rendered
    assert "exec_brief -> executive (pptx) [dispatch=manual_review]" in rendered
