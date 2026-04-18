"""SQLite repository for organizational semantic context."""

from __future__ import annotations

import sqlite3
from datetime import date

from ds_agent.memory.semantic.domain.org_context import (
    CalendarEvent,
    DecisionLogEntry,
    NegativeKnowledge,
    TeamOwnership,
)
from ds_agent.memory.semantic.infrastructure.sqlite_base import (
    SemanticSqliteDatabase,
    json_dumps,
    json_loads,
)


class SqliteOrgContextRepository:
    """SQLite-backed repository for org semantic context."""

    def __init__(self, db: SemanticSqliteDatabase) -> None:
        self._db = db

    def list_calendar_events(self, *, as_of: date | None = None) -> list[CalendarEvent]:
        with self._db.lock, self._db.connect() as conn:
            if as_of is None:
                rows = conn.execute(
                    "SELECT * FROM semantic_calendar_event ORDER BY start_date, end_date"
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM semantic_calendar_event
                    WHERE start_date <= ? AND end_date >= ?
                    ORDER BY start_date, end_date
                    """,
                    (str(as_of), str(as_of)),
                ).fetchall()
        return [self._row_to_calendar(row) for row in rows]

    def save_calendar_event(self, event: CalendarEvent) -> None:
        with self._db.lock, self._db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO semantic_calendar_event (
                    event_id, type, name, start_date, end_date, description, impact_hint
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.type,
                    event.name,
                    event.start_date.isoformat(),
                    event.end_date.isoformat(),
                    event.description,
                    event.impact_hint,
                ),
            )
            conn.commit()

    def get_team(self, team: str) -> TeamOwnership | None:
        with self._db.lock, self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM semantic_team_ownership WHERE team = ?",
                (team,),
            ).fetchone()
        return self._row_to_team(row) if row is not None else None

    def save_team(self, ownership: TeamOwnership) -> None:
        with self._db.lock, self._db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO semantic_team_ownership (
                    team, contact, owned_metrics_json, owned_tables_json, approver_chain_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    ownership.team,
                    ownership.contact,
                    json_dumps(ownership.owned_metrics),
                    json_dumps(ownership.owned_tables),
                    json_dumps(ownership.approver_chain),
                ),
            )
            conn.commit()

    def list_negative_knowledge(self, topic: str) -> list[NegativeKnowledge]:
        with self._db.lock, self._db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM semantic_negative_knowledge
                WHERE topic = ?
                ORDER BY recorded_at DESC
                """,
                (topic,),
            ).fetchall()
        return [self._row_to_nk(row) for row in rows]

    def save_negative_knowledge(self, entry: NegativeKnowledge) -> None:
        with self._db.lock, self._db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO semantic_negative_knowledge (
                    nk_id, topic, wrong_approach, why_wrong, correct_approach,
                    recorded_at, recorded_by, references_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.nk_id,
                    entry.topic,
                    entry.wrong_approach,
                    entry.why_wrong,
                    entry.correct_approach,
                    entry.recorded_at.isoformat(),
                    entry.recorded_by,
                    json_dumps(entry.references),
                ),
            )
            conn.commit()

    def save_decision_log(self, entry: DecisionLogEntry) -> None:
        with self._db.lock, self._db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO semantic_decision_log (
                    decision_id, date, summary, context, metrics_used_json,
                    verified_query_ids_json, outcome, rationale
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.decision_id,
                    entry.date.isoformat(),
                    entry.summary,
                    entry.context,
                    json_dumps(entry.metrics_used),
                    json_dumps(entry.verified_query_ids),
                    entry.outcome,
                    entry.rationale,
                ),
            )
            conn.commit()

    @staticmethod
    def _row_to_calendar(row: sqlite3.Row) -> CalendarEvent:
        return CalendarEvent.model_validate(
            {
                "event_id": str(row["event_id"]),
                "type": row["type"],
                "name": str(row["name"]),
                "start_date": str(row["start_date"]),
                "end_date": str(row["end_date"]),
                "description": str(row["description"]),
                "impact_hint": str(row["impact_hint"]) if row["impact_hint"] is not None else None,
            }
        )

    @staticmethod
    def _row_to_team(row: sqlite3.Row) -> TeamOwnership:
        return TeamOwnership.model_validate(
            {
                "team": str(row["team"]),
                "contact": str(row["contact"]),
                "owned_metrics": json_loads(row["owned_metrics_json"], default=[]),
                "owned_tables": json_loads(row["owned_tables_json"], default=[]),
                "approver_chain": json_loads(row["approver_chain_json"], default=[]),
            }
        )

    @staticmethod
    def _row_to_nk(row: sqlite3.Row) -> NegativeKnowledge:
        return NegativeKnowledge.model_validate(
            {
                "nk_id": str(row["nk_id"]),
                "topic": str(row["topic"]),
                "wrong_approach": str(row["wrong_approach"]),
                "why_wrong": str(row["why_wrong"]),
                "correct_approach": str(row["correct_approach"]),
                "recorded_at": str(row["recorded_at"]),
                "recorded_by": row["recorded_by"],
                "references": json_loads(row["references_json"], default=[]),
            }
        )
