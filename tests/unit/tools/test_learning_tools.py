import importlib
import json
import sys
from datetime import UTC, datetime

import pytest

from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore
from ds_agent.tools.registry import ToolRegistry


@pytest.fixture
def learning_tool_module(tmp_path, monkeypatch):
    ToolRegistry.reset()
    monkeypatch.setenv("DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1", "1")

    module_name = "ds_agent.tools.learning_tools"
    if module_name in sys.modules:
        module = importlib.reload(sys.modules[module_name])
    else:
        module = importlib.import_module(module_name)

    module._learning_store = SqliteLearningStore(tmp_path / "learning.db")
    yield module
    module._learning_store = None


def _seed_warning_item(store: SqliteLearningStore) -> None:
    from ds_agent.domain.learning.learning_item import LearningItem, LearningItemType

    created_at = datetime(2026, 4, 21, 2, 0, tzinfo=UTC)
    store.save_item(
        LearningItem(
            item_id="LI-WARN-1",
            item_type=LearningItemType.PATTERN,
            title="Harness warning: overfitting",
            content="Validation score diverges from train score.\n\nSuggestion: Rebuild the split.",
            signature="sig-warning-1",
            tags=["harness.warning", "overfitting", "severity:high", "surface:daemon"],
            scope="project",
            created_at=created_at,
            updated_at=created_at,
            metadata={
                "warningType": "overfitting",
                "severity": "high",
                "surface": "daemon",
                "recurrenceCount": 4,
                "firstSeenAt": "2026-04-21T00:30:00+00:00",
                "lastSeenAt": "2026-04-21T02:00:00+00:00",
                "surfaces": ["daemon", "ws"],
                "failureTaxonomyClass": "overfitting",
                "failureTaxonomyRecurrenceCount": 4,
                "failureTaxonomyPromotionCandidate": True,
                "rawPayload": {
                    "type": "overfitting",
                    "severity": "high",
                    "message": "Validation score diverges from train score.",
                },
            },
        )
    )


@pytest.mark.asyncio
async def test_list_learning_inbox_tool_includes_metadata(learning_tool_module) -> None:
    _seed_warning_item(learning_tool_module._learning_store)

    payload = json.loads(await ToolRegistry.dispatch("list_learning_inbox", {"status": "all"}))

    assert payload["ok"] is True
    assert payload["count"] == 1
    item = payload["items"][0]
    assert item["created_at"] == "2026-04-21T02:00:00+00:00"
    assert item["metadata"]["recurrenceCount"] == 4
    assert item["metadata"]["failureTaxonomyClass"] == "overfitting"


@pytest.mark.asyncio
async def test_get_learning_item_tool_includes_detail_metadata(learning_tool_module) -> None:
    _seed_warning_item(learning_tool_module._learning_store)

    payload = json.loads(await ToolRegistry.dispatch("get_learning_item", {"item_id": "LI-WARN-1"}))

    assert payload["ok"] is True
    assert payload["updated_at"] == "2026-04-21T02:00:00+00:00"
    assert payload["metadata"]["failureTaxonomyPromotionCandidate"] is True
    assert payload["metadata"]["rawPayload"]["message"] == (
        "Validation score diverges from train score."
    )


@pytest.mark.asyncio
async def test_readonly_learning_governance_tools_work_when_mutation_flag_off(
    learning_tool_module,
    monkeypatch,
    tmp_path,
) -> None:
    from ds_agent.tools.path_utils import set_active_workspace

    _seed_warning_item(learning_tool_module._learning_store)
    report_dir = tmp_path / "Docs" / "operations" / "gc_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "GC_REPORT_2026-04-21_020000.md"
    report_path.write_text("# Failure Taxonomy GC Report\n", encoding="utf-8")

    set_active_workspace(tmp_path)
    monkeypatch.delenv("DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1", raising=False)

    try:
        status_payload = json.loads(
            await ToolRegistry.dispatch("get_learning_governance_status", {})
        )
        report_payload = json.loads(await ToolRegistry.dispatch("get_gc_report", {}))

        assert status_payload["ok"] is True
        assert status_payload["review_enabled"] is False
        assert status_payload["backlog"]["activeWarningItems"] == 1
        assert status_payload["backlog"]["activeWarningRecurrences"] == 4
        assert report_payload["ok"] is True
        assert report_payload["path"].endswith("GC_REPORT_2026-04-21_020000.md")
    finally:
        set_active_workspace(None)
