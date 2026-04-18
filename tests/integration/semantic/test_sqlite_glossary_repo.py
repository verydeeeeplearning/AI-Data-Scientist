from __future__ import annotations

import uuid
from pathlib import Path

from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.infrastructure.sqlite_base import SemanticSqliteDatabase
from ds_agent.memory.semantic.infrastructure.sqlite_glossary_repo import SqliteGlossaryRepository


def _db() -> SemanticSqliteDatabase:
    base_dir = Path("semantic_test_artifacts/glossary")
    base_dir.mkdir(parents=True, exist_ok=True)
    return SemanticSqliteDatabase(base_dir / f"{uuid.uuid4().hex}.db")


def test_glossary_repo_round_trip_and_lookup() -> None:
    repo = SqliteGlossaryRepository(_db())
    term = GlossaryTerm(
        term_id="term.mau",
        canonical_form="MAU",
        definition="월간 활성 유저",
        synonyms=["monthly active users"],
        abbreviations=["MAU"],
        translations={"ko": "월간 활성 유저"},
        linked_metric_ids=["mau"],
        category="metric",
    )
    repo.save(term)

    restored = repo.get(term.term_id)
    assert restored is not None
    assert restored.canonical_form == "MAU"

    matches = repo.lookup("월간 활성 유저")
    assert matches
    assert matches[0].term_id == term.term_id

