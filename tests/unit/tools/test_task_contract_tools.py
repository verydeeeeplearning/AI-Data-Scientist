import importlib
import json
import sys
import uuid
from pathlib import Path

import pytest

from ds_agent.infrastructure.persistence.task_contract_store import SqliteTaskContractStore
from ds_agent.infrastructure.task_contract_container import build_task_contract_container
from ds_agent.tools.registry import ToolRegistry


@pytest.fixture
def task_contract_tool_module():
    ToolRegistry.reset()
    module_name = "ds_agent.tools.task_contract_tools"
    if module_name in sys.modules:
        module = importlib.reload(sys.modules[module_name])
    else:
        module = importlib.import_module(module_name)

    base_dir = Path("task_contract_test_artifacts/task-contract-tools")
    base_dir.mkdir(parents=True, exist_ok=True)
    store = SqliteTaskContractStore(base_dir / f"{uuid.uuid4().hex}.db")
    module.set_task_contract_container(build_task_contract_container(store=store))
    return module


@pytest.mark.asyncio
async def test_task_contract_tools_happy_path(task_contract_tool_module, tmp_path: Path) -> None:
    result = await ToolRegistry.dispatch(
        "create_task_contract",
        {
            "session_id": "session-1",
            "contract_type": "churn_analysis",
            "business_goal": "Reduce churn",
            "goal_brief": {
                "business_question": "Why churn?",
                "ds_problem_statement": "Binary classification",
                "comparison_baseline": "last quarter",
                "decision_to_make": "prioritize actions",
                "expected_effort": "M",
            },
            "authority": "delegate",
            "audience": "executive",
            "mission": "weekly-kpi-triage",
            "required_deliverables": [
                {"type": "exec_brief", "audience": "executive", "format": "pptx"},
                {"type": "pm_action_memo", "audience": "pm", "format": "markdown"},
            ],
        },
    )
    payload = json.loads(result)
    assert payload["ok"] is True
    task_id = payload["task_id"]

    built = json.loads(
        await ToolRegistry.dispatch(
            "build_delivery_pack",
            {
                "task_id": task_id,
                "source_analysis_id": "FA-42",
                "signed_by": "ds-agent@test",
            },
        )
    )
    assert built["ok"] is True
    assert built["artifacts"] == 2
    assert built["status"] == "draft"

    listed = json.loads(
        await ToolRegistry.dispatch("list_my_contracts", {"session_id": "session-1"})
    )
    assert listed["ok"] is True
    assert listed["contracts"][0]["task_id"] == task_id

    fetched = json.loads(await ToolRegistry.dispatch("get_task_contract", {"task_id": task_id}))
    assert fetched["ok"] is True
    assert fetched["contract"]["business_goal"] == "Reduce churn"
    assert fetched["contract"]["authority"] == "delegate"
    assert fetched["contract"]["audience"] == "executive"
    assert fetched["contract"]["mission"] == "weekly-kpi-triage"
    assert fetched["delivery_pack"]["source_analysis_id"] == "FA-42"
    assert fetched["delivery_pack"]["status"] == "draft"
    assert len(fetched["delivery_pack"]["artifacts"]) == 2

    pm_artifact = next(
        artifact
        for artifact in fetched["delivery_pack"]["artifacts"]
        if artifact["type"] == "pm_action_memo"
    )
    rendered = json.loads(
        await ToolRegistry.dispatch(
            "render_delivery_artifact",
            {
                "task_id": task_id,
                "artifact_id": pm_artifact["artifact_id"],
                "analysis": {
                    "summary": "Churn increased in premium cohorts.",
                    "next_actions": ["Create retention experiment", "Assign PM owner"],
                },
                "output_dir": str(tmp_path),
            },
        )
    )
    assert rendered["ok"] is True
    assert Path(rendered["output_path"]).exists()
    assert rendered["pack_status"] == "rendered"

    dispatched = json.loads(
        await ToolRegistry.dispatch(
            "dispatch_delivery",
            {
                "task_id": task_id,
                "artifact_ids": [pm_artifact["artifact_id"]],
                "approve_manual_review": True,
            },
        )
    )
    assert dispatched["ok"] is True
    assert dispatched["dispatch_status"] == "dispatched"
    assert dispatched["sent"] == 2

    delivery_log = json.loads(
        await ToolRegistry.dispatch(
            "list_delivery_log",
            {
                "task_id": task_id,
                "artifact_ids": [pm_artifact["artifact_id"]],
                "limit": 10,
            },
        )
    )
    assert delivery_log["ok"] is True
    assert delivery_log["returned"] == 2
    assert delivery_log["summary"]["pack_status"] == "dispatched"
    assert delivery_log["summary"]["sent"] == 2
    assert all(
        entry["artifact_id"] == pm_artifact["artifact_id"] for entry in delivery_log["records"]
    )

    fetched_after_render = json.loads(
        await ToolRegistry.dispatch("get_task_contract", {"task_id": task_id})
    )
    persisted_pm_artifact = next(
        artifact
        for artifact in fetched_after_render["delivery_pack"]["artifacts"]
        if artifact["artifact_id"] == pm_artifact["artifact_id"]
    )
    assert persisted_pm_artifact["rendered_uri"] == rendered["output_path"]
    assert fetched_after_render["delivery_pack"]["status"] == "dispatched"


