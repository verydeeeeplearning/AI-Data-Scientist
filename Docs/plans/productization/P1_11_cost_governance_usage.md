# P1-11: 비용 거버넌스 & 사용량 제어

**우선순위**: P1
**요구사항 섹션**: 5.12
**상태**: Complete
**의존성**: P0-02 (API key 관리와 연동)

---

## 개요

일반 사용자는 토큰 단가를 모른다. 비용 UX 없으면 "예상치 못한 과금" 불만이 빠르게 발생.
또한 Anthropic prompt caching이 이미 활성화돼 있다면 이 절약분을 사용자에게 보여주는 것이
신뢰를 높이는 데 유리하다.

---

## 설계

### 비용 대시보드

```
┌─────────────────────────────────────────────┐
│  이번 달 AI 사용                             │
│                                             │
│  $3.42  ←━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫ $10.00 (한도)
│          34%                                │
│                                             │
│  절약: $1.20 (프롬프트 캐싱)                 │
│  이번 세션: $0.08 / 오늘: $0.55             │
│                                             │
│  [한도 변경] [상세 내역]                      │
└─────────────────────────────────────────────┘
```

### 경고 임계치

- 60% 도달: 상태바에 주황 표시
- 80% 도달: 기본 경고 알림 "이번 달 예산의 80%를 사용했습니다"
- 100% 도달: 새 분석 차단 + "한도 초과" 다이얼로그

---

## 구현 상태 (2026-04-14)

- 백엔드 사용량 추적은 `PricingTracker`와 조직 사용량 저장소에 연결됐다. 모델별 비용, input/output/cache/reasoning tokens, cache savings가 월/일/세션 집계에 반영된다.
- 사용량 대시보드는 `GET /api/usage/summary`와 `usage.summary` RPC/event로 제공된다. Sidebar `UsageMeter`, Settings `CostSettings`, workflow warning surface가 같은 요약 payload를 공유한다.
- 예산 제어는 `provider.max_budget_usd`와 `provider.budget_warning_threshold_pct` 설정으로 동작한다. 경고 임계치는 60/80/90 중 선택 가능하고, 100% 도달 시 새 분석 시작이 차단된다.
- 시각 정책은 문서 의도대로 분리됐다. Sidebar 미터는 60%부터 주황 표시, 경고 이벤트는 설정값 기준, 새 run 차단은 100% 도달 시 적용된다.

### 실제 구현 파일

- `src/ds_agent/providers/pricing.py`
- `src/ds_agent/runtime/organization_store.py`
- `src/ds_agent/application/services/usage_summary.py`
- `src/ds_agent/api/routes/usage.py`
- `src/ds_agent/api/ws_handler.py`
- `src/ds_agent/config/schema.py`
- `src/ds_agent/api/config_manager.py`
- `src/ds_agent/api/routes/config.py`
- `electron/src/renderer/hooks/useUsageSummary.ts`
- `electron/src/renderer/components/sidebar/UsageMeter.tsx`
- `electron/src/renderer/components/settings/CostSettings.tsx`
- `electron/src/renderer/stores/usageStore.ts`

### 검증

- `pytest tests/unit/application/test_usage_summary.py tests/unit/infrastructure/test_pricing.py tests/unit/infrastructure/test_organization_store.py tests/unit/infrastructure/test_api.py tests/unit/infrastructure/test_config.py -q`
- `ruff check ...`
- `ruff format --check ...`
- `cd electron && npx tsc --noEmit`

---

## 구현 Phase 계획

### Phase 1: 사용량 추적 백엔드

**새 파일**: `src/ds_agent/application/use_cases/usage_tracker.py`

```python
@dataclass
class UsageRecord:
    timestamp: datetime
    session_id: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int    # 프롬프트 캐시 히트
    cache_creation_tokens: int
    cost_usd: float           # 계산된 비용

class UsageTracker:
    """사용량 기록 및 집계."""

    def __init__(self, db: SessionDB) -> None:
        self._db = db

    def record(self, usage: UsageRecord) -> None:
        self._db.save_usage(usage)

    def get_monthly_summary(self) -> MonthlySummary:
        records = self._db.get_usage_since(start_of_month())
        total_cost = sum(r.cost_usd for r in records)
        cache_savings = sum(
            r.cache_read_tokens * CACHE_READ_PRICE[r.model]
            for r in records
        )
        return MonthlySummary(
            total_cost_usd=total_cost,
            cache_savings_usd=cache_savings,
            session_count=len({r.session_id for r in records}),
            by_model=self._group_by_model(records),
        )
```

**LLM 응답에서 usage 추출**:

```python
# Anthropic SDK 응답에서 usage 추출
def extract_anthropic_usage(response: Message) -> UsageRecord:
    usage = response.usage
    return UsageRecord(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=getattr(usage, 'cache_read_input_tokens', 0),
        cache_creation_tokens=getattr(usage, 'cache_creation_input_tokens', 0),
        cost_usd=calculate_cost(response.model, usage),
    )
```

**가격 테이블**: `src/ds_agent/infrastructure/pricing/model_pricing.py`

