from __future__ import annotations

import pytest

from ds_agent.agent.confidence_scorer import ConfidenceScorer
from ds_agent.application.services.mission_required_checks import MissionRequiredCheckResolver
from ds_agent.application.services.verifier_orchestrator import VerifierOrchestrator
from ds_agent.domain.dtos.verifier_context import VerifierConfig, VerifierContext
from ds_agent.domain.entities.review_verdict import CheckResult, LayerResult

pytestmark = pytest.mark.contract


def _layer(layer: str, checks: list[CheckResult]) -> LayerResult:
    return LayerResult(
        layer=layer,  # type: ignore[arg-type]
        checks=checks,
    )


@pytest.mark.asyncio
async def test_prediction_required_check_metadata_contract_matches_current_pack(
    mission_loader,
    fixed_clock,
    verdict_repo,
    static_verifier_factory,
    make_task_contract,
) -> None:
    resolver = MissionRequiredCheckResolver(mission_loader)
    pack = mission_loader.load("prediction")
    resolution = resolver.resolve_pack(pack)
    orchestrator = VerifierOrchestrator(
        statistical=static_verifier_factory(
            _layer(
                "statistical",
                [
                    CheckResult(
                        check_id="baseline_comparison",
                        status="pass",
                        score=1.0,
                        evidence={},
                        message="baseline exceeded",
                        duration_ms=1,
                    ),
                    CheckResult(
                        check_id="temporal_split_robustness",
                        status="pass",
                        score=1.0,
                        evidence={},
                        message="temporal split is stable",
                        duration_ms=1,
                    ),
                    CheckResult(
                        check_id="subgroup_stability",
                        status="warn",
                        score=0.61,
                        evidence={},
                        message="minor subgroup variance",
                        duration_ms=1,
                    ),
                ],
            )
        ),
        data=static_verifier_factory(
            _layer(
                "data",
                [
                    CheckResult(
                        check_id="schema_contract_validation",
                        status="pass",
                        score=1.0,
                        evidence={},
                        message="schema is stable",
                        duration_ms=1,
                    ),
                    CheckResult(
                        check_id="data_leakage_detection",
                        status="pass",
                        score=1.0,
                        evidence={},
                        message="no label leakage detected",
                        duration_ms=1,
                    ),
                ],
            )
        ),
        policy=static_verifier_factory(
            _layer(
                "policy",
                [
                    CheckResult(
                        check_id="pii_exposure",
                        status="pass",
                        score=1.0,
                        evidence={},
                        message="no sensitive exposure",
                        duration_ms=1,
                    )
                ],
            )
        ),
        narrative=static_verifier_factory(
            LayerResult(
                layer="narrative",
                checks=[
                    CheckResult(
                        check_id="claim_evidence_alignment",
                        status="pass",
                        score=1.0,
                        evidence={},
                        message="claims are aligned",
                        duration_ms=1,
                    )
                ],
                metadata={"judge_mode": "llm", "judge_check_count": 1},
            )
        ),
        repo=verdict_repo,
        scorer=ConfidenceScorer(),
        clock=fixed_clock,
        mission_required_check_resolver=resolver,
    )

    verdict = await orchestrator.run(
        VerifierContext(
            run_id="run-contract-1",
            task_contract=make_task_contract(mission="prediction"),
            artifacts={},
            config=VerifierConfig(),
        )
    )

    assert verdict_repo.saved[-1].verdict_id == verdict.verdict_id
    assert verdict.metadata["judge_mode"] == "llm"
    assert verdict.metadata["mission_name"] == pack.name
    assert verdict.metadata["mission_pack_loaded"] is True
    assert verdict.metadata["mission_required_checks"] == list(pack.required_checks)
    assert verdict.metadata["mission_required_check_map"] == {
        required_check: list(check_ids)
        for required_check, check_ids in resolution.mapped_required_checks.items()
    }
    assert verdict.metadata["mission_required_check_ids"] == list(resolution.resolved_check_ids)
    assert verdict.metadata["mission_required_check_results"] == {
        "schema_drift": "pass",
        "label_leakage": "pass",
        "temporal_leakage": "pass",
        "baseline_compare": "pass",
        "subgroup_stability": "warn",
    }
    assert verdict.metadata["mission_required_check_failures"] == []


@pytest.mark.asyncio
async def test_missing_mission_pack_contract_stays_explicit_in_verdict_metadata(
    mission_loader,
    fixed_clock,
    verdict_repo,
    static_verifier_factory,
    make_task_contract,
) -> None:
    orchestrator = VerifierOrchestrator(
        statistical=static_verifier_factory(
            _layer(
                "statistical",
                [
                    CheckResult(
                        check_id="baseline_comparison",
                        status="pass",
                        score=1.0,
                        evidence={},
                        message="baseline exceeded",
                        duration_ms=1,
                    )
                ],
            )
        ),
        data=static_verifier_factory(
            _layer(
                "data",
                [
                    CheckResult(
                        check_id="schema_contract_validation",
                        status="pass",
                        score=1.0,
                        evidence={},
                        message="schema stable",
                        duration_ms=1,
                    )
                ],
            )
        ),
        policy=static_verifier_factory(
            _layer(
                "policy",
                [
                    CheckResult(
                        check_id="pii_exposure",
                        status="pass",
                        score=1.0,
                        evidence={},
                        message="policy clean",
                        duration_ms=1,
                    )
                ],
            )
        ),
        narrative=static_verifier_factory(
            _layer(
                "narrative",
                [
                    CheckResult(
                        check_id="claim_evidence_alignment",
                        status="pass",
                        score=1.0,
                        evidence={},
                        message="aligned",
                        duration_ms=1,
                    )
                ],
            )
        ),
        repo=verdict_repo,
        scorer=ConfidenceScorer(),
        clock=fixed_clock,
        mission_required_check_resolver=MissionRequiredCheckResolver(mission_loader),
    )

    verdict = await orchestrator.run(
        VerifierContext(
            run_id="run-contract-2",
            task_contract=make_task_contract(mission="missing-pack"),
            artifacts={},
            config=VerifierConfig(),
        )
    )

    assert verdict.metadata["mission_name"] == "missing-pack"
    assert verdict.metadata["mission_pack_loaded"] is False
    assert "mission_required_checks" not in verdict.metadata
    assert "mission_required_check_results" not in verdict.metadata