@pytest.mark.asyncio
async def test_verify_assumption_tool_marks_entry_verified(task_contract_tool_module) -> None:
    created = json.loads(
        await ToolRegistry.dispatch(
            "create_task_contract",
            {
                "session_id": "session-1",
                "contract_type": "churn_analysis",
                "business_goal": "Reduce churn",
                "goal_brief": {
                    "business_question": "Why churn?",
                    "ds_problem_statement": "Binary classification",
                    "comparison_baseline": "last quarter",
                    "decision_to_make": "prioritize actions",
                    "expected_effort": "M",
                },
                "required_deliverables": [
                    {"type": "exec_brief", "audience": "executive", "format": "pptx"}
                ],
            },
        )
    )
    assumed = json.loads(
        await ToolRegistry.dispatch(
            "add_assumption",
            {
                "task_id": created["task_id"],
                "statement": "Churn equals 30 days inactive",
                "rationale": "Team convention",
                "risk_level": "medium",
            },
        )
    )

    verified = json.loads(
        await ToolRegistry.dispatch(
            "verify_assumption",
            {
                "task_id": created["task_id"],
                "entry_id": assumed["entry_id"],
                "expected_version": 2,
                "verification_note": "Matched against the retention playbook.",
            },
        )
    )

    assert verified["ok"] is True
    assert verified["verified"] is True
    fetched = json.loads(
        await ToolRegistry.dispatch("get_task_contract", {"task_id": created["task_id"]})
    )
    assert fetched["assumption_log"]["entries"][0]["verified"] is True


@pytest.mark.asyncio
async def test_update_task_contract_returns_version_conflict(task_contract_tool_module) -> None:
    created = json.loads(
        await ToolRegistry.dispatch(
            "create_task_contract",
            {
                "session_id": "session-1",
                "contract_type": "churn_analysis",
                "business_goal": "Reduce churn",
                "goal_brief": {
                    "business_question": "Why churn?",
                    "ds_problem_statement": "Binary classification",
                    "comparison_baseline": "last quarter",
                    "decision_to_make": "prioritize actions",
                    "expected_effort": "M",
                },
                "required_deliverables": [
                    {"type": "exec_brief", "audience": "executive", "format": "pptx"}
                ],
            },
        )
    )
    result = json.loads(
        await ToolRegistry.dispatch(
            "update_task_contract",
            {
                "task_id": created["task_id"],
                "expected_version": 99,
                "patch": {"decision_owner": "pm@corp"},
            },
        )
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "VERSION_CONFLICT"


@pytest.mark.asyncio
async def test_update_task_contract_returns_review_gate_metadata(task_contract_tool_module) -> None:
    created = json.loads(
        await ToolRegistry.dispatch(
            "create_task_contract",
            {
                "session_id": "session-1",
                "contract_type": "churn_analysis",
                "business_goal": "Reduce churn",
                "goal_brief": {
                    "business_question": "Why churn?",
                    "ds_problem_statement": "Binary classification",
                    "comparison_baseline": "last quarter",
                    "decision_to_make": "prioritize actions",
                    "expected_effort": "M",
                },
                "required_deliverables": [
                    {"type": "exec_brief", "audience": "executive", "format": "pptx"}
                ],
            },
        )
    )

    agreed = json.loads(
        await ToolRegistry.dispatch(
            "update_task_contract",
            {
                "task_id": created["task_id"],
                "expected_version": 1,
                "patch": {},
                "transition_to": "agreed",
            },
        )
    )
    assert agreed["ok"] is True

    in_progress = json.loads(
        await ToolRegistry.dispatch(
            "update_task_contract",
            {
                "task_id": created["task_id"],
                "expected_version": 2,
                "patch": {},
                "transition_to": "in_progress",
            },
        )
    )
    assert in_progress["ok"] is True

    result = json.loads(
        await ToolRegistry.dispatch(
            "update_task_contract",
            {
                "task_id": created["task_id"],
                "expected_version": 3,
                "patch": {},
                "transition_to": "review",
            },
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_TRANSITION"
    assert result["error"]["metadata"]["kind"] == "verifier_review_gate"
    assert result["error"]["metadata"]["failure"] == "missing_review_verdict"
