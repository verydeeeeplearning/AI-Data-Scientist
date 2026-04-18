"""Use case for trust-policy evaluation over referenced tables."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from ds_agent.memory.semantic.application.dtos import TableTrustDecisionDTO
from ds_agent.memory.semantic.application.ports import TableTrustRepository
from ds_agent.memory.semantic.domain.trust import TrustGrade


class CheckTableTrustUseCase:
    """Decide whether tables can be used automatically."""

    def __init__(self, trust_repo: TableTrustRepository) -> None:
        self._trust_repo = trust_repo

    def execute(
        self,
        fqtns: Sequence[str],
        *,
        allow_untrusted: bool = False,
    ) -> TableTrustDecisionDTO:
        unique_fqtns = list(dict.fromkeys(fqtns))
        tables = self._trust_repo.bulk_get(unique_fqtns)
        found = {table.fqtn for table in tables}
        missing = [fqtn for fqtn in unique_fqtns if fqtn not in found]
        warnings: list[str] = []

        if missing:
            warnings.append(f"missing trust metadata: {', '.join(missing)}")

        if missing and not allow_untrusted:
            return TableTrustDecisionDTO(
                action="block",
                tables=tables,
                missing_tables=missing,
                warnings=warnings,
            )

        grades = {table.grade for table in tables}
        action: Literal["allow", "caveat", "confirm", "block"]
        if TrustGrade.UNTRUSTED in grades and not allow_untrusted:
            warnings.append("untrusted table referenced")
            action = "block"
        elif TrustGrade.BRONZE in grades or (TrustGrade.UNTRUSTED in grades and allow_untrusted):
            warnings.append("manual confirmation required for bronze/untrusted table")
            action = "confirm"
        elif TrustGrade.SILVER in grades:
            warnings.append("silver-grade table requires caveat")
            action = "caveat"
        else:
            action = "allow"

        return TableTrustDecisionDTO(
            action=action,
            tables=tables,
            missing_tables=missing,
            warnings=warnings,
        )
