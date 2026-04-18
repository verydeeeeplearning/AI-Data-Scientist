"""SkillExtractor unit tests."""

from __future__ import annotations

from pathlib import Path

from ds_agent.self_improve.post_project import ProjectOutcome
from ds_agent.self_improve.skill_extractor import SkillExtractor
from ds_agent.skills.parser import parse_skill_file


def _successful_outcome(**overrides) -> ProjectOutcome:
    base = dict(
        project_id="proj-001",
        task_type="classification",
        success=True,
        primary_metric="f1",
        primary_metric_value=0.91,
        models_tried=["lightgbm", "xgboost"],
        best_model="lightgbm",
        domain="healthcare",
        key_findings=["Feature X dominates", "Class imbalance required SMOTE"],
        steps_taken=[
            "Profile dataset",
            "Engineer time-window features",
            "Train baseline + LightGBM",
            "Calibrate probabilities",
        ],
    )
    base.update(overrides)
    return ProjectOutcome(**base)


def test_skill_extractor_writes_markdown_for_successful_outcome(tmp_path: Path) -> None:
    extractor = SkillExtractor(custom_dir=tmp_path)
    outcome = _successful_outcome()

    result = extractor.extract(outcome)

    assert result is not None
    assert result.path.exists()
    text = result.path.read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "category: extracted" in text
    assert "proj-001" in text
    assert "LightGBM" in text or "lightgbm" in text
    assert "promotion_status: pending_promotion" in text
    assert result.candidate_id == result.name
    assert result.promotion_status == "pending_promotion"


def test_extracted_markdown_is_parseable_as_skill(tmp_path: Path) -> None:
    extractor = SkillExtractor(custom_dir=tmp_path)
    result = extractor.extract(_successful_outcome())

    assert result is not None
    entry = parse_skill_file(result.path)
    assert entry is not None
    assert entry.category == "extracted"
    assert entry.author == "skill_extractor"
    assert "extracted" in entry.tags


def test_skip_failed_outcome(tmp_path: Path) -> None:
    extractor = SkillExtractor(custom_dir=tmp_path)
    outcome = _successful_outcome(success=False)

    assert extractor.extract(outcome) is None
    assert list(tmp_path.iterdir()) == []


def test_skip_when_too_few_steps(tmp_path: Path) -> None:
    extractor = SkillExtractor(custom_dir=tmp_path, min_steps=5)
    outcome = _successful_outcome()

    assert extractor.extract(outcome) is None


def test_skip_when_metric_below_threshold(tmp_path: Path) -> None:
    extractor = SkillExtractor(custom_dir=tmp_path, min_metric_value=0.95)
    outcome = _successful_outcome(primary_metric_value=0.80)

    assert extractor.extract(outcome) is None


def test_post_project_learner_invokes_skill_extractor(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from ds_agent.self_improve.post_project import PostProjectLearner

    extractor = SkillExtractor(custom_dir=tmp_path)
    learner = PostProjectLearner(
        experiment_log=MagicMock(),
        code_registry=MagicMock(),
        domain_kb=MagicMock(),
        skill_extractor=extractor,
    )

    result = learner.learn(_successful_outcome())

    assert result["custom_skills_extracted"] == 1
    assert len(list(tmp_path.glob("*.md"))) == 1
