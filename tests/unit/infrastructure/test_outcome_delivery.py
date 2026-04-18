"""Tests for ds_agent.runtime.outcome_delivery."""

from __future__ import annotations

from ds_agent.runtime.delivery_policy_store import JsonDeliveryPolicyStore
from ds_agent.runtime.outcome_delivery import select_outcome_deliverables


class TestOutcomeDelivery:
    def test_failed_run_returns_summary(self, tmp_path) -> None:
        store = JsonDeliveryPolicyStore(tmp_path)
        items = select_outcome_deliverables(
            run_status="failed",
            run_message="analyze data",
            result_preview=None,
            error="division by zero",
            project_id="p1",
            project_files=[],
            policy_store=store,
        )
        assert len(items) == 1
        assert items[0].kind == "summary"
        assert "division by zero" in items[0].text

    def test_succeeded_run_with_png(self, tmp_path) -> None:
        store = JsonDeliveryPolicyStore(tmp_path)
        plot = tmp_path / "chart.png"
        plot.write_bytes(b"\x89PNG")

        items = select_outcome_deliverables(
            run_status="succeeded",
            run_message="EDA complete",
            result_preview="Generated 3 charts",
            error=None,
            project_id="p1",
            project_files=[{"path": "chart.png", "full_path": str(plot)}],
            policy_store=store,
        )
        assert any(i.kind == "summary" for i in items)
        assert any(i.kind == "file" for i in items)

    def test_blocked_extension_not_sent(self, tmp_path) -> None:
        store = JsonDeliveryPolicyStore(tmp_path)
        model = tmp_path / "model.pkl"
        model.write_bytes(b"\x80")

        items = select_outcome_deliverables(
            run_status="succeeded",
            run_message="Training done",
            result_preview=None,
            error=None,
            project_id="p1",
            project_files=[{"path": "model.pkl", "full_path": str(model)}],
            policy_store=store,
        )
        assert not any(i.kind == "file" for i in items)
        assert any(i.kind == "hint" for i in items)

    def test_max_artifacts_capped(self, tmp_path) -> None:
        store = JsonDeliveryPolicyStore(tmp_path)
        files = []
        for i in range(6):
            f = tmp_path / f"chart_{i}.png"
            f.write_bytes(b"\x89PNG")
            files.append({"path": f"chart_{i}.png", "full_path": str(f)})

        items = select_outcome_deliverables(
            run_status="succeeded",
            run_message="plots",
            result_preview=None,
            error=None,
            project_id="p1",
            project_files=files,
            policy_store=store,
            max_artifacts=3,
        )
        file_items = [i for i in items if i.kind == "file"]
        hint_items = [i for i in items if i.kind == "hint"]
        assert len(file_items) == 3
        assert len(hint_items) == 1
        assert "3 more" in hint_items[0].text

    def test_cancelled_run(self, tmp_path) -> None:
        store = JsonDeliveryPolicyStore(tmp_path)
        items = select_outcome_deliverables(
            run_status="cancelled",
            run_message="analyze",
            result_preview=None,
            error=None,
            project_id=None,
            project_files=[],
            policy_store=store,
        )
        assert items[0].kind == "summary"
        assert "cancelled" in items[0].text
