"""Domain skill pack loader for PLAN 17 Phase 5."""

from __future__ import annotations

from pathlib import Path

from ds_agent.skills.hub import SkillHub


class DomainPackLoader:
    """Load domain-specific skill directories and guardrails."""

    def __init__(self) -> None:
        self._base_dir = Path(__file__).resolve().parent
        self._builtin_dir = self._base_dir / "builtin"
        self._shared_dir = self._base_dir / "shared"
        self._domain_dir = self._base_dir / "domain"
        self._pack_dirs = {
            "finance": self._domain_dir / "finance",
            "healthcare": self._domain_dir / "healthcare",
            "marketing": self._domain_dir / "marketing",
        }
        self._default_skill_names = {
            "finance": ["financial-ts-modeling", "risk-metric-suite", "look-ahead-bias-guard"],
            "healthcare": ["survival-analysis", "hipaa-compliance"],
            "marketing": ["uplift-modeling", "attribution-modeling", "ltv-prediction"],
        }

    def build_skill_hub(self, domain_packs: list[str], *, include_builtin: bool = True) -> SkillHub:
        directories: list[Path] = []
        if include_builtin:
            directories.append(self._builtin_dir)
            directories.append(self._shared_dir)
        directories.extend(self.get_skill_directories(domain_packs))
        return SkillHub.from_directories(directories)

    def get_skill_directories(self, domain_packs: list[str]) -> list[Path]:
        return [self._pack_dirs[pack] for pack in domain_packs if pack in self._pack_dirs]

    def get_default_skill_names(self, domain_packs: list[str]) -> list[str]:
        names: list[str] = []
        for pack in domain_packs:
            names.extend(self._default_skill_names.get(pack, []))
        return names

    def validate_guardrails(self, domain_pack: str, code: str, task_hint: str = "") -> list[str]:
        """Return guardrail warnings for a specific domain pack."""
        normalized_code = code.lower()
        normalized_hint = task_hint.lower()
        warnings: list[str] = []

        if domain_pack == "finance":
            if (
                "train_test_split" in normalized_code
                and (
                    "time series" in normalized_hint
                    or "forecast" in normalized_hint
                    or "return" in normalized_hint
                )
            ):
                warnings.append(
                    "Finance time-series tasks should use walk-forward validation, "
                    "not random train_test_split."
                )
            if "future" in normalized_code or "lead(" in normalized_code:
                warnings.append(
                    "Finance modeling must avoid look-ahead bias and future price references."
                )

        if domain_pack == "healthcare" and "patient_name" in normalized_code:
            warnings.append(
                "Healthcare workflows should de-identify HIPAA identifiers before analysis."
            )

        if (
            domain_pack == "marketing"
            and "uplift" in normalized_hint
            and "randomized" not in normalized_code
        ):
            warnings.append(
                "Uplift analysis should confirm treatment/control design and SUTVA assumptions."
            )

        return warnings