```python
MODEL_PRICING: dict[str, ModelPrice] = {
    "claude-opus-4-6": ModelPrice(
        input=15.0 / 1_000_000,
        output=75.0 / 1_000_000,
        cache_read=1.5 / 1_000_000,
        cache_creation=18.75 / 1_000_000,
    ),
    "claude-sonnet-4-6": ModelPrice(
        input=3.0 / 1_000_000,
        output=15.0 / 1_000_000,
        cache_read=0.3 / 1_000_000,
        cache_creation=3.75 / 1_000_000,
    ),
    "claude-haiku-4-5": ModelPrice(
        input=0.8 / 1_000_000,
        output=4.0 / 1_000_000,
        cache_read=0.08 / 1_000_000,
        cache_creation=1.0 / 1_000_000,
    ),
}
```

---

### Phase 2: 비용 대시보드 UI

**새 API**: `GET /api/usage/summary`

```python
@router.get("/usage/summary")
async def get_usage_summary() -> UsageSummaryResponse:
    monthly = usage_tracker.get_monthly_summary()
    budget = config_manager.get("provider.max_budget_usd")
    return UsageSummaryResponse(
        monthly_cost_usd=monthly.total_cost_usd,
        monthly_budget_usd=budget,
        budget_used_pct=monthly.total_cost_usd / budget * 100 if budget else 0,
        cache_savings_usd=monthly.cache_savings_usd,
        session_cost_usd=monthly.current_session_cost,
        today_cost_usd=monthly.today_cost,
    )
```

**새 파일**: `electron/src/renderer/components/sidebar/UsageMeter.tsx`

```tsx
export function UsageMeter() {
  const { data: usage } = useUsageSummary();
  if (!usage) return null;

  const pct = Math.min(usage.budget_used_pct, 100);
  const isWarning = pct >= 60;
  const isDanger = pct >= 80;

  return (
    <div className="usage-meter">
      <div className="usage-header">
        <span>이번 달 사용</span>
        <span className="usage-amount">
          ${usage.monthly_cost_usd.toFixed(2)} / ${usage.monthly_budget_usd.toFixed(0)}
        </span>
      </div>

      <ProgressBar
        value={pct}
        className={isDanger ? 'danger' : isWarning ? 'warning' : ''}
      />

      {usage.cache_savings_usd > 0 && (
        <div className="cache-savings">
          💡 캐싱으로 ${usage.cache_savings_usd.toFixed(2)} 절약
        </div>
      )}

      <div className="usage-detail text-muted">
        세션: ${usage.session_cost_usd.toFixed(3)} · 오늘: ${usage.today_cost_usd.toFixed(2)}
      </div>
    </div>
  );
}
```

---

### Phase 3: 예산 한도 초과 차단

**수정 파일**: `src/ds_agent/agent/core.py` (agent loop)

```python
# agent loop 시작 전 예산 확인
async def run(self, message: str) -> AsyncIterator[str]:
    summary = await self._usage_tracker.get_monthly_summary()
    budget = self._config.provider.max_budget_usd

    if budget and summary.total_cost_usd >= budget:
        yield ErrorEvent(
            code="DSA-LLM-002",
            message=f"이번 달 사용 한도(${budget})에 도달했습니다. 설정에서 한도를 늘리거나 내달까지 기다려주세요.",
        )
        return

    # 정상 실행
    async for event in self._loop():
        yield event
```

**80% 경고 알림**:

```python
if budget and summary.total_cost_usd / budget >= 0.8:
    yield WarningEvent(
        message=f"이번 달 예산의 {summary.budget_used_pct:.0f}%를 사용했습니다.",
        action={"label": "한도 변경", "url": "/settings/cost"},
    )
```

---

### Phase 4: 예산 설정 UI

**새 파일**: `electron/src/renderer/components/settings/CostSettings.tsx`

```tsx
export function CostSettings() {
  return (
    <section>
      <h3>비용 설정</h3>

      <FormField label="월간 한도">
        <div className="budget-input">
          <span>$</span>
          <Input type="number" name="max_budget_usd" min={0} step={1} />
          <span className="hint">0이면 한도 없음</span>
        </div>
      </FormField>

      <FormField label="경고 임계치">
        <Select
          options={[
            { value: '60', label: '60% (권장)' },
            { value: '80', label: '80%' },
            { value: '90', label: '90%' },
          ]}
        />
      </FormField>

      <div className="preset-buttons">
        <Button variant="outline" onClick={() => setBudget(5)}>$5/월</Button>
        <Button variant="outline" onClick={() => setBudget(10)}>$10/월</Button>
        <Button variant="outline" onClick={() => setBudget(20)}>$20/월</Button>
        <Button variant="outline" onClick={() => setBudget(0)}>한도 없음</Button>
      </div>
    </section>
  );
}
```

---

## Quality Gate

- [x] LLM 응답마다 usage 기록 확인 (input/output/cache tokens)
- [x] 월간 비용 합산 정확성 테스트
- [x] 캐시 절약 금액 표시 확인 (Anthropic cache_read_input_tokens)
- [x] 한도 100% 도달 시 새 분석 차단 확인
- [x] 80% 경고 알림 표시 확인
- [x] 세션/일/월별 비용 분리 집계 확인
