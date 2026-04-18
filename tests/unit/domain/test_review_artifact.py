from __future__ import annotations

from ds_agent.domain.entities.review_artifact import build_review_artifact


def test_build_review_artifact_validates_payload_by_skill() -> None:
    artifact = build_review_artifact(
        skill_name="retrain-vs-rollback",
        summary="Rollback is safer than retrain for this degradation.",
        artifact={
            "recommendation": "rollback",
            "rationale": "Recent drift and F1 loss exceed the rollback threshold.",
            "evidence": ["psi=0.31", "f1_macro=-0.14"],
        },
        narrative="The deployed model drifted materially and should be rolled back.",
    )

    assert artifact.skill_name == "retrain-vs-rollback"
    assert artifact.artifact.recommendation == "rollback"
