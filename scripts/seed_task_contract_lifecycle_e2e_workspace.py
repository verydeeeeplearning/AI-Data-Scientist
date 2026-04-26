"""Seed an isolated task-contract lifecycle workspace for Electron E2E tests."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import _repo_imports  # noqa: F401

from ds_agent.application.dtos.task_contract import (
    DeliveryPackInputDTO,
    ReviewVerdictInputDTO,
    TaskContractDraftDTO,
)
from ds_agent.application.services.task_contract_usecases import (
    CreateTaskContractUseCase,
    RecordDeliveryPackUseCase,
    RecordReviewVerdictUseCase,
)
from ds_agent.config.loader import save_config
from ds_agent.config.schema import DSAgentConfig
from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.domain.entities.review_verdict import ConfidenceBand
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
    parser.add_argument("--session-id", default="seeded-task-contract-session")
    parser.add_argument("--task-id", default="TC-2026-902")
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
                content="Prepare a stakeholder-ready churn contract and move it through review.",
            ),
            ChatMessage(
                role=Role.ASSISTANT,
                content="Seeded task contract lifecycle workspace is ready for operator actions.",
            ),
        ],
    )


def _seed_task_contract(workspace_dir: Path, session_id: str, task_id: str) -> None:
    now = datetime(2026, 4, 16, 11, 0, tzinfo=UTC)
    store = SqliteTaskContractStore.for_workspace(str(workspace_dir))
    ids = _SeedIds(task_id)
    publisher = _NullPublisher()
    clock = _SeedClock(now)

    CreateTaskContractUseCase(store=store, clock=clock, ids=ids, publisher=publisher).execute(
        TaskContractDraftDTO.model_validate(
            {
                "session_id": session_id,
                "contract_type": "churn_analysis",
                "business_goal": "Prepare a retention-risk readout and owner-ready next actions.",
                "authority": "delegate",
                "audience": "senior_staff",
                "goal_brief": {
                    "business_question": "What is driving retention risk in the premium cohort?",
                    "ds_problem_statement": "Prioritize churn diagnostics and next actions.",
                    "comparison_baseline": "previous four-week retention baseline",
                    "decision_to_make": (
                        "confirm the response owner and launch the next intervention"
                    ),
                    "expected_effort": "M",
                },
                "required_deliverables": [
                    {"type": "exec_brief", "audience": "executive", "format": "markdown"}
                ],
                "created_by": "user",
            }
        )
    )

    RecordReviewVerdictUseCase(store, clock, ids, publisher).execute(
        ReviewVerdictInputDTO(
            task_id=task_id,
            category="orchestrator",
            result="pass",
            reviewer="verifier_orchestrator",
            summary="All required review gates passed.",
            run_id="run-seeded-auto-review",
            confidence=ConfidenceBand(score=0.74),
            metadata={
                "source": "auto_verifier",
                "auto_verifier_mode": "shadow",
            },
        )
    )

    RecordDeliveryPackUseCase(store, clock, ids, publisher).execute(
        DeliveryPackInputDTO.model_validate(
            {
                "task_id": task_id,
                "items": [
                    {
                        "deliverable_type": "exec_brief",
                        "audience": "executive",
                        "format": "markdown",
                        "artifact_path": "reports/retention-exec-brief.md",
                        "delivered": True,
                        "delivery_channel": "email",
                        "artifact_id": "DA-1",
                        "verifier_report_id": "VR-1",
                    }
                ],
                "artifacts": [
                    {
                        "artifact_id": "DA-1",
                        "type": "exec_brief",
                        "audience": "executive",
                        "format": "markdown",
                        "content_policy": {
                            "structure": ["Summary", "Recommendation", "Next actions"],
                            "technical_detail": "balanced",
                            "tone": "actionable",
                            "include_verifier_results": True,
                            "speculative_claims": "flagged",
                        },
                        "template_ref": "exec-brief/default",
                        "delivery_channel": ["email"],
                        "dispatch_mode": "manual_review",
                        "receivers": [{"role": "decision_owner", "resolver": "task_contract"}],
                        "rendered_uri": "reports/retention-exec-brief.md",
                        "verifier_report_id": "VR-1",
                    }
                ],
                "follow_up_actions": ["Confirm response owner", "Prepare launch checklist"],
                "source_analysis_id": "FA-LIFECYCLE-1",
                "status": "dispatched",
                "tenant": "default",
            }
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

    print(
        "seeded "
        f"config={config_path} workspace={workspace_dir} "
        f"session={args.session_id} task={args.task_id}"
    )


if __name__ == "__main__":
    main()
