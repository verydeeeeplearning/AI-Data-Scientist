"""standing_order tool tests."""

from __future__ import annotations

import asyncio
import json

from ds_agent.application.services.scheduler_service import SchedulerService, set_scheduler_service
from ds_agent.infrastructure.cron_runner import CronRunner
from ds_agent.runtime.policy_store import JsonPolicyStore
from ds_agent.tools.registry import ToolRegistry
from ds_agent.tools.standing_order_tools import standing_order


class TestStandingOrderTool:
    def test_create_list_and_history(self, tmp_path):
        service = SchedulerService(
            store=JsonPolicyStore(base_dir=tmp_path),
            cron_runner=CronRunner(),
        )
        set_scheduler_service(service)

        created = json.loads(
            asyncio.run(
                ToolRegistry.dispatch(
                    "standing_order",
                    {
                        "action": "create",
                        "name": "Weekly KPI scan",
                        "session_id": "session-1",
                        "prompt": "Scan KPI drift and summarize anomalies.",
                        "trigger": {
                            "type": "cron",
                            "cron": "0 9 * * MON",
                            "timezone": "Asia/Seoul",
                        },
                        "budget_limit_usd": 0.5,
                    },
                )
            )
        )
        order_id = created["order"]["order_id"]

        listed = json.loads(
            asyncio.run(ToolRegistry.dispatch("standing_order", {"action": "list"}))
        )
        assert listed["count"] == 1
        assert listed["orders"][0]["order_id"] == order_id

        run_now = json.loads(
            asyncio.run(
                ToolRegistry.dispatch(
                    "standing_order",
                    {"action": "run_now", "order_id": order_id},
                )
            )
        )
        assert run_now["dispatch"]["session_id"] == "session-1"

        history = json.loads(
            asyncio.run(
                ToolRegistry.dispatch(
                    "standing_order",
                    {"action": "view_history", "order_id": order_id},
                )
            )
        )
        assert history["history"][0]["status"] == "run_requested"

        # Direct call stays importable and self-registered.
        assert standing_order is not None
