# S14 RC-5 In-Adapter Egress Kill-Switch — CHANGELOG

**실행일**: 2026-04-18
**RFC**: `Docs/rfc/RFC_2026-04_adapter_killswitch.md` (Accepted)
**해결 이슈**: RC-5 (`Docs/qa_run_2026-04-17/B10_comms_export/FINAL.json` §deferred_issues)

## 코드 변경

### 신규
- `src/ds_agent/infrastructure/external/egress_guard.py`:
  - `is_egress_enabled() -> bool` — `DS_AGENT_NETWORK_EGRESS_ENABLED` env truthy 값 인식 (`1`, `true`, `yes`, `on`, 대소문자/whitespace 무시). 미설정 = disabled (fail-safe).
  - `make_disabled_result() -> tuple[str, str]` — 공통 `("EGRESS_DISABLED", "...")` 반환.

### 5 connector에 3줄 가드 삽입
- `slack_connector.py::SlackConnector.dispatch`
- `jira_connector.py::JiraConnector.dispatch`
- `confluence_connector.py::ConfluenceConnector.dispatch`
- `notion_connector.py::NotionConnector.dispatch`
- `git_connector.py::GitConnector.dispatch`

삽입 위치: `if dry_run: return stub` 블록 **이후**, try 블록 **이전**. dry_run 경로는 기존 동작 보존 (short-circuit before guard).

삽입 패턴:
```python
# S14 in-adapter egress kill-switch (RC-5 closed).
if not is_egress_enabled():
    code, msg = make_disabled_result()
    return ConnectorResult(
        success=False,
        error_code=code,
        error_message=msg,
        retriable=False,
    )
```

### 신규 테스트
- `tests/unit/infrastructure/test_egress_guard.py` (17 테스트): truthy/falsy 매트릭스, 공백 처리, 미설정 default, `make_disabled_result` 계약
- `tests/unit/infrastructure/test_connector_killswitch.py` (10 테스트): 5 connector × `dry_run=False` EGRESS_DISABLED + 5 connector × `dry_run=True` 기존 동작 보존

## Quality Gate

- [x] RFC 작성 및 self-approved
- [x] 신규 테스트 27/27 pass
- [x] 수정 파일 ruff 0 error (confluence_connector.py import order는 --fix로 정리)
- [x] `check_import_contracts` ok (2 계약 유지)
- [x] `check_mypy_baseline` baseline 345 동일, new=0 (annotation 신규 코드가 baseline 이내)
- [x] tests/unit/infrastructure 전체 실행: 1270/1273 pass. 3 fail은 ENV-1 Windows flake(`test_placeholder_tools`, `test_telegram_runner` x2) 기존 이슈로 HANDOFF §4.5 scope 외
- [x] B10 Round 1 simulated_mode + dry_run 테스트 경로 변경 없이 통과 확인

## 보안 이중 방어선 확립

**이전 (단일 방어선)**:
```
LLM → Hub policy gate(simulated_mode) → Connector.dispatch → network
         ↑ 단일 실패점 (정책 우회 시 무방비)
```

**이후 (이중 방어선)**:
```
LLM → Hub policy gate(simulated_mode) → Connector.dispatch
                                         → is_egress_enabled() 체크
                                         → disabled면 EGRESS_DISABLED return
                                         → enabled면 network
```

## 제품 컨셉 정합성

메모리 `feedback_preserve_autonomy` § "Hard constraint만 코드가 강제" 원칙:
- LLM은 여전히 `dispatch(...)` 자유롭게 호출 가능 (orchestrator 역할 유지).
- 코드는 "network egress" hard constraint만 gate — policy/workflow 결정은 LLM이 담당.
- fail-safe default는 "안전 쪽 실패" (deny by default).

## 재감사 요구사항

B10 Round 2: 원래 B10 프롬프트 + "§adapter-level kill-switch 전수 검증" 추가. 새 가드가 5 connector 전수에 일관 적용됨을 독립 agent가 검증.

## Rollback 전략

3 파일 그룹 독립 revert 가능:
1. 5 connector guard 블록 제거 → 기존 dispatch 동작 복원
2. `egress_guard.py` 삭제
3. 테스트 2건 삭제

## 관측 지점 / 운영 노트

- **운영**: 배포 시 `DS_AGENT_NETWORK_EGRESS_ENABLED=true` 명시 설정. 미설정 시 실 호출 전수 `EGRESS_DISABLED` 반환 (regression이 아닌 의도된 보호).
- **테스트 환경**: 기존 simulated_mode / dry_run 테스트 경로 영향 없음. Integration test가 real mode를 기대할 경우 env 주입 필요.

## 별도 이월

- **SlackClient.send** 내부에도 별도 가드 불필요 — SlackConnector.dispatch에서 이미 guard 통과. 그러나 SlackClient를 직접 사용하는 다른 코드 경로가 있다면 별도 RFC 필요 (현재 부재 확인).
- **client stub injection 패턴**: Email/Calendar connector는 B10 기록에 따라 in-adapter kill-switch 이미 보유 — scope 외.
