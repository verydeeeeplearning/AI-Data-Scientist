"""Seed an isolated workflow-integration workspace for Electron E2E tests.

Creates a task contract, a work object in intake phase, and seeded
integration events (Slack message + Jira ticket) so the E2E test can
exercise the WorkObject panel mutations and IntegrationSettings health
check without requiring real external services.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import _repo_imports  # noqa: F401

from ds_agent.application.dtos.task_contract import TaskContractDraftDTO
from ds_agent.application.dtos.work_object import CreateWorkObjectDTO
from ds_agent.application.services.task_contract_usecases import (
    CreateTaskContractUseCase,
)
from ds_agent.application.services.work_object_usecases import (
    CreateWorkObjectUseCase,
)
from ds_agent.config.loader import save_config
from ds_agent.config.schema import DSAgentConfig
from ds_agent.domain.entities.integration_event import (
    IntegrationEvent,
    IntegrationEventStatus,
)
from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.infrastructure.persistence.task_contract_store import (
    SqliteTaskContractStore,
)
from ds_agent.infrastructure.persistence.work_object_store import (
    SqliteWorkObjectStore,
)
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
    work_object_id: str
    _counter: int = 0

    def new_task_id(self, _now: datetime) -> str:
        return self.task_id

    def new_work_object_id(self, _now: datetime) -> str:
        return self.work_object_id

    def new_artifact_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{9510000 + self._counter}"


class _NullPublisher:
    def publish(self, _event: object) -> None:
        return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed workflow-integration E2E workspace",
    )
    parser.add_argument("--home-dir")
    parser.add_argument("--config-path")
    parser.add_argument("--workspace-dir", required=True)
    parser.add_argument(
        "--session-id",
        default="seeded-workflow-session",
    )
    parser.add_argument("--task-id", default="TC-2026-951")
    parser.add_argument("--work-object-id", default="WO-2026-951001")
    args = parser.parse_args()
    if not args.home_dir and not args.config_path:
        parser.error("either --home-dir or --config-path is required")
    return args


def _seed_config(config_path: Path, workspace_dir: Path) -> None:
    config = DSAgentConfig()
    config.agent.workspace_dir = str(workspace_dir)
    config.gateway.autonomous_runtime_enabled = False
    save_config(config, config_path)


def _seed_runtime_session(
    workspace_dir: Path,
    session_id: str,
) -> None:
    RuntimeSessionRegistry(str(workspace_dir)).ensure(session_id, "electron")
    JsonTranscriptStore(str(workspace_dir)).replace_messages(
        session_id,
        [
            ChatMessage(
                role=Role.USER,
                content=(
                    "Dispatch the weekly churn report to Slack "
                    "and create a Jira follow-up ticket."
                ),
            ),
            ChatMessage(
                role=Role.ASSISTANT,
                content=(
                    "Workflow integration workspace is seeded. "
                    "Ready for operator review."
                ),
            ),
        ],
    )


def _seed_task_contract(
    workspace_dir: Path,
    session_id: str,
    task_id: str,
) -> SqliteTaskContractStore:
    now = datetime(2026, 4, 16, 9, 0, tzinfo=UTC)
    store = SqliteTaskContractStore.for_workspace(str(workspace_dir))
    ids = _SeedIds(task_id, "")
    CreateTaskContractUseCase(
        store=store,
        clock=_SeedClock(now),
        ids=ids,
        publisher=_NullPublisher(),
    ).execute(
        TaskContractDraftDTO.model_validate(
            {
                "session_id": session_id,
                "contract_type": "churn_analysis",
                "business_goal": (
                    "Analyse weekly churn drivers and dispatch "
                    "stakeholder-facing summary with follow-up ticket."
                ),
                "authority": "delegate",
                "audience": "senior_staff",
                "mission": "weekly-churn-report",
                "goal_brief": {
                    "business_question": (
                        "Why did weekly churn spike above the 4-week baseline?"
                    ),
                    "ds_problem_statement": (
                        "Churn driver triage with automated dispatch."
                    ),
                    "comparison_baseline": "prior four-week rolling baseline",
                    "decision_to_make": (
                        "assign owner and select remediation action"
                    ),
                    "expected_effort": "M",
                },
                "required_deliverables": [
                    {
                        "type": "exec_brief",
                        "audience": "executive",
                        "format": "md",
                    },
                ],
                "created_by": "user",
            },
        ),
    )
    return store


def _seed_work_object(
    workspace_dir: Path,
    task_id: str,
    work_object_id: str,
) -> SqliteWorkObjectStore:
    now = datetime(2026, 4, 16, 9, 5, tzinfo=UTC)
    wo_store = SqliteWorkObjectStore.for_workspace(str(workspace_dir))
    tc_store = SqliteTaskContractStore.for_workspace(str(workspace_dir))
    ids = _SeedIds(task_id, work_object_id)
    CreateWorkObjectUseCase(
        wo_store,
        tc_store,
        _SeedClock(now),
        ids,
    ).execute(
        CreateWorkObjectDTO(
            task_contract_id=task_id,
            title="Weekly churn report dispatch",
            request_source="electron",
            requestor_id="operator",
            requestor_display="Operator (E2E seed)",
            original_text=(
                "Dispatch the weekly churn report to Slack "
                "and create a Jira follow-up ticket."
            ),
            channel="electron",
            tags=["churn", "weekly", "e2e-seed"],
        ),
    )
    return wo_store


def _seed_integration_events(
    wo_store: SqliteWorkObjectStore,
    work_object_id: str,
) -> None:
    base = datetime(2026, 4, 16, 9, 10, tzinfo=UTC)
    events = [
        IntegrationEvent(
            event_id="IE-seed-slack-001",
            work_object_id=work_object_id,
            system="slack",
            action="post_message",
            request_payload_hash="seed-hash-slack",
            idempotency_key="seed-idem-slack-001",
            status=IntegrationEventStatus.SUCCESS,
            external_ref=None,
            attempt=1,
            latency_ms=120,
            started_at=base,
            finished_at=base + timedelta(milliseconds=120),
        ),
        IntegrationEvent(
            event_id="IE-seed-jira-001",
            work_object_id=work_object_id,
            system="jira",
            action="create_issue",
            request_payload_hash="seed-hash-jira",
            idempotency_key="seed-idem-jira-001",
            status=IntegrationEventStatus.SUCCESS,
            external_ref=None,
            attempt=1,
            latency_ms=340,
            started_at=base + timedelta(seconds=5),
            finished_at=base + timedelta(seconds=5, milliseconds=340),
        ),
    ]
    for event in events:
        wo_store.record_event(event)


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
    _seed_task_contract(
        workspace_dir,
        args.session_id,
        args.task_id,
    )
    wo_store = _seed_work_object(
        workspace_dir,
        args.task_id,
        args.work_object_id,
    )
    _seed_integration_events(wo_store, args.work_object_id)

    print(
        "seeded "
        f"config={config_path} workspace={workspace_dir} "
        f"session={args.session_id} task={args.task_id} "
        f"work_object={args.work_object_id}"
    )


if __name__ == "__main__":
    main()
