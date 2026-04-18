# RFC: In-Adapter Egress Kill-Switch for 5 External Connectors

**작성일**: 2026-04-18
**상태**: Accepted (self-approved per Decision Log §24.2-6 scope — S14)
**Sprint**: S14
**출처**: B10 R1 observation RC-5 (`Docs/qa_run_2026-04-17/B10_comms_export/FINAL.json` §deferred_issues)

---

## 1. 배경

**B10 Round 1 실측 발견** (`Docs/qa_run_2026-04-17/B10_comms_export/FINAL.json`):

> Slack / Jira / Confluence / Notion / Git connector lacks in-adapter `_is_configured()` kill-switch; real-mode egress is gated at IntegrationHub / DeliveryRouter policy layer. Harness urllib monkeypatch intercepted all 5 attempted egresses.

### 현재 구조
```
┌────────────────────────────┐
│ IntegrationHub / Router    │  ← policy-layer gate (현재 단일 방어선)
│ (simulated_mode=True 체크)  │
└────────────┬───────────────┘
             ↓
┌────────────────────────────┐
│ Connector.dispatch(...)    │  ← 어떤 내부 guard도 없음 (bug surface)
│  if dry_run:  return stub  │     dry_run=False + real credential 주입 시
│  self._client.send(...)    │     즉시 network egress 발생 가능
└────────────────────────────┘
```

### Risk
- Policy layer가 버그/오설정으로 우회되면 즉시 real egress.
- Test harness가 urllib monkeypatch로 모든 egress를 차단했지만, **이는 테스트 환경 차원의 우연한 안전망**이지 프로덕션 가드가 아님.
- 제품 컨셉("LLM이 유일한 오케스트레이터")에 비추어: LLM이 도구를 호출할 때 **hard constraint 레벨 safeguard**는 코드 영역이어야 함 (메모리 `feedback_preserve_autonomy` §"Hard constraint만 코드가 강제" 원칙).

---

## 2. 제안: 이중 방어선 (Defense in Depth)

IntegrationHub policy layer는 유지 + 각 connector **adapter 내부에 추가 guard**.

### 2.1 공용 유틸
`src/ds_agent/infrastructure/external/egress_guard.py` 신설:

```python
def is_egress_enabled() -> bool:
    """Return True only if DS_AGENT_NETWORK_EGRESS_ENABLED is set to a truthy value."""
    import os
    value = os.environ.get("DS_AGENT_NETWORK_EGRESS_ENABLED", "")
    return value.lower() in {"1", "true", "yes", "on"}
```

### 2.2 각 connector의 `dispatch`에 3줄 추가
```python
def dispatch(self, request, *, idempotency_key, dry_run=False):
    if dry_run:
        return _dry_run_stub(...)
    if not is_egress_enabled():
        return ConnectorResult(
            success=False,
            error_code="EGRESS_DISABLED",
            error_message=(
                "Network egress disabled at adapter layer. "
                "Set DS_AGENT_NETWORK_EGRESS_ENABLED=true to enable."
            ),
            retriable=False,
        )
    # ... real client call
```

### 2.3 대상 5 connector
- `slack_connector.py::SlackConnector.dispatch`
- `jira_connector.py::JiraConnector.dispatch`
- `confluence_connector.py::ConfluenceConnector.dispatch`
- `notion_connector.py::NotionConnector.dispatch`
- `git_connector.py::GitConnector.dispatch` (동일 구조 확인 후)

Email/Calendar는 B10이 이미 in-adapter kill-switch 보유로 판정 → scope 외.

---

## 3. 대안 검토

### 3.1 Option A: 단일 hub policy gate 유지 (현 상태)
- Pro: 단순. 구현 0
- Con: 단일 failure point. 우회 시 무방비
- **기각** — §1 risk 해소 안 됨

### 3.2 Option B: Feature flag decorator
- Connector method에 `@requires_egress` 데코레이터
- Pro: 선언적
- Con: 데코레이터 동작이 테스트/mock 경로에서 쉽게 깨질 수 있음 (MagicMock 주입 시 decorator 우회)
- **기각** — §1 테스트 환경 우연 안전망 문제 재현

### 3.3 Option C (선택): 명시적 in-method guard
- dispatch 맨 시작부에서 explicit 체크
- Pro: 모든 호출 경로에 공통 적용. 우회 어려움. 테스트에서도 동일 경로
- Con: 5 connector에 동일 코드 반복 (3줄)
- **선택** — 가드 single source of truth는 `egress_guard.py` 공용 유틸

---

## 4. 호환성

### 4.1 기존 테스트
- B10 Round 1 테스트 전수는 `dry_run=True` 또는 urllib monkeypatch로 동작. **새 가드로 영향 없음**.
- Integration 테스트가 real mode를 기대한다면 `DS_AGENT_NETWORK_EGRESS_ENABLED=true` env 주입으로 통과.

### 4.2 Default 정책
- `DS_AGENT_NETWORK_EGRESS_ENABLED` **미설정 시 disabled** (fail-safe).
- Production 배포 시 운영팀이 명시적 opt-in.

### 4.3 문서
- `Docs/DS_AGENT_COMPREHENSIVE_REPORT_2026-04-17_ADDENDUM.md`에 §11 "Security Boundary" 추가 예정 (S14 CHANGELOG에 반영).
- 운영 가이드에 `DS_AGENT_NETWORK_EGRESS_ENABLED` env 명시.

---

## 5. 테스트 전략

### 5.1 신규 단위 테스트
`tests/unit/infrastructure/test_egress_guard.py`:
- `DS_AGENT_NETWORK_EGRESS_ENABLED=true` → `is_egress_enabled() == True`
- `=false`, `=0`, unset → `False`
- `=1`, `=yes`, `=on` → `True`

`tests/unit/infrastructure/test_connector_killswitch.py`:
- 5 connector × `dispatch(dry_run=False)` + env unset → `success=False, error_code="EGRESS_DISABLED"`
- 5 connector × `dispatch(dry_run=False)` + env `=true` + client mock → real path 진입 (mock response 확인)
- 5 connector × `dispatch(dry_run=True)` + env unset → dry_run 응답 (가드 이전 short-circuit, **기존 동작 변경 없음**)

### 5.2 B10 Round 2 재감사
B10 원래 프롬프트에 "adapter-level kill-switch 검증" 추가하여 재감사. 새 가드가 5 connector 전수에 적용됨을 독립 agent가 확인.

---

## 6. 구현 순서

1. `egress_guard.py` + 단위 테스트 RED→GREEN
2. 5 connector에 guard 삽입 + 통합 테스트 RED→GREEN
3. Addendum §11 섹션 추가
4. Quality Gate 통과 후 B10 Round 2 재감사 스폰

---

## 7. 승인

Decision Log §24.2-6에 따라 본 RFC는 self-approved. 변경 사항 발생 시 이 파일 "변경 이력"에 append.

## 8. 변경 이력

| 날짜 | 변경 | 작성자 |
|------|------|--------|
| 2026-04-18 | 최초 작성 및 self-approval | Main orchestrator |
