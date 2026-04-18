# Phase 02: Run Outcome and Artifact Auto-Delivery

**Priority**: P1  
**Status**: Proposed  
**Depends On**: Phase 00-01

---

## 1. Goal

Auto-deliver the right summaries and artifacts when a run outcome clearly
deserves operator attention.

---

## 2. Current Gap

Telegram can already send artifacts on demand, but outcome-driven delivery is
manual.

Missing today:

- success-summary push for important completed runs
- failure-summary push with the right artifact or log hint
- auto-send of selected reports or plots
- policy gating for what is safe to auto-send

---

## 3. Planned Implementation

Primary files:

- `src/ds_agent/gateway/telegram_runner.py`
- `src/ds_agent/runtime/runtime_event_log.py`
- `src/ds_agent/api/workspace_service.py`

Potentially needed:

- `src/ds_agent/runtime/outcome_delivery_policy.py`

Implementation items:

- define run-outcome triggers:
  - failed
  - blocked
  - succeeded with notable artifact
  - succeeded with degraded quality signal
- prefer persisted outcome signals over process-local runtime state when
  delivery must work across daemon, API, and Telegram processes
- choose deliverable payloads such as:
  - summary text
  - report file
  - key plot
  - next action hint
- ensure selection is policy-driven and bounded

---

## 4. Delivery Rules

- auto-delivery should prefer summaries first, files second
- large artifact pushes should only happen when policy allows them
- no sensitive or low-value artifact should be auto-sent just because it exists
- failures should explain what happened before attaching files
- default cloud Bot API file-size limits mean some artifacts must fall back to
  summary-plus-pull rather than auto-attachment

---

## 5. Verification

Required:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m pytest tests/integration/test_runtime_wiring.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/gateway/telegram_runner.py src/ds_agent/api/workspace_service.py
```

Manual checks:

1. Complete one run that produces a report and confirm the expected summary or file is delivered
2. Fail one run and confirm the failure summary is concise and actionable

---

## 6. Exit Criteria

- useful run outcomes can be auto-delivered without manual polling
- auto-delivery is policy-bounded and explainable
- artifact pushes feel intentional rather than noisy

---

## Review: 실현 가능성 점검 코멘트 (2026-04-13)

### R1. Telegram 파일 전송 하드 제한 — policy에 명시적으로 반영

| 제한 | 값 | 처리 |
|------|---|------|
| Bot API 업로드 최대 | 50MB | 초과 시 summary + pull 안내 fallback |
| caption 최대 | 1024자 | 긴 요약은 별도 텍스트 메시지 선행 |

```python
# outcome_delivery_policy.py 에 포함되어야 할 로직
MAX_AUTO_SEND_FILE_SIZE = 50 * 1024 * 1024  # 50MB

def should_auto_send_artifact(file_path: Path, policy: DeliveryPolicy) -> bool:
    if file_path.stat().st_size > MAX_AUTO_SEND_FILE_SIZE:
        return False  # → summary + "/artifact <id> <index>" 안내로 fallback
    # ... policy 평가 계속
```

### R2. 자동 전송 대상 파일 유형 가이드라인

DS 에이전트 산출물 중 auto-delivery에 적합한 것:
- `.png`, `.jpg` — 플롯/차트 (보통 수 KB~MB)
- `.html` — 인터랙티브 리포트 (보통 수 MB)
- `.csv` — 소규모 결과 데이터 (크기 변동)

auto-delivery에서 **제외해야 할 것**:
- `.pkl`, `.joblib` — 모델 파일 (수십~수백 MB)
- `.parquet`, `.feather` — 대용량 데이터셋
- `.log` — 디버깅용, 민감 정보 포함 가능

이 분류를 policy의 기본 필터로 포함하는 것을 권장한다.

### R3. 자동 전송과 rate limit의 교차점

한 run이 다수의 산출물(예: 5개 플롯 + 1 리포트)을 생성하면,
auto-delivery가 연속으로 6개 파일을 전송하게 되어 Telegram rate limit에 걸릴 수 있다.

**권장**: 한 run의 auto-delivery는 최대 N건(예: 3건)으로 제한하고,
나머지는 `/artifacts <project_id>` 안내로 대체.
또는 가장 중요한 산출물 1건 + "외 N건" 요약으로 통합.
