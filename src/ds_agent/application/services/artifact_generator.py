"""Application service for generating non-code communication artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from ds_agent.domain.value_objects.artifact import ArtifactSpec, ArtifactType


@dataclass(frozen=True, slots=True)
class ArtifactOutput:
    """Generated artifact payload."""

    content: str
    format: str
    metadata: dict[str, object]


class ArtifactGenerator:
    """Generate artifact content from structured analysis output."""

    def generate(self, spec: ArtifactSpec, data: dict[str, object]) -> ArtifactOutput:
        if spec.artifact_type == ArtifactType.MEMO:
            content = self._memo(data)
        elif spec.artifact_type == ArtifactType.SQL:
            content = self._sql_artifact(data)
        elif spec.artifact_type == ArtifactType.SLIDE:
            content = self._slide_spec(data)
        elif spec.artifact_type == ArtifactType.MODEL_CARD:
            content = self._model_card(data)
        else:
            raise ValueError(f"Unsupported artifact type: {spec.artifact_type.value}")
        return ArtifactOutput(content=content, format=spec.format, metadata=dict(spec.metadata))

    @staticmethod
    def _as_list(value: object) -> list[object]:
        """Return value if it is a list, else []. Centralises dict[str, object] narrowing."""
        return value if isinstance(value, list) else []

    @staticmethod
    def _memo(data: dict[str, object]) -> str:
        findings = ArtifactGenerator._as_list(data.get("key_findings", []))
        recommendations = ArtifactGenerator._as_list(data.get("recommendations", []))
        risks = ArtifactGenerator._as_list(data.get("risks", []))
        next_steps = ArtifactGenerator._as_list(data.get("next_steps", []))
        return (
            "\n".join(
                [
                    "# Executive Memo",
                    "",
                    "## Summary",
                    str(data.get("summary", "")),
                    "",
                    "## Key Findings",
                    *[f"- {item}" for item in findings if isinstance(item, str)],
                    "",
                    "## Recommendations",
                    *[f"- {item}" for item in recommendations if isinstance(item, str)],
                    "",
                    "## Risks",
                    *[f"- {item}" for item in risks if isinstance(item, str)],
                    "",
                    "## Next Steps",
                    *[f"- {item}" for item in next_steps if isinstance(item, str)],
                ]
            ).strip()
            + "\n"
        )

    @staticmethod
    def _sql_artifact(data: dict[str, object]) -> str:
        sql = str(data.get("sql", "")).strip()
        description = str(data.get("description", "")).strip()
        schema_yml = str(data.get("schema_yml", "")).strip()
        tests = data.get("tests", [])
        lines = ["-- SQL Artifact", f"-- {description}", "", sql, ""]
        if schema_yml:
            lines.extend(["-- schema.yml", schema_yml, ""])
        if isinstance(tests, list) and tests:
            lines.append("-- tests")
            lines.extend(f"-- - {item}" for item in tests)
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _slide_spec(data: dict[str, object]) -> str:
        sections = ArtifactGenerator._as_list(data.get("sections", []))
        lines = ["# Slide Spec", ""]
        for index, section in enumerate(sections, start=1):
            if not isinstance(section, dict):
                continue
            title = str(section.get("title", f"Slide {index}"))
            bullets = section.get("bullets", [])
            lines.extend([f"## Slide {index}: {title}"])
            if isinstance(bullets, list):
                lines.extend(f"- {bullet}" for bullet in bullets if isinstance(bullet, str))
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _model_card(data: dict[str, object]) -> str:
        return (
            "\n".join(
                [
                    "# Model Card",
                    "",
                    f"- Model: {data.get('model_name', 'unknown')}",
                    f"- Use case: {data.get('use_case', 'n/a')}",
                    f"- Inputs: {data.get('inputs', [])}",
                    f"- Metrics: {data.get('metrics', {})}",
                    f"- Limitations: {data.get('limitations', [])}",
                ]
            ).strip()
            + "\n"
        )
