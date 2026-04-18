# Enhancement Specs Implementation Gap Audit (2026-04-16)

## Scope

- 대상 문서: `Docs/enhancement-specs/README.md`, `01`~`10` 본문, 2026-04-16 addendum 문서들
- 점검 범위: `src/`, `electron/`, `tests/`, `scripts/`
- 판정 기준:
  - `Implemented`: spec deliverable에 대응되는 domain/application/infrastructure/presentation/test 근거가 확인됨
  - `Partial`: 핵심 뼈대는 있으나 operator surface, E2E, cutover, later phase가 비어 있음
  - `Not implemented`: spec가 요구하는 전용 엔티티/유스케이스/CLI/UI/migration 근거를 찾지 못함

## Audit Note

- 이 문서는 정적 감사 결과다. 문서에 적힌 모든 테스트 수치를 재실행하지는 않았다.
- 따라서 아래 판정은 "문서 주장"이 아니라 "현재 코드베이스에서 확인 가능한 구현 근거" 기준이다.

## Executive Summary

| Spec | 문서상 상태 | 코드 기준 판정 | 아직 남은 구현/검증 갭 |
|---|---|---|---|
| `01-task-contract` | core complete + optional polish | `Implemented (minor residual)` | Electron realtime subscribe/push만 미구현 |
| `02-semantic-memory` | README는 `미착수`, 본문은 Phase 1~6 대규모 업데이트 | `Partial` | 문서-실코드 상태 불일치, semantic 전용 Electron/E2E 검증 공백, `DomainKB` 완전 cutover 미완료 |
| `03-verifier-orchestrator` | current scope complete | `Implemented` | 현재 계획 범위 기준 추가 갭 미발견 |
| `04-autonomy-control-plane` | current scope complete | `Implemented` | 현재 계획 범위 기준 추가 갭 미발견 |
| `05-evaluation-harness` | current scope complete | `Implemented` | 현재 계획 범위 기준 추가 갭 미발견 |
| `06-decision-os` | current scope complete | `Implemented` | 현재 계획 범위 기준 추가 갭 미발견 |
| `07-stakeholder-communication` | current scope complete | `Implemented` | 현재 계획 범위 기준 추가 갭 미발견 |
| `08-workflow-integration` | P2a complete, P3a landed, P3b partial | `Partial` | Electron mutation control, IntegrationSettings/health/replay, packaged E2E, later connectors 미구현 |
| `09-async-portfolio` | `미착수` | `Not implemented` | spec 전용 portfolio layer 전체 미구현 |
| `10-self-improvement-governance` | `미착수` | `Not implemented (with prerequisites)` | governance layer 전체 미구현. 다만 `pending_promotion` gate 선행 자산은 존재 |

## High-Priority Findings

### 1. `08-workflow-integration`이 다음 실제 개발 우선순위다

- 이미 `WorkObject`, `IntegrationHub`, Slack/Jira/Confluence/Notion/Git, API/CLI, read-only Electron panel까지 연결돼 있다.
- 하지만 spec이 직접 남은 일로 적은 핵심 operator loop가 아직 닫히지 않았다.
- 확인 근거:
  - `electron/src/renderer/components/workflow/WorkObjectPanel.tsx`는 조회/필터/리프레시 중심의 read-only UI다.
  - 같은 컴포넌트에서 intake/advance/close action 버튼이나 form state가 없다.
  - `electron/src/renderer/components/` 아래 `IntegrationSettings.tsx`가 없다.
  - `electron/tests/`에는 `contract/work-object-panel.spec.ts`만 있고 packaged smoke/E2E는 없다.
  - `src/ds_agent/infrastructure/external/`에는 `SlackConnector`, `JiraConnector`, `ConfluenceConnector`, `NotionConnector`, `GitConnector`만 확인된다.
- 남은 구현 항목:
  - Electron-side mutation controls for WorkObject intake/phase/close
  - IntegrationSettings / integration health / replay surfaces
  - packaged WorkObject E2E coverage
  - Email/Calendar/BI, Asana/Monday, DLQ/replay operations

### 2. `09-async-portfolio`는 사실상 아직 시작되지 않았다

