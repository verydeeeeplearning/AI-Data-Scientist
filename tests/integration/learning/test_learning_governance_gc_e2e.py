from __future__ import annotations

import importlib
import json
import shutil
import sys
from pathlib import Path

import pytest

from ds_agent.application.learning.harness_warning_ingestor import HarnessWarningIngestor
from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore
from ds_agent.self_improve.promotion_candidates import JsonPromotionCandidateStore
from ds_agent.tools.path_utils import get_active_workspace, set_active_workspace
from ds_agent.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_warning_ingestion_gc_and_report_register_failure_taxonomy_candidate(
    monkeypatch,
) -> None:
    ToolRegistry.reset()
    monkeypatch.setenv("DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1", "1")

    module_name = "ds_agent.tools.learning_tools"
    if module_name in sys.modules:
        module = importlib.reload(sys.modules[module_name])
    else:
        module = importlib.import_module(module_name)

    previous_workspace = get_active_workspace()
    workspace = (Path.cwd() / "phase5_gc_test_workspace").resolve()
    store: SqliteLearningStore | None = None

    try:
        shutil.rmtree(workspace, ignore_errors=True)
        workspace.mkdir(parents=True, exist_ok=True)
        set_active_workspace(workspace)
        store = SqliteLearningStore.for_workspace(str(workspace))
        module._learning_store = store
        ingestor = HarnessWarningIngestor(store)

        for index in range(3):
            ingestor.ingest(
                {
                    "type": "leakage",
                    "severity": "high",
                    "message": "Data leakage pattern detected",
                },
                session_id=f"session-{index}",
                run_id=f"run-{index}",
                surface="ws",
            )

        gc_payload = json.loads(
            await ToolRegistry.dispatch(
                "run_gc_loop",
                {"promotion_threshold": 3, "limit": 50},
            )
        )
        report_payload = json.loads(await ToolRegistry.dispatch("get_gc_report", {}))

        assert gc_payload["ok"] is True
        assert gc_payload["total_items"] == 1
        assert gc_payload["total_recurrences"] == 3
        assert gc_payload["promotion_candidate_classes"] == ["leakage"]
        assert gc_payload["skill_candidates"] == [
            {
                "failure_class": "leakage",
                "candidate_id": "failure-taxonomy-leakage",
                "status": "pending_promotion",
                "pending_path": gc_payload["skill_candidates"][0]["pending_path"],
                "reused_existing": False,
            }
        ]

        items = store.list_items(limit=10)
        assert len(items) == 1
        assert items[0].metadata["failureTaxonomyClass"] == "leakage"
        assert items[0].metadata["failureTaxonomyPromotionCandidate"] is True
        assert items[0].metadata["failureTaxonomyCandidateId"] == "failure-taxonomy-leakage"

        candidate_path = Path(gc_payload["skill_candidates"][0]["pending_path"])
        assert candidate_path.exists()
        candidate_text = candidate_path.read_text(encoding="utf-8")
        assert "Guardrail Draft" in candidate_text

        assert report_payload["ok"] is True
        assert "Registered Skill Candidates" in report_payload["content"]
        assert "failure-taxonomy-leakage" in report_payload["content"]
    finally:
        module._learning_store = None
        if store is not None:
            store._conn.close()
        set_active_workspace(previous_workspace)
        shutil.rmtree(workspace, ignore_errors=True)


@pytest.mark.asyncio
async def test_finalize_learning_candidate_promotion_promotes_gc_candidate(
    monkeypatch,
) -> None:
    ToolRegistry.reset()
    monkeypatch.setenv("DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1", "1")

    module_name = "ds_agent.tools.learning_tools"
    if module_name in sys.modules:
        module = importlib.reload(sys.modules[module_name])
    else:
        module = importlib.import_module(module_name)

    previous_workspace = get_active_workspace()
    workspace = (Path.cwd() / "phase5_gc_test_workspace").resolve()
    active_custom_dir = workspace / "active_custom"
    store: SqliteLearningStore | None = None

    try:
        shutil.rmtree(workspace, ignore_errors=True)
        workspace.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("DS_AGENT_ACTIVE_CUSTOM_SKILLS_DIR", str(active_custom_dir))
        set_active_workspace(workspace)
        store = SqliteLearningStore.for_workspace(str(workspace))
        module._learning_store = store
        ingestor = HarnessWarningIngestor(store)

        for index in range(3):
            ingestor.ingest(
                {
                    "type": "leakage",
                    "severity": "high",
                    "message": "Data leakage pattern detected",
                },
                session_id=f"session-{index}",
                run_id=f"run-{index}",
                surface="ws",
            )

        gc_payload = json.loads(
            await ToolRegistry.dispatch(
                "run_gc_loop",
                {"promotion_threshold": 3, "limit": 50},
            )
        )
        finalize_payload = json.loads(
            await ToolRegistry.dispatch(
                "finalize_learning_candidate_promotion",
                {
                    "candidate_id": "failure-taxonomy-leakage",
                    "candidate_score": 0.82,
                    "baseline_score": 0.80,
                    "passed_tasks": 1,
                    "total_tasks": 1,
                },
            )
        )

        assert gc_payload["ok"] is True
        assert finalize_payload["ok"] is True
        assert finalize_payload["status"] == "promoted"
        assert finalize_payload["promoted"] is True
        assert finalize_payload["promoted_path"] is not None

        promoted_path = Path(finalize_payload["promoted_path"])
        assert promoted_path.exists()
        assert promoted_path.parent == active_custom_dir

        candidate_store = JsonPromotionCandidateStore.for_workspace(str(workspace))
        candidate = candidate_store.get("failure-taxonomy-leakage")
        assert candidate is not None
        assert candidate.status == "promoted"
        assert candidate.promoted_path == str(promoted_path)
    finally:
        module._learning_store = None
        if store is not None:
            store._conn.close()
        set_active_workspace(previous_workspace)
        shutil.rmtree(workspace, ignore_errors=True)
