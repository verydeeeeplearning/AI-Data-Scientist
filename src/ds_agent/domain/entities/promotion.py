"""Decision OS promotion-gate entities."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TargetStage = Literal["staging", "production", "canary"]
PolicyCheckStatus = Literal["pass", "warn", "fail", "skipped"]
ApprovalRole = Literal["DS", "Lead", "MLOps"]
ApprovalStatus = Literal["pending", "approved", "rejected"]
ChainState = Literal[
    "pending_DS",
    "pending_Lead",
    "pending_MLOps",
    "approved",
    "rejected",
    "expired",
]


class PolicyCheck(BaseModel):
    """One machine-evaluated policy gate outcome."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    status: PolicyCheckStatus
    detail: str = Field(min_length=1)


class ApprovalStep(BaseModel):
    """One assigned approver within the promotion chain."""

    model_config = ConfigDict(frozen=True)

    role: ApprovalRole
    approver: str = Field(min_length=1)
    status: ApprovalStatus = "pending"
    decided_at: datetime | None = None
    note: str | None = None


class RollbackPlan(BaseModel):
    """Validated rollback-plan document consumed by the promotion gate."""

    model_config = ConfigDict(frozen=True)

    previous_champion_model_id: str = Field(min_length=1)
    traffic_shift_procedure: str = Field(min_length=1)
    health_check_queries: list[str] = Field(min_length=1)
    estimated_rollback_time_sec: int = Field(gt=0)
    owner: str = Field(min_length=1)


class PromotionDecision(BaseModel):
    """Persisted promotion decision with policy evidence and approval state."""

    model_config = ConfigDict(frozen=True)

    decision_id: str = Field(min_length=1)
    candidate_run_id: str = Field(min_length=1)
    candidate_model_id: str = Field(min_length=1)
    target_stage: TargetStage
    policy_checks: list[PolicyCheck] = Field(default_factory=list)
    approvals: list[ApprovalStep] = Field(default_factory=list)
    chain_state: ChainState
    rollback_plan_ref: str = Field(min_length=1)
    created_at: datetime
    resolved_at: datetime | None = None

    def current_step(self) -> ApprovalStep | None:
        """Return the currently pending approval step."""

        mapping: dict[ChainState, ApprovalRole] = {
            "pending_DS": "DS",
            "pending_Lead": "Lead",
            "pending_MLOps": "MLOps",
            "approved": "MLOps",
            "rejected": "DS",
            "expired": "DS",
        }
        if not self.chain_state.startswith("pending_"):
            return None
        role = mapping[self.chain_state]
        for step in self.approvals:
            if step.role == role:
                return step
        return None

    def approve(self, approver: str, note: str, decided_at: datetime) -> PromotionDecision:
        """Approve the current step and advance the chain."""

        current = self.current_step()
        if current is None:
            raise ValueError("Promotion decision is not pending approval.")
        if current.approver != approver:
            raise ValueError(f"Approval must be completed by {current.approver}, not {approver}.")
        updated_steps = [
            (
                step.model_copy(
                    update={
                        "status": "approved",
                        "decided_at": decided_at,
                        "note": note,
                    }
                )
                if step.role == current.role
                else step
            )
            for step in self.approvals
        ]
        next_state: ChainState
        resolved_at: datetime | None = None
        if current.role == "DS":
            next_state = "pending_Lead"
        elif current.role == "Lead":
            next_state = "pending_MLOps"
        else:
            next_state = "approved"
            resolved_at = decided_at
        return self.model_copy(
            update={
                "approvals": updated_steps,
                "chain_state": next_state,
                "resolved_at": resolved_at,
            }
        )

    def reject(self, approver: str, reason: str, decided_at: datetime) -> PromotionDecision:
        """Reject the current step and close the chain."""

        current = self.current_step()
        if current is None:
            raise ValueError("Promotion decision is not pending approval.")
        if current.approver != approver:
            raise ValueError(f"Rejection must be completed by {current.approver}, not {approver}.")
        updated_steps = [
            (
                step.model_copy(
                    update={
                        "status": "rejected",
                        "decided_at": decided_at,
                        "note": reason,
                    }
                )
                if step.role == current.role
                else step
            )
            for step in self.approvals
        ]
        return self.model_copy(
            update={
                "approvals": updated_steps,
                "chain_state": "rejected",
                "resolved_at": decided_at,
            }
        )
