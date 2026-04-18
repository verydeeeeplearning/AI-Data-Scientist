"""CronRunner tests."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from ds_agent.domain.entities.standing_order import CronTrigger
from ds_agent.infrastructure.cron_runner import CronRunner


class TestCronRunner:
    def test_should_trigger_weekly_schedule(self):
        runner = CronRunner()
        now = datetime(2026, 4, 13, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))

        assert runner.should_trigger(
            "0 9 * * MON",
            now=now,
            timezone="Asia/Seoul",
        ) is True

    def test_next_run_advances_to_next_match(self):
        runner = CronRunner()
        trigger = CronTrigger("0 9 * * MON", timezone="Asia/Seoul")
        after = datetime(2026, 4, 13, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))

        next_run = runner.next_run(trigger, after=after)

        assert next_run == datetime(2026, 4, 20, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))