- spec가 요구하는 `PortfolioEntry`, `WaitCondition`, `PortfolioScheduler`, `PortfolioCheckpoint`, `ProjectControlTower`, `portfolio` CLI는 코드에서 확인되지 않았다.
- `rg` 기준으로 `src/`, `electron/`, `tests/` 안에 spec 전용 portfolio 타입/모듈명이 나오지 않는다.
- 존재하는 것은 선행 자산뿐이다:
  - `src/ds_agent/runtime/task_ledger.py`
  - `src/ds_agent/runtime/checkpoint_store.py`
  - `src/ds_agent/runtime/background_task_manager.py`
  - `src/ds_agent/runtime/goal_store.py`
- 즉, `09`는 "붙일 기반은 있음"이지 "스펙 구현이 들어간 상태"는 아니다.
- 남은 구현 항목:
  - domain/application/infrastructure portfolio layer
  - migration v12
  - wait-condition evaluator / scheduler
  - prompt integration
  - Electron `ProjectControlTower`
  - CLI `portfolio` subcommand

### 3. `10-self-improvement-governance`는 prerequisite는 있지만 governance layer가 없다

- 현재 repo에는 self-improve 후보 승격의 선행 자산이 있다:
  - `src/ds_agent/self_improve/promotion_candidates.py`
  - `src/ds_agent/self_improve/promotion_gate.py`
  - `src/ds_agent/evaluation/infrastructure/cli/eval_cli.py`
- 하지만 spec 10의 핵심 거버넌스 아티팩트는 없다:
  - `LearningItem`
  - `LearningInbox`
  - `ReviewEvent`
  - `ConflictAlert`
  - `list_learning_inbox`
  - `review_learning_item`
  - `PromoteLearningItemUseCase`
  - `DeprecateLearningItemUseCase`
- roadmap 문서에는 `self_improve/learning_inbox.py`가 계획돼 있지만 실제 파일은 없다.
- `electron/`에도 `LearningInbox.tsx`나 이에 대응하는 hook/test가 없다.
- migration 패키지에도 spec이 요구한 v13 스키마는 없다.
- 판정:
  - `05`의 pending-promotion gate는 "10의 대체 구현"이 아니라 "10으로 넘어가기 위한 전단계"다.

## Medium-Priority Findings

### 4. `02-semantic-memory`는 README 표가 stale이고, 실제로는 부분 구현 상태다

- `Docs/enhancement-specs/README.md` 표는 `02`를 `미착수`로 적고 있다.
- 그러나 실제 코드에는 semantic layer가 넓게 들어가 있다:
  - `src/ds_agent/memory/semantic/` domain/application/infrastructure 패키지
  - `src/ds_agent/agent/semantic_hooks.py`
  - `src/ds_agent/tools/semantic_query.py`
  - `src/ds_agent/tools/load_semantic_pack.py`
  - `src/ds_agent/cli/semantic_cli.py`
  - `src/ds_agent/runtime/semantic_proposal_router.py`
  - `electron/src/renderer/components/semantic/MetricSourcePanel.tsx`
- 즉 `02`는 `미착수`가 아니라 "core는 많이 landed, 운영 검증과 cutover가 남은 상태"로 보는 것이 맞다.

#### 02에서 아직 남은 갭

- semantic 전용 Electron 테스트 공백
  - `electron/tests/`에서 `semantic` 관련 contract/smoke/E2E를 찾지 못했다.
  - 현재 Electron semantic surface는 `MetricSourcePanel` 실장만 있고 전용 테스트 근거가 약하다.
- semantic 전용 Telegram/operator surface 부재
  - `src/ds_agent/gateway`, `src/ds_agent/channels`에서 semantic 전용 surface는 찾지 못했다.
  - proposal approval은 `ApprovalPanel`/approval bus를 통해 generic하게만 노출된다.
- quality gate 문서-실코드 차이
  - spec 본문은 `scripts/check_layer_deps.py`를 요구하지만, 실제 repo에는 이 파일이 없다.
  - 대체로 `scripts/check_import_contracts.py`는 존재하지만, spec 명세와는 다르다.
- `DomainKB` 완전 cutover 미완료
  - `src/ds_agent/agent/factory.py`는 `DomainKB`와 `SemanticMemoryHintBuilder`를 같이 사용한다.
  - `src/ds_agent/runtime/memory_query_service.py`, `src/ds_agent/self_improve/learning_adapter.py`도 여전히 `DomainKB`를 직접 인스턴스화한다.
  - 따라서 semantic memory가 sole source로 완전히 승격된 상태는 아니다.

