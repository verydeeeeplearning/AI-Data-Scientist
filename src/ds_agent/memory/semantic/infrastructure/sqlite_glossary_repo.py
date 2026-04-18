"""SQLite repository for business glossary terms."""

from __future__ import annotations

import sqlite3
from collections import OrderedDict

from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.infrastructure.sqlite_base import (
    SemanticSqliteDatabase,
    json_dumps,
    json_loads,
    prepare_fts_query,
)


class SqliteGlossaryRepository:
    """SQLite-backed glossary repository."""

    def __init__(self, db: SemanticSqliteDatabase) -> None:
        self._db = db

    def get(self, term_id: str) -> GlossaryTerm | None:
        with self._db.lock, self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM semantic_glossary WHERE term_id = ?",
                (term_id,),
            ).fetchone()
        return self._row_to_term(row) if row is not None else None

    def lookup(self, query: str, *, limit: int = 5) -> list[GlossaryTerm]:
        normalized = query.strip()
        if not normalized:
            return []
        results: OrderedDict[str, GlossaryTerm] = OrderedDict()
        with self._db.lock, self._db.connect() as conn:
            exact_rows = conn.execute(
                """
                SELECT *
                FROM semantic_glossary
                WHERE lower(canonical_form) = ?
                LIMIT ?
                """,
                (normalized.casefold(), limit),
            ).fetchall()
            for row in exact_rows:
                term = self._row_to_term(row)
                results[term.term_id] = term

            if len(results) < limit:
                fts_rows = conn.execute(
                    """
                    SELECT g.*
                    FROM semantic_glossary g
                    JOIN semantic_glossary_fts f ON g.rowid = f.rowid
                    WHERE semantic_glossary_fts MATCH ?
                    LIMIT ?
                    """,
                    (prepare_fts_query(normalized), limit - len(results)),
                ).fetchall()
                for row in fts_rows:
                    term = self._row_to_term(row)
                    results.setdefault(term.term_id, term)
        return list(results.values())[:limit]

    def save(self, term: GlossaryTerm) -> None:
        payload = term.model_dump(mode="json")
        variants_text = " ".join(
            [
                term.canonical_form,
                *term.synonyms,
                *term.abbreviations,
                *payload["translations"].values(),
            ]
        )
        with self._db.lock, self._db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO semantic_glossary (
                    term_id, canonical_form, definition, synonyms_json, abbreviations_json,
                    translations_json, linked_metric_ids_json, category, owner, variants_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    term.term_id,
                    term.canonical_form,
                    term.definition,
                    json_dumps(payload["synonyms"]),
                    json_dumps(payload["abbreviations"]),
                    json_dumps(payload["translations"]),
                    json_dumps(payload["linked_metric_ids"]),
                    term.category,
                    term.owner,
                    variants_text,
                ),
            )
            conn.commit()

    @staticmethod
    def _row_to_term(row: sqlite3.Row) -> GlossaryTerm:
        return GlossaryTerm.model_validate(
            {
                "term_id": str(row["term_id"]),
                "canonical_form": str(row["canonical_form"]),
                "definition": str(row["definition"]),
                "synonyms": json_loads(row["synonyms_json"], default=[]),
                "abbreviations": json_loads(row["abbreviations_json"], default=[]),
                "translations": json_loads(row["translations_json"], default={}),
                "linked_metric_ids": json_loads(row["linked_metric_ids_json"], default=[]),
                "category": row["category"],
                "owner": str(row["owner"]) if row["owner"] is not None else None,
            }
        )
