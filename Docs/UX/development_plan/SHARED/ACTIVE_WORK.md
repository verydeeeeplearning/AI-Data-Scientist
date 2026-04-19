# ACTIVE_WORK 진행 중 작업 (Lock)

현재 작업 중인 agent lock 은 active 항목만 유지한다. 완료되었거나 더 이상 touch 하지 않는 lock 은 제거한다.

---

## 작성 형식

```markdown
- **PLAN**: <plan path>
  **Owner**: <agent-id>
  **Started**: YYYY-MM-DDTHH:MM:SSZ
  **Worktree**: <path>
  **예상 종료**: YYYY-MM-DDTHH:MMZ
  **Files (예상 touch)**:
    - `path/to/file1`
    - `path/to/file2`
  **현재 sub-phase**: <ID>
```

---

## 작업 시작 전 체크리스트
1. 본인 PLAN 이 기존 active lock 과 충돌하는지 확인
2. 충돌 시 owner 와 조율하거나 leader 에 escalate
3. 충돌이 없으면 본인 항목 추가 후 작업 시작

## 작업 완료 시
- 본인 항목 제거
- `DEVELOPMENT_LOG.md` 에 결과 append

## Stale lock 처리
- 24h 이상 갱신이 없고 `DEVELOPMENT_LOG.md` 에 완료/부분완료 기록이 있으면 leader 가 stale 로 판단해 제거 가능

---

## 현재 lock

> agent-w0-foundation-001 의 Wave 0 작업 (PLAN_02 sp1.1/1.2, PLAN_03 전체, PLAN_01 sp1.1/1.2) 완료 — 2026-04-19. 상세는 `DEVELOPMENT_LOG.md` 참조.

> codex-w1e 의 PLAN_02 backend/FE domain/infrastructure/MissionHeader/Collapse/Budget warning 작업 — leader 가 stale lock 제거 (2026-04-19, ACTIVE_WORK 갱신 누락). 상세는 `DEVELOPMENT_LOG.md` 의 leader-PLAN_02 항목 참조.

> agent-w1c-models-backend-002 의 PLAN_06 백엔드/테스트/툴팁 마감 작업 완료 — 2026-04-19. 상세는 `DEVELOPMENT_LOG.md` 12:30 UTC 항목 참조.

> agent-w1d-upload-ui-002 의 PLAN_04 UI 마감 (action wiring, global DnD overlay, error states, a11y) 완료 — 2026-04-19. 상세는 `DEVELOPMENT_LOG.md` 항목 참조. 본 worktree 는 commit 보류 — leader 머지 시 4-commit 분리 예정.

> agent-w1f-timeline-finalize-002 의 PLAN_03 finalize 작업 (Wave 1 영역 100%) 완료 — 2026-04-19. 상세는 `DEVELOPMENT_LOG.md` 09:30 UTC 항목 참조.

> leader 후속 정리 (2026-04-19): `application/mission/getMissionContext.ts` lint:arch violation 을 W1-D 패턴(port DI)으로 fix — `getMissionContextPort.ts` 신규 + `useMissionContext.ts` composition root 에서 `fetchCurrentMissionContext` 주입. `npm run lint:arch` 0 violations.

> leader 인프라 정리 (2026-04-19): `.gitignore` 의 `runtime/` 패턴이 production code (`src/ds_agent/runtime/` 48 files + `electron/src/renderer/components/runtime/` 17 files) 를 첫 commit 부터 차단하던 문제 fix. `runtime/` → `/runtime/` (root-anchored) 변경. 65+ 파일이 머지 대기 untracked 로 인식.

> agent-w1e-mission-finalize-003 (PLAN_02 finalize) — 2026-04-19T15:30Z 시작 후 ~16:00Z API 한도 도달로 중단. 산출물 미보존. leader 가 stale lock 정리 (2026-04-19). 후속 Phase C agent 가 재발주 예정.

> agent-phaseB-a11y-baseline-001 의 cross_cutting/PLAN_01 (Phase B finalize — @axe-core/playwright 4.11.2 install, 5 e2e specs, lint:a11y strict, .github/workflows/a11y.yml CI gate, ADR-0010) 완료 — 2026-04-19. 5 surface 모두 0 critical/serious violation, 0 minor/moderate. 상세는 `DEVELOPMENT_LOG.md` 19:00 UTC 항목 참조.

> agent-phaseA-wave0-fixes-001 의 Wave 0 finalization 작업 (A1 useWebSocket envelope, A2 CI wave0 gate, A3 lint:arch 강화, A4 envelope ts ms, A5 registry version enforce) 완료 — 2026-04-19. 상세는 `DEVELOPMENT_LOG.md` 17:30 UTC 항목 참조.

> agent-phaseC-w1e-finalize-001 의 PLAN_02 finalize 작업 (Phase C — 6 hand-off 항목 모두 완료) — 2026-04-19. 상세는 `DEVELOPMENT_LOG.md` 21:30 UTC 항목 참조.