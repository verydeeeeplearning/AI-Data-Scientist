"""Prompt-hint builder for semantic memory."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ds_agent.infrastructure.semantic_memory_runtime import resolve_semantic_db_path


class SemanticMemoryHintBuilder:
    """Build a compact semantic-context summary for prompt injection."""

    def __init__(
        self,
        workspace_dir: str | Path,
        *,
        max_items: int = 3,
    ) -> None:
        self._workspace_dir = Path(workspace_dir)
        self._max_items = max_items

    def build_hints(self) -> str:
        """Return semantic context summary or an empty string when unavailable."""

        db_path = resolve_semantic_db_path(self._workspace_dir)
        if not db_path.exists():
            return ""

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                metrics = self._fetch_metrics(conn)
                glossary = self._fetch_glossary(conn)
                calendar = self._fetch_calendar(conn)
                negative = self._fetch_negative_knowledge(conn)
        except sqlite3.Error:
            return ""

        lines: list[str] = []
        if metrics:
            rendered = ", ".join(
                f"{row['metric_id']} (owner: {row['owner']}, grain: {row['grain']})"
                for row in metrics
            )
            lines.append(f"- Metrics: {rendered}")
        if glossary:
            rendered = ", ".join(
                f"{row['canonical_form']} [{row['category']}]" for row in glossary
            )
            lines.append(f"- Glossary: {rendered}")
        if calendar:
            rendered = ", ".join(
                f"{row['name']} ({row['start_date']}..{row['end_date']})" for row in calendar
            )
            lines.append(f"- Calendar: {rendered}")
        if negative:
            rendered = ", ".join(
                f"{row['topic']} -> {row['correct_approach']}" for row in negative
            )
            lines.append(f"- Negative Knowledge: {rendered}")

        if not lines:
            return ""
        return "## Semantic Context\n" + "\n".join(lines)

    def _fetch_metrics(self, conn: sqlite3.Connection) -> list[sqlite3.Row]:
        return conn.execute(
            """
            SELECT metric_id, owner, grain
            FROM semantic_metric
            ORDER BY COALESCE(last_reviewed, '') DESC, metric_id ASC
            LIMIT ?
            """,
            (self._max_items,),
        ).fetchall()

    def _fetch_glossary(self, conn: sqlite3.Connection) -> list[sqlite3.Row]:
        return conn.execute(
            """
            SELECT canonical_form, category
            FROM semantic_glossary
            ORDER BY canonical_form ASC
            LIMIT ?
            """,
            (self._max_items,),
        ).fetchall()

    def _fetch_calendar(self, conn: sqlite3.Connection) -> list[sqlite3.Row]:
        return conn.execute(
            """
            SELECT name, start_date, end_date
            FROM semantic_calendar_event
            ORDER BY start_date ASC, end_date ASC
            LIMIT ?
            """,
            (self._max_items,),
        ).fetchall()

    def _fetch_negative_knowledge(self, conn: sqlite3.Connection) -> list[sqlite3.Row]:
        return conn.execute(
            """
            SELECT topic, correct_approach
            FROM semantic_negative_knowledge
            ORDER BY recorded_at DESC
            LIMIT ?
            """,
            (self._max_items,),
        ).fetchall()
