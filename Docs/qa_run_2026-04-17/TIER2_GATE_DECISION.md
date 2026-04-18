# Tier 2 Gate Decision — Feature Behavior Test

**작성일**: 2026-04-17
**판정자**: Main orchestrator (D18 Release Readiness Auditor가 최종 판정 시 상위 결론)
**판정 시점**: B05~B12 8개 agent 완료 직후
**판정 범위**: Tier 2 Hard Gate (계획서 §10.1) + No-Go Triggers (§10.3)

---

## 1. 실행 현황

| Agent | 상태 | 핵심 메트릭 | 주요 발견 |
|:-----:|:----:|------------|----------|
| **B05** Agent Core & Hook Chain | PASS | 30/30 hook fire, 0 dead hook, 212 pytest pass | Doc drift D5-1: 계획서 `<ds:review_artifacts>` vs 코드 `<!-- DS_REVIEW_ARTIFACTS -->` |
| **B06** Tools Registry Fuzz | PASS | 86/86 tool, 0 critical failure, 10/10 sandbox block, SQL injection 무력화 | 26/26 scope pytest |
| **B07** Memory & Semantic | PASS | 7/7 path, FTS5 precision@10 = 1.00, 88/89 pytest | PRE-1 재확인 (스코프 외); NegativeKnowledge proposal payload 스키마 risk (auto_apply=False라 즉시 영향 없음) |
| **B08** Task Contract / Verifier / Decision OS | PASS | 8/8 path, 4-layer verifier 전수 경로, 10-dim delta 0.642, RunDiff determinism sha256 일치, 69/73 pytest (4 env-fail) | NOTE-B08-1: Promotion Gate가 계획서보다 **더 엄격** (staging도 3-of-3 요구). ENV-2: pandas/numpy 미설치 4 fail |
| **B09** Autonomy Control Plane | PASS | 81/84 strict authority matrix (83/84 w/ runtime overlay), 24h incident 경계 정확, FREEZE writes 9/9 block | B09-F2: FREEZE 모드 read(diagnostic sql) 일부 AUTO — 안전 holes 아니나 spec/code gap |
| **B10** Comms / Workflow / Export | PASS | 30/30 matrix cell, 한국어 roundtrip equal, real adapter call 0건, DLQ replay ok | RC-5: Slack/Jira/Confluence/Notion/Git adapter 내 kill-switch 없음 (hub policy에 의존) |
| **B11** Portfolio / Learning Governance | **8/9 PASS, Path 8 FAIL** | max_active_slots/auto-deprecation/PriorityCalculator informational 전부 enforce; Rollback atomicity **NON_ATOMIC_PARTIAL** | **FAIL-B11-8**: `RollbackPromotionUseCase`가 `save_item` + `save_deprecation_record`를 single txn으로 감싸지 않음. 중간 실패 시 audit trail split |
| **B12** Provider Router & Cost | PASS | 12/12 provider roundtrip, cost accuracy 1.0, OAuth 2, real API call 0건 | 6 non-blocking findings (streaming Anthropic/Codex만, gemini pricing default, codex subprocess timeout 300s vs 120s 등) |

---

## 2. Hard Gate 판정 (계획서 §10.1 "Tier 2")

| 기준 | 상태 | 증거 |
|------|:----:|------|
| 30 hook 전부 fire 확인 | ✅ | B05: `build_hook_registry` 전수 fire trace (`B05_fire_trace.jsonl`, 181 rows) |
| 86 tool 전부 호출 가능 (계약 스키마 통과) | ✅ | B06: AST 86 ↔ Registry 86 일치, 0 critical failure |
| 4-layer verifier 전부 경로 실행 | ✅ | B08: L1/L2/L3/L4 독립 fail 경로 + happy path 5건 `B08_verdict_samples/` |
| 개별 도구 오류율 <5% (soft-fail 한도) | ✅ | B06 430 cell 중 critical 0; B08의 pandas/numpy ENV-2 4건은 환경 문제로 격리 |

**Hard Gate 4/4 PASS.**

---

## 3. No-Go Trigger 심사 (계획서 §10.3)

| Trigger | 발생? | 판단 근거 |
|---------|:-----:|----------|
| Tier 1 hard gate 실패 | ❌ | Tier 1 Round 2 전수 pass |
| Tier 2 security/auth critical 실패 (샌드박스 탈출·시크릿 노출·PII 누설) | ❌ | B06 sandbox 10/10 block, SQL injection 무력화; B10 real adapter call 0건; B12 real API call 0건. Tier 1 A02 이미 PII 7/7 통과 |
| D17 no-change regression delta ≠ 0 | ⏳ | Tier 4에서 판정 |
| 3-Tier 인터페이스 결과 불일치 | ⏳ | Tier 3 C13에서 판정 |
| 30 hook 중 dead hook 존재 | ❌ | B05: 30/30 fire 확인 |

