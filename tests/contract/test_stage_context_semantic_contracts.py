from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ds_agent.agent.prompt_builder import (
    _STAGE_RULES,
    _STAGE_TO_SKILLS,
    PromptBuilder,
)
from ds_agent.domain.entities.working_memory import SessionWorkingMemory
from ds_agent.domain.value_objects.analysis_stage import AnalysisStage
from ds_agent.runtime.working_memory import JsonWorkingMemoryStore

pytestmark = pytest.mark.contract


def _repo_skill_names() -> set[str]:
    repo_root = Path(__file__).resolve().parents[2]
    skill_dirs = (
        repo_root / "src" / "ds_agent" / "skills" / "builtin",
        repo_root / "src" / "ds_agent" / "skills" / "shared",
    )
    names: set[str] = set()
    for skill_dir in skill_dirs:
        names.update(path.stem for path in skill_dir.glob("*.md"))
    return names


def _manual_contract_workspace(name: str) -> Path:
    base_dir = Path("contract_gate_tmp").resolve()
    base_dir.mkdir(parents=True, exist_ok=True)
    workspace = base_dir / name
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def test_stage_rule_coverage_matches_analysis_stage_enum() -> None:
    assert set(_STAGE_RULES) == set(AnalysisStage)
    assert set(_STAGE_TO_SKILLS) == set(AnalysisStage)
    assert all(_STAGE_RULES[stage] for stage in AnalysisStage)


def test_stage_skill_overlay_refs_real_repo_skills() -> None:
    repo_skills = _repo_skill_names()
    referenced_skills = {
        skill_name for skill_names in _STAGE_TO_SKILLS.values() for skill_name in skill_names
    }

    assert referenced_skills
    assert referenced_skills <= repo_skills


def test_working_memory_stage_fields_round_trip_in_json_store() -> None:
    workspace = _manual_contract_workspace("stage-context-roundtrip")
    store = JsonWorkingMemoryStore(base_dir=workspace)
    original = SessionWorkingMemory(
        session_id="session-stage-roundtrip",
        current_summary="Modeling is in progress.",
        current_stage=AnalysisStage.MODELING,
        stage_entered_at=1_776_761_400.0,
        next_step="Train the baseline first.",
    )

    store.save(original)
    loaded = store.load("session-stage-roundtrip")

    assert loaded is not None
    assert loaded.current_stage == AnalysisStage.MODELING
    assert loaded.stage_entered_at == 1_776_761_400.0
    assert loaded.next_step == "Train the baseline first."


def test_working_memory_legacy_payload_without_stage_fields_loads_cleanly() -> None:
    workspace = _manual_contract_workspace("stage-context-legacy")
    store = JsonWorkingMemoryStore(base_dir=workspace)
    payload = {
        "session_id": "session-legacy",
        "active_goal_id": None,
        "last_run_id": None,
        "last_user_message": "Profile the dataset.",
        "current_summary": "Recovered from a pre-Phase-3 memory file.",
        "next_step": "Inspect missingness by column.",
        "pending_questions": [],
        "last_reflection": "",
        "recovery_note": None,
        "updated_at": 1_776_761_400.0,
    }
    memory_path = workspace / "working-memory" / "session-legacy.memory.json"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = store.load("session-legacy")

    assert loaded is not None
    assert loaded.current_stage is None
    assert loaded.stage_entered_at is None
    assert loaded.next_step == "Inspect missingness by column."


def test_prompt_builder_injects_stage_guidance_for_persisted_stage() -> None:
    working_memory_store = MagicMock()
    working_memory_store.load.return_value = SessionWorkingMemory(
        session_id="session-stage-prompt",
        current_stage=AnalysisStage.EVALUATION,
        next_step="Translate the metric trade-offs into business risk.",
    )

    builder = PromptBuilder(
        session_id="session-stage-prompt",
        working_memory_store=working_memory_store,
    )
    system_prompt = builder.build("Summarize the evaluation state.")[0].content

    assert "Stage-Aware Guidance" in system_prompt
    assert "Current stage: evaluation" in system_prompt
    assert "Execution Continuity" in system_prompt
    assert "Prioritize these skills right now: `evaluation`" in system_prompt