### 5. `01-task-contract`는 거의 닫혔고 realtime subscribe만 잔여다

- addendum 기준으로 broad operator-flow gap은 닫혔다.
- 실제로도 assumption verify, lifecycle/governance smoke, Mission Brief panel은 확인된다.
- 다만 spec 본문이 요구한 `task_contract.subscribe` IPC는 현재 없다.
- 확인 근거:
  - `electron/src/main/ipc.ts`에는 `list`, `active`, `get`, `update`, `close`, `verifyAssumption`, `buildDeliveryPack`, `renderArtifact`, `dispatchDelivery`, `listDeliveryLog`, `listShadowComparisons`, `getShadowComparison`만 있다.
  - `electron/src/preload/index.ts`에도 subscribe bridge가 없다.
  - `electron/src/renderer/hooks/useTaskContract.ts`는 `stream.done` / `tool.end`를 받아 `refresh()`하는 polling-like refresh-on-action 모델이다.
- 결론:
  - 현재 남은 것은 spec addendum이 말한 그대로 optional realtime subscribe/push polish다.

## No Material Feature-Scope Gaps Found

아래 문서들은 spot-check 기준으로 현재 계획 범위의 핵심 deliverable이 코드/테스트/UI까지 연결되어 있었고, 문서가 말하는 "현재 scope 완료" 주장과 큰 충돌을 찾지 못했다.

- `03-verifier-orchestrator`
  - 근거: `src/ds_agent/application/services/verifier_orchestrator.py`, `src/ds_agent/tools/verifier_tool.py`, verifier judge fixtures, Electron quality-panel contract test
- `04-autonomy-control-plane`
  - 근거: `src/ds_agent/runtime/action_classifier.py`, `src/ds_agent/runtime/autonomy_policy.py`, `electron/src/renderer/components/settings/PolicyStudio.tsx`, `electron/tests/smoke/autonomy-control-plane.spec.ts`
- `05-evaluation-harness`
  - 근거: `src/ds_agent/tools/evaluation.py`, `electron/src/renderer/components/runtime/RegressionBoard.tsx`, `electron/tests/contract/regression-board.spec.ts`, self-improve candidate gate classes
- `06-decision-os`
  - 근거: `src/ds_agent/tools/decision_os_tools.py`, `src/ds_agent/application/services/review_artifact_capture.py`, `electron/src/renderer/components/workflow/ReviewTab.tsx`, `electron/tests/smoke/decision-os-review.spec.ts`
- `07-stakeholder-communication`
  - 근거: `src/ds_agent/infrastructure/delivery/delivery_router.py`, `src/ds_agent/infrastructure/delivery/channel_adapters.py`, `electron/tests/contract/mission-brief.spec.ts`, `electron/tests/contract/task-contract-preview.spec.ts`

## Recommended Backlog Order

1. `08` P3b operator loop close
   - WorkObjectPanel mutation control
   - IntegrationSettings/health/replay
   - packaged E2E
2. `10` governance layer 착수
   - `LearningItem` / inbox / review workflow / migration v13
3. `09` portfolio layer 착수
   - portfolio domain/app/infra + scheduler + UI/CLI
4. `02` 문서/검증/cutover 정리
   - README 상태 수정
   - semantic Electron test 추가
   - `DomainKB` coexistence vs cutover 방침 명시
   - quality gate 스크립트 명세 정합화
5. `01` optional realtime subscribe/push

## Documentation Hygiene Issues

- `Docs/enhancement-specs/README.md`의 `02-semantic-memory` 행은 현재 코드 상태와 맞지 않는다.
- `01-task-contract.md` 본문 상단의 "후속 polish" 일부는 addendum으로 이미 상당 부분 해소되었으므로, 본문 상태 문구를 addendum 기준으로 재정리하는 편이 안전하다.

## Bottom Line

- 실질적인 미구현 우선순위는 `08 -> 10 -> 09 -> 02 cleanup -> 01 optional polish` 순이다.
- `03`, `04`, `05`, `06`, `07`은 현재 enhancement-specs 범위 기준으로는 추가 feature-gap보다 유지보수/확장 단계로 보는 것이 맞다.
- `02`는 "미착수"가 아니라 "상당 부분 구현됐지만 운영 검증과 cutover 정리가 남은 상태"다.
