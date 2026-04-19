# ACTIVE_WORK — 진행 중 작업 (Lock)

현재 작업 중인 agent의 lock 표. **자기 항목만 추가/제거**한다.

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

1. 본 표에서 자기 PLAN의 파일과 겹치는 행이 있는가?
2. 있으면 → 해당 owner와 협의 (또는 leader에 escalate)
3. 없으면 → 자기 항목 추가 후 작업 시작

## 작업 완료 시

- 자기 항목 제거
- DEVELOPMENT_LOG에 항목 추가

## Stale lock 처리

- 항목이 24h 이상 갱신 안 됨 + DEVELOPMENT_LOG에 완료 기록 없음 → leader가 stale로 판단하여 제거 가능

---

## 현재 lock

(작업 시작 시 추가)

- **PLAN**: phase1_quick_wins/PLAN_05_sidebar_collapse
  **Owner**: agent-w1-sidebar-001
  **Started**: 2026-04-19T04:07:49.2386345Z
  **Worktree**: C:\Users\aquap\Desktop\AI_Data_Scientist_Demo
  **예상 종료**: 2026-04-19T08:07Z
  **Files (예상 touch)**:
    - `electron/src/renderer/components/layout/Sidebar.tsx`
    - `electron/src/renderer/components/sidebar/SidebarItem.tsx`
    - `electron/src/renderer/hooks/useKeyboardShortcut.ts`
    - `electron/src/renderer/hooks/useSidebarCollapse.ts`
    - `electron/src/renderer/utils/sidebarLayout.ts`
    - `electron/src/renderer/utils/keyboardShortcut.ts`
    - `electron/src/renderer/stores/i18nStore.ts`
    - `electron/tests/contract/sidebarCollapse.spec.ts`
  **현재 sub-phase**: Sub-Phase 5.1 RED

> agent-w0-foundation-001 의 Wave 0 작업 (PLAN_02 sp1.1/1.2, PLAN_03 전체, PLAN_01 sp1.1/1.2) 완료 — 2026-04-19. 상세는 `DEVELOPMENT_LOG.md` 참조.
