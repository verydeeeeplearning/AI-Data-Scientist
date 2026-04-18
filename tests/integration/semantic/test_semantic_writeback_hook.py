from __future__ import annotations

import json

import pytest

from ds_agent.agent.hooks import HookContext
from ds_agent.agent.semantic_hooks import SemanticWritebackHook
from ds_agent.infrastructure.semantic_memory_container import build_semantic_memory_container
from ds_agent.tools._semantic_common import set_semantic_memory_container


@pytest.fixture(autouse=True)
def _reset_semantic_container() -> None:
    set_semantic_memory_container(None)
    yield
    set_semantic_memory_container(None)


@pytest.mark.asyncio
async def test_semantic_writeback_hook_persists_verified_query_proposal(tmp_path) -> None:
    container = build_semantic_memory_container(db_path=str(tmp_path / "semantic.sqlite3"))
    set_semantic_memory_container(container)
    events: list[tuple[str, dict]] = []
    ctx = HookContext(
        session_id="session-writeback",
        emit=lambda event, payload: events.append((event, payload)),
    )

    result = await SemanticWritebackHook().post_tool_use(
        "run_verifier",
        {
            "session_id": "session-writeback",
            "artifacts": {
                "semantic_candidates": [
                    {
                        "proposal_type": "verified_query",
                        "parity_confirmed": True,
                        "payload": {
                            "vq_id": "vq-monthly-churn-postgres",
                            "metric_id": "monthly_churn_rate",
                            "dialect": "postgres",
                            "description": "Verified monthly churn query",
                            "sql_template": "SELECT 0.05 AS monthly_churn_rate",
                            "referenced_tables": ["prod.growth.subscription"],
                            "verified_by": "reviewer@corp.example",
                            "last_verified": "2026-04-16",
                            "verification_evidence": "Dashboard parity with Growth board",
                        },
                    }
                ]
            },
        },
        json.dumps(
            {
                "ok": True,
                "artifact_ref": "verdict:RV-1",
                "payload": {
                    "verdict_id": "RV-1",
                    "result": "pass",
                    "run_id": "TC-1:session-writeback",
                    "confidence": {"score": 0.9, "grade": "high"},
                    "blocking_issues": [],
                },
            },
            ensure_ascii=False,
        ),
        False,
        ctx,
    )

    pending = container.proposals.list_pending(limit=10)
    payload = json.loads(result.modified_result or "{}")
    created_events = [event for event in events if event[0] == "semantic.proposal.created"]

    assert len(pending) == 1
    assert pending[0].proposal_type.value == "verified_query"
    assert pending[0].target_id == "monthly_churn_rate"
    assert payload["semantic_writeback"][0]["proposal_id"] == pending[0].proposal_id
    assert created_events
