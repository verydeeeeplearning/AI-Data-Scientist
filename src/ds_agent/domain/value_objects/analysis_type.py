"""Domain value object for analysis type routing."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class AnalysisType:
    """Structured analysis type classification."""

    type: str
    required_skills: list[str] = field(default_factory=list)
    required_guards: list[str] = field(default_factory=list)
    typical_artifacts: list[str] = field(default_factory=list)
    workflow_template: str = ""
    workflow_stages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
