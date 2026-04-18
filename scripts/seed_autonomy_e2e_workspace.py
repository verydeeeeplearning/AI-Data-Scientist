"""Seed an isolated autonomy-control-plane workspace for Electron E2E tests."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ds_agent.application.dtos.task_contract import AssumptionInputDTO, TaskContractDraftDTO
from ds_agent.application.services.task_contract_usecases import (
    AddAssumptionUseCase,
    CreateTaskContractUseCase,
)
from ds_agent.config.loader import save_config
from ds_agent.config.schema import DSAgentConfig
from ds_agent.domain.entities.certification import AutonomyRunStat
from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.domain.value_objects.audience_persona import AudiencePersona
from ds_agent.domain.value_objects.authority_mode import AuthorityMode
from ds_agent.infrastructure.persistence.certification_store import SqliteCertificationStore
from ds_agent.infrastructure.persistence.task_contract_store import SqliteTaskContractStore
from ds_agent.runtime.session_registry import RuntimeSessionRegistry
from ds_agent.runtime.transcript_store import JsonTranscriptStore


@dataclass
class _SeedClock:
    now_value: datetime

    def now(self) -> datetime:
        return self.now_value


@dataclass
class _SeedIds:
    task_id: str
    _counter: int = 0

    def new_task_id(self, _now: datetime) -> str:
        return self.task_id

    def new_artifact_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter}"


class _NullPublisher:
    def publish(self, _event: object) -> None:
        return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home-dir")
    parser.add_argument("--config-path")
    parser.add_argument("--workspace-dir", required=True)
    parser.add_argument("--session-id", default="seeded-autonomy-session")
    parser.add_argument("--task-id", default="TC-2026-901")
    args = parser.parse_args()
    if not args.home_dir and not args.config_path:
        parser.error("either --home-dir or --config-path is required")
    return args


def _seed_config(config_path: Path, workspace_dir: Path) -> None:
    config = DSAgentConfig()
    config.agent.workspace_dir = str(workspace_dir)
    config.gateway.autonomous_runtime_enabled = False
    save_config(config, config_path)


def _seed_runtime_session(workspace_dir: Path, session_id: str) -> None:
    RuntimeSessionRegistry(str(workspace_dir)).ensure(session_id, "electron")
    JsonTranscriptStore(str(workspace_dir)).replace_messages(
        session_id,
        [
            ChatMessage(
                role=Role.USER,
                content="Review last week's KPI anomaly summary and update the mission controls.",
            ),
            ChatMessage(
                role=Role.ASSISTANT,
                content="Seeded autonomy control plane workspace is ready for operator review.",
            ),
        ],
    )


def _seed_task_contract(workspace_dir: Path, session_id: str, task_id: str) -> None:
    now = datetime(2026, 4, 16, 9, 0, tzinfo=UTC)
    store = SqliteTaskContractStore.for_workspace(str(workspace_dir))
    ids = _SeedIds(task_id)
    use_case = CreateTaskContractUseCase(
        store=store,
        clock=_SeedClock(now),
        ids=ids,
        publisher=_NullPublisher(),
    )
    use_case.execute(
        TaskContractDraftDTO.model_validate(
            {
                "session_id": session_id,
                "contract_type": "kpi_triage",
                "business_goal": (
                    "Triage weekly KPI anomalies and prepare operator-facing next actions."
                ),
                "authority": "delegate",
                "audience": "senior_staff",
                "mission": "weekly-kpi-triage",
                "goal_brief": {
                    "business_question": (
                        "Why did weekly growth KPIs drift from the expected range?"
                    ),
                    "ds_problem_statement": "Anomaly triage with stakeholder-ready explanations.",
                    "comparison_baseline": "prior four-week rolling baseline",
                    "decision_to_make": "assign an owner and select the next diagnostic action",
                    "expected_effort": "M",
                },
                "required_deliverables": [
                    {
                        "type": "exec_brief",
                        "audience": "executive",
                        "format": "md",
                    }
                ],
                "created_by": "user",
            }
        )
    )
    AddAssumptionUseCase(
        store=store,
        clock=_SeedClock(now),
        ids=ids,
        publisher=_NullPublisher(),
    ).execute(
        AssumptionInputDTO(
            task_id=task_id,
            statement="KPI anomaly threshold matches the operator playbook definition.",
            rationale="The weekly alert should stay aligned with the documented threshold.",
            risk_level="high",
        )
    )


def _seed_certification_stats(workspace_dir: Path) -> None:
    store = SqliteCertificationStore.for_workspace(str(workspace_dir))
    started_at = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)
    for index in range(10):
        run_started = started_at + timedelta(days=index)
        store.record_run_stat(
            AutonomyRunStat(
                mission_name="weekly-kpi-triage",
                mission_version=1,
                run_id=f"shadow-run-{index + 1:02d}",
                authority=AuthorityMode.SHADOW,
                audience=AudiencePersona.PEER_DS,
                started_at=run_started,
                ended_at=run_started + timedelta(minutes=18),
                outcome="success",
                verifier_score=0.91,
                violations_critical=0,
                violations_warn=0,
                rollback_rehearsal=(index == 0),
            )
        )


def main() -> None:
    args = _parse_args()
    if args.config_path:
        config_path = Path(args.config_path).expanduser().resolve()
    else:
        home_dir = Path(args.home_dir).expanduser().resolve()
        config_path = home_dir / ".ds-agent" / "config.yaml"
    workspace_dir = Path(args.workspace_dir).expanduser().resolve()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    _seed_config(config_path, workspace_dir)
    _seed_runtime_session(workspace_dir, args.session_id)
    _seed_task_contract(workspace_dir, args.session_id, args.task_id)
    _seed_certification_stats(workspace_dir)

    print(
        "seeded "
        f"config={config_path} workspace={workspace_dir} "
        f"session={args.session_id} task={args.task_id}"
    )


if __name__ == "__main__":
    main()
