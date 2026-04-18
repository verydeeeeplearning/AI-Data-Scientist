"""Shared scenario fixtures for C13 Phase 3 parity harness.

3 scenarios exercised across 3 channels (CLI / Telegram / Electron).
The goal text, audience, authority switches and CAUTION tool names are
channel-agnostic — this module is the single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    """One parity scenario."""

    scenario_id: str
    goal: str
    audience: str
    authority_mode: str | None
    caution_tool: str | None
    expect_delivery_pack: bool
    notes: str


P01 = Scenario(
    scenario_id="P-01",
    goal="tips.csv의 total_bill 예측 — 데이터 로드와 프로파일링, baseline 선형 회귀 모델, 평가, 최종 DeliveryPack(PDF)을 생성하세요.",
    audience="Peer",
    authority_mode=None,  # default supervised
    caution_tool=None,
    expect_delivery_pack=True,
    notes="기본 분석 → 보고서 Happy path",
)

P02 = Scenario(
    scenario_id="P-02",
    goal="현재 세션의 Authority를 Supervised에서 Delegate로 전환하고, 실험 기록 삭제(가상) CAUTION 도구를 호출해 승인 플로우를 트리거하세요.",
    audience="Peer",
    authority_mode="delegate",
    caution_tool="experiment_log.delete",
    expect_delivery_pack=False,
    notes="자율 모드 전환 + CAUTION approval",
)

P03 = Scenario(
    scenario_id="P-03",
    goal="세션에서 관찰한 반복 패턴을 LearningInbox 항목으로 추출하고, 하나를 review·approve 후 promote. 이후 2회 eval 실패 → auto-deprecate를 시뮬레이션하세요.",
    audience="Peer",
    authority_mode=None,
    caution_tool=None,
    expect_delivery_pack=False,
    notes="학습 거버넌스 사이클",
)

ALL_SCENARIOS: list[Scenario] = [P01, P02, P03]


def scenario_by_id(sid: str) -> Scenario:
    for s in ALL_SCENARIOS:
        if s.scenario_id == sid:
            return s
    raise KeyError(sid)