**No-Go Trigger 0건 발생.** (Tier 3/4 영역은 각 Tier에서 재심사)

---

## 4. B11 Path 8 분류 (최대 쟁점)

`RollbackPromotionUseCase` 비원자성은 명백한 correctness 결함이나, 계획서 §10.3 **No-Go Triggers에 명시된 항목은 아니다** (security/auth/regression/parity/dead-hook).

**분류**: **Feature-level defect, Fix Sprint Round 3 candidate. Tier 2 Hard Gate 통과를 차단하지 않음.**

근거:
- Tier 2 Hard Gate(§10.1)는 "커버리지·호출 가능성" 기준 (hook fire / tool 호출 / verifier 경로). B11 Path 8은 이 기준에 해당하지 않음.
- §10.3 No-Go는 security/시크릿/회귀/parity/dead-hook의 5 구체 trigger로 제한. Rollback 비원자성은 포함되지 않음.
- 단, **상용 배포 전 반드시 해결** 필요 — 감사 추적 분할은 거버넌스 요구사항 위반. Tier 3 진입 중 병렬로 Fix Sprint Round 3 착수 권장.

**Fix Sprint Round 3 권장 범위**:
- **FAIL-B11-8**: `RollbackPromotionUseCase`에 use-case-level transaction 도입 또는 보상 트랜잭션(compensating revert). (HIGH PRIORITY)
- **NOTE-B08-1**: Promotion Gate staging 승인 로직이 계획서보다 엄격 → 계획서 문구 조정(코드 유지) 권장.
- **RC-5**: Slack/Jira/Confluence/Notion/Git adapter에 in-adapter kill-switch 추가 검토 (방어 심도).
- **D5-1 (B05)**: `<ds:review_artifacts>` → `<!-- DS_REVIEW_ARTIFACTS {...} -->` 문구 조정.
- **B11 drift D1~D4**: 계획서 문구와 코드 정렬.
- **ENV-2**: B08 pandas/numpy 미설치로 4 fail — 테스트 환경 dev extras 보정.

---

## 5. 최종 판정

**Tier 2 Gate: PASS (with FAIL-B11-8 documented for Fix Sprint Round 3).**

- Hard Gate 4/4 통과.
- No-Go Trigger 0건.
- B11 Path 8 FAIL은 §10.3 범주 밖, Fix Sprint Round 3로 이관.
- **Tier 3 진입 가능** — C13 Parity / C14 Gold Tasks / C15 Packaging 병렬 스폰 대상.

---

## 6. 이월 이슈 (Tier 3~4 또는 Fix Sprint Round 3)

| ID | 출처 | 유형 | 이관 대상 |
|----|------|------|----------|
| FAIL-B11-8 | B11 Path 8 | 기능 결함 | **Fix Sprint Round 3 (HIGH)** |
| NOTE-B08-1 | B08 Promotion Gate | 문서 불일치 | Fix Sprint Round 3 (문서) |
| RC-5 | B10 | 아키텍처 검토 | Fix Sprint Round 3 또는 post-beta |
| D5-1 | B05 doc drift | 문서 | Fix Sprint Round 3 (문서) |
| B11-D1~D4 | B11 | 문서/maturity | Fix Sprint Round 3 (문서) + v2 spec |
| ENV-2 | B08 환경 | 테스트 env | 유지보수 스프린트 |
| B09-F2 | B09 | spec/code gap | Fix Sprint Round 3 검토 |
| B12 findings (6건) | B12 | non-blocking | post-beta |
| PRE-1 | B07 재확인 | 기존 결함 | 별도 스프린트 (계속 이월) |
| PRE-2 (mypy 3건) | 계속 | 기존 결함 | 유지보수 스프린트 |

---

## 7. 기록 이력

| 시각 | 이벤트 | 비고 |
|------|--------|------|
| 2026-04-17 | B05/B06/B07/B08 1차 배치 병렬 완료 | 전원 pass |
| 2026-04-17 | B09/B12 2차 배치 pass | — |
| 2026-04-17 | B10/B11 2차 배치 — rate limit 도달 | B10은 FINAL.json까지 완료, B11은 증거+리포트까지 완료·FINAL.json만 orchestrator가 재구성 |
| 2026-04-17 | Tier 2 Gate PASS 판정 | Fix Sprint Round 3 권고 첨부 |

---

*D18 Release Readiness Auditor가 Tier 3/4 종료 후 이 문서를 `RELEASE_GATE_DECISION.md`에 병합할 때 상위 결론으로 반영한다.*
