"""Audience-specific report adaptation."""

from __future__ import annotations

import re
from typing import Any

from ds_agent.domain.value_objects.artifact import AudienceProfile


class AudienceAdapter:
    """Adapt structured analysis content to a target audience."""

    def adapt(self, content: dict[str, Any] | str, audience: AudienceProfile | str) -> str:
        profile = (
            audience if isinstance(audience, AudienceProfile) else AudienceProfile(role=audience)
        )
        normalized = self._normalize_content(content)
        role = profile.role.lower()
        if role == "executive":
            return self._to_executive(normalized)
        if role == "technical":
            return self._to_technical(normalized)
        if role == "pm":
            return self._to_pm(normalized)
        if role == "slack":
            return self._to_slack(normalized)
        return self._to_technical(normalized)

    @staticmethod
    def _normalize_content(content: dict[str, Any] | str) -> dict[str, Any]:
        if isinstance(content, dict):
            return content
        text = content.strip()
        paragraphs = [
            paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()
        ]
        summary = paragraphs[0] if paragraphs else text
        findings = [
            line.strip("-* ") for line in text.splitlines() if line.strip().startswith(("-", "*"))
        ]
        return {
            "summary": summary,
            "key_findings": findings[:5],
            "recommendations": findings[5:8],
            "risks": [],
            "next_steps": [],
            "full_text": text,
        }

    @staticmethod
    def _to_executive(content: dict[str, Any]) -> str:
        findings = content.get("key_findings", [])
        recommendations = content.get("recommendations", [])
        return (
            "\n".join(
                [
                    "# Executive Memo",
                    "",
                    "## So What",
                    str(content.get("summary", "")),
                    "",
                    "## What Changed",
                    *[f"- {item}" for item in findings[:3] if isinstance(item, str)],
                    "",
                    "## Recommended Action",
                    *[f"- {item}" for item in recommendations[:2] if isinstance(item, str)],
                ]
            ).strip()
            + "\n"
        )

    @staticmethod
    def _to_technical(content: dict[str, Any]) -> str:
        return (
            "\n".join(
                [
                    "# Technical Report",
                    "",
                    "## Summary",
                    str(content.get("summary", "")),
                    "",
                    "## Findings",
                    *[
                        f"- {item}"
                        for item in content.get("key_findings", [])
                        if isinstance(item, str)
                    ],
                    "",
                    "## Recommendations",
                    *[
                        f"- {item}"
                        for item in content.get("recommendations", [])
                        if isinstance(item, str)
                    ],
                    "",
                    "## Risks",
                    *[f"- {item}" for item in content.get("risks", []) if isinstance(item, str)],
                ]
            ).strip()
            + "\n"
        )

    @staticmethod
    def _to_pm(content: dict[str, Any]) -> str:
        next_steps = content.get("next_steps", [])
        recommendations = content.get("recommendations", [])
        return (
            "\n".join(
                [
                    "# PM Brief",
                    "",
                    "## Context",
                    str(content.get("summary", "")),
                    "",
                    "## Decisions Needed",
                    *[f"- {item}" for item in recommendations[:3] if isinstance(item, str)],
                    "",
                    "## Next Steps",
                    *[f"- {item}" for item in next_steps[:3] if isinstance(item, str)],
                ]
            ).strip()
            + "\n"
        )

    @staticmethod
    def _to_slack(content: dict[str, Any]) -> str:
        bullets = [str(content.get("summary", ""))]
        bullets.extend(
            str(item) for item in content.get("key_findings", [])[:2] if isinstance(item, str)
        )
        return "\n".join(f"- {bullet}" for bullet in bullets if bullet).strip() + "\n"
