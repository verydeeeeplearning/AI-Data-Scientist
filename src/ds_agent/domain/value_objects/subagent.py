"""Subagent value objects for isolated helper-agent execution."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

from ds_agent.domain.value_objects.budget import BudgetPolicy

SubagentRole = Literal["builder", "validator", "reporter", "operator"]
SessionTarget = Literal["main", "isolated", "current"]

_VALID_ROLES = frozenset({"builder", "validator", "reporter", "operator"})
_VALID_SESSION_TARGETS = frozenset({"main", "isolated", "current"})
_ROLE_INSTRUCTIONS: dict[SubagentRole, str] = {
    "builder": (
        "Produce or revise the concrete analysis artifact. Prefer actionable output over "
        "discussion, and state any assumptions explicitly."
    ),
    "validator": (
        "Validate the proposed result. Check methodology errors, data leakage, unsupported "
        "claims, and overfitting risks before approving it."
    ),
    "reporter": (
        "Summarize the analysis for the intended audience. Highlight the decision-relevant "
        "findings, confidence level, and limitations."
    ),
    "operator": (
        "Monitor operational health and incident signals. Report anomalies, likely causes, "
        "and the next corrective action."
    ),
}


@dataclass(slots=True)
class SubagentSpec:
    """Execution spec for one isolated subagent run."""

    role: SubagentRole
    prompt: str
    budget_usd: float = 2.0
    tools: list[str] | None = None
    model: str | None = None
    timeout_seconds: float = 180.0
    session_target: SessionTarget = "isolated"
    context: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.role not in _VALID_ROLES:
            raise ValueError(f"Unsupported subagent role: {self.role}")
        if not self.prompt.strip():
            raise ValueError("Subagent prompt is required")
        if self.budget_usd <= 0:
            raise ValueError("Subagent budget_usd must be > 0")
        if self.timeout_seconds <= 0:
            raise ValueError("Subagent timeout_seconds must be > 0")
        if self.session_target not in _VALID_SESSION_TARGETS:
            raise ValueError(f"Unsupported session target: {self.session_target}")
        if self.model is not None:
            self.model = self.model.strip() or None
        if self.tools is not None:
            seen: set[str] = set()
            normalized: list[str] = []
            for tool_name in self.tools:
                name = str(tool_name).strip()
                if name and name not in seen:
                    seen.add(name)
                    normalized.append(name)
            self.tools = normalized
        self.context = self.context.strip()

    @property
    def role_instruction(self) -> str:
        """Return the DS-specialized instruction prefix for this role."""
        return _ROLE_INSTRUCTIONS[self.role]

    def build_prompt(self, *, context_summary: str | None = None) -> str:
        """Build the instruction payload sent to the isolated subagent."""
        parts = [
            f"Subagent role: {self.role}",
            self.role_instruction,
        ]
        merged_context = "\n\n".join(
            item.strip()
            for item in [self.context, context_summary or ""]
            if item and item.strip()
        )
        if merged_context:
            parts.append(f"Parent context:\n{merged_context}")
        if self.metadata:
            details = ", ".join(f"{key}={value}" for key, value in sorted(self.metadata.items()))
            parts.append(f"Run metadata: {details}")
        parts.append(f"Assigned task:\n{self.prompt.strip()}")
        return "\n\n".join(parts)

    def build_budget_policy(self, default: BudgetPolicy | None = None) -> BudgetPolicy:
        """Build a run-local budget policy derived from the parent default."""
        base = replace(default) if default is not None else BudgetPolicy()
        base.max_cost_usd = self.budget_usd
        base.max_wall_time_seconds = self.timeout_seconds
        return base
