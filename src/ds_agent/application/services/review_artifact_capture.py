"""Parse hidden shared-skill review artifacts from final assistant responses."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.domain.entities.review_artifact import ReviewSkillName

_CAPTURE_BLOCK_RE = re.compile(
    r"<!--\s*DS_REVIEW_ARTIFACTS\s*(\{.*?\})\s*-->",
    re.DOTALL,
)


class ReviewArtifactCaptureItem(BaseModel):
    """One structured review artifact emitted in a hidden response block."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1)
    skill_name: ReviewSkillName
    summary: str = Field(min_length=1)
    artifact: dict[str, object] = Field(default_factory=dict)
    narrative: str | None = None


class ReviewArtifactCaptureEnvelope(BaseModel):
    """One hidden capture envelope embedded in the assistant response."""

    model_config = ConfigDict(frozen=True)

    artifacts: list[ReviewArtifactCaptureItem] = Field(default_factory=list)


class ReviewArtifactCaptureParseResult(BaseModel):
    """Parsed capture entries plus the cleaned user-facing response."""

    model_config = ConfigDict(frozen=True)

    cleaned_response: str
    captures: list[ReviewArtifactCaptureItem] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def review_artifact_capture_instructions() -> str:
    """Return the system-prompt contract for hidden review-artifact capture."""

    return (
        "## Decision OS Review Artifact Capture\n"
        "- When you make a structured Decision OS judgment for a specific experiment run "
        "using `backtesting`, `causal-assumption-check`, `uncertainty-quantification`, "
        "or `retrain-vs-rollback`, append one hidden HTML comment at the very end.\n"
        "- Use exactly this shape: "
        '`<!-- DS_REVIEW_ARTIFACTS {"artifacts": [{"run_id": "run-123", '
        '"skill_name": "backtesting", "summary": "...", "narrative": "optional", '
        '"artifact": {...}}]} -->`.\n'
        "- Only emit the hidden block when you know the concrete Decision OS experiment "
        "run id and can populate the typed fields faithfully.\n"
        "- Keep the visible answer human-readable. The hidden block is machine-readable only."
    )


def extract_review_artifact_captures(response: str) -> ReviewArtifactCaptureParseResult:
    """Extract hidden review-artifact blocks and strip them from the response."""

    captures: list[ReviewArtifactCaptureItem] = []
    errors: list[str] = []
    for raw_payload in _CAPTURE_BLOCK_RE.findall(response):
        try:
            parsed = json.loads(raw_payload)
            envelope = ReviewArtifactCaptureEnvelope.model_validate(parsed)
            captures.extend(envelope.artifacts)
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(str(exc))

    cleaned = _CAPTURE_BLOCK_RE.sub("", response)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return ReviewArtifactCaptureParseResult(
        cleaned_response=cleaned,
        captures=captures,
        errors=errors,
    )
