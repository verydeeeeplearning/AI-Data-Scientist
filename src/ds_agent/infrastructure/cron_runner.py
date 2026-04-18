"""Cron expression evaluation for standing orders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from ds_agent.domain.entities.standing_order import CronTrigger

_MONTH_NAMES = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

_WEEKDAY_NAMES = {
    "SUN": 0,
    "MON": 1,
    "TUE": 2,
    "WED": 3,
    "THU": 4,
    "FRI": 5,
    "SAT": 6,
}


@dataclass(slots=True)
class _CronFields:
    minutes: set[int]
    hours: set[int]
    days: set[int]
    months: set[int]
    weekdays: set[int]
    raw_days: str
    raw_weekdays: str


class CronRunner:
    """Evaluate cron expressions without optional third-party dependencies."""

    def should_trigger(
        self,
        expression: str,
        *,
        now: datetime | None = None,
        timezone: str = "UTC",
    ) -> bool:
        """Return whether the cron expression matches the given instant."""
        trigger = CronTrigger(cron=expression, timezone=timezone)
        return self.matches(trigger, now=now)

    def matches(self, trigger: CronTrigger, *, now: datetime | None = None) -> bool:
        """Return whether one CronTrigger is due at the given instant."""
        current = self._normalize_time(now, trigger.timezone)
        fields = self._parse(trigger.cron)

        weekday = (current.weekday() + 1) % 7
        day_matches = current.day in fields.days
        weekday_matches = weekday in fields.weekdays
        if fields.raw_days != "*" and fields.raw_weekdays != "*":
            date_matches = day_matches or weekday_matches
        else:
            date_matches = day_matches and weekday_matches

        return (
            current.minute in fields.minutes
            and current.hour in fields.hours
            and current.month in fields.months
            and date_matches
        )

    def next_run(self, trigger: CronTrigger, *, after: datetime | None = None) -> datetime:
        """Return the next matching instant for the cron trigger."""
        current = self._normalize_time(after, trigger.timezone).replace(second=0, microsecond=0)
        candidate = current + timedelta(minutes=1)
        for _ in range(366 * 24 * 60):
            if self.matches(trigger, now=candidate):
                return candidate
            candidate += timedelta(minutes=1)
        raise ValueError(f"Unable to resolve next run for cron expression: {trigger.cron}")

    def _normalize_time(self, value: datetime | None, timezone: str) -> datetime:
        zone = ZoneInfo(timezone)
        if value is None:
            return datetime.now(zone).replace(second=0, microsecond=0)
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC).astimezone(zone)
        return value.astimezone(zone)

    def _parse(self, expression: str) -> _CronFields:
        minute, hour, day, month, weekday = expression.upper().split()
        return _CronFields(
            minutes=self._parse_field(minute, 0, 59),
            hours=self._parse_field(hour, 0, 23),
            days=self._parse_field(day, 1, 31),
            months=self._parse_field(month, 1, 12, names=_MONTH_NAMES),
            weekdays=self._parse_field(weekday, 0, 7, names=_WEEKDAY_NAMES, fold_seven=True),
            raw_days=day,
            raw_weekdays=weekday,
        )

    def _parse_field(
        self,
        raw: str,
        minimum: int,
        maximum: int,
        *,
        names: dict[str, int] | None = None,
        fold_seven: bool = False,
    ) -> set[int]:
        values: set[int] = set()
        for part in raw.split(","):
            values.update(
                self._expand_part(
                    part.strip(),
                    minimum,
                    maximum,
                    names=names,
                    fold_seven=fold_seven,
                )
            )
        return values

    def _expand_part(
        self,
        part: str,
        minimum: int,
        maximum: int,
        *,
        names: dict[str, int] | None,
        fold_seven: bool,
    ) -> set[int]:
        if part == "*":
            return set(range(minimum, maximum + 1))

        if "/" in part:
            base, step_raw = part.split("/", 1)
            step = int(step_raw)
            base_values = self._expand_part(
                "*" if base == "" else base,
                minimum,
                maximum,
                names=names,
                fold_seven=fold_seven,
            )
            start = min(base_values)
            return {value for value in sorted(base_values) if (value - start) % step == 0}

        if "-" in part:
            start_raw, end_raw = part.split("-", 1)
            start = self._coerce_value(start_raw, names=names, fold_seven=fold_seven)
            end = self._coerce_value(end_raw, names=names, fold_seven=fold_seven)
            if end < start:
                raise ValueError(f"Invalid cron range: {part}")
            return set(range(start, end + 1))

        return {self._coerce_value(part, names=names, fold_seven=fold_seven)}

    @staticmethod
    def _coerce_value(
        raw: str,
        *,
        names: dict[str, int] | None,
        fold_seven: bool,
    ) -> int:
        token = raw.strip().upper()
        value = names[token] if names and token in names else int(token)
        if fold_seven and value == 7:
            return 0
        return value
