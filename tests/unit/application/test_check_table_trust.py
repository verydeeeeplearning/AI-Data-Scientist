from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from ds_agent.memory.semantic.application.check_table_trust import CheckTableTrustUseCase
from ds_agent.memory.semantic.domain.trust import RefreshSLA, TableTrust, TrustGrade


class _TrustRepo:
    def __init__(self, tables: list[TableTrust]) -> None:
        self._tables = {table.fqtn: table for table in tables}

    def get(self, fqtn: str) -> TableTrust | None:
        return self._tables.get(fqtn)

    def bulk_get(self, fqtns: Sequence[str]) -> list[TableTrust]:
        return [self._tables[fqtn] for fqtn in fqtns if fqtn in self._tables]

    def save(self, table: TableTrust) -> None:
        self._tables[table.fqtn] = table


def _table(fqtn: str, grade: TrustGrade) -> TableTrust:
    return TableTrust(
        fqtn=fqtn,
        grade=grade,
        owner="growth_team",
        description="table",
        refresh=RefreshSLA(cadence="daily", max_staleness_minutes=1440),
        grade_rationale="ok",
        last_audited=date(2026, 4, 1),
    )


def test_check_table_trust_returns_allow_for_gold() -> None:
    result = CheckTableTrustUseCase(_TrustRepo([_table("prod.good", TrustGrade.GOLD)])).execute(
        ["prod.good"]
    )

    assert result.action == "allow"


def test_check_table_trust_returns_caveat_for_silver() -> None:
    result = CheckTableTrustUseCase(
        _TrustRepo([_table("prod.silver", TrustGrade.SILVER)])
    ).execute(["prod.silver"])

    assert result.action == "caveat"


def test_check_table_trust_returns_confirm_for_bronze() -> None:
    result = CheckTableTrustUseCase(
        _TrustRepo([_table("prod.bronze", TrustGrade.BRONZE)])
    ).execute(["prod.bronze"])

    assert result.action == "confirm"


def test_check_table_trust_returns_block_for_missing_or_untrusted() -> None:
    result = CheckTableTrustUseCase(
        _TrustRepo([_table("prod.untrusted", TrustGrade.UNTRUSTED)])
    ).execute(["prod.untrusted", "missing.table"])

    assert result.action == "block"
    assert "missing.table" in result.missing_tables
