# P1-09: Provider/Model 추상화 UX

**우선순위**: P1
**요구사항 섹션**: 5.4
**상태**: Complete
**의존성**: P0-02 (credential storage), P1-08 (onboarding)

---

## 자율 Agent 원칙 확인

> Provider/Model 추상화는 사용자 UI 레이어에서만 일어난다.
> 내부적으로 provider router는 그대로 동작하며, LLM이 어떤 tool을 사용할지는 자율적으로 결정한다.
> 단지 사용자가 "Balanced"를 선택하면 그것이 config.provider.default_model에 반영되는 것이다.

---

## 설계

### Simple Mode 프리셋 (기본 UI)

```
┌────────────────────────────────────────────────────┐
│  AI 성능 설정                                       │
│                                                    │
│  ○ 최고 품질      복잡한 분석, 상세한 보고서에 적합    │
│                   (조금 느리고, 비용이 더 듭니다)     │
│                                                    │
│  ● 균형 (권장)    대부분의 분석에 적합               │
│                                                    │
│  ○ 빠른 응답      간단한 질문, 빠른 확인에 적합       │
│                   (비용이 적게 듭니다)               │
│                                                    │
│  ○ 내 컴퓨터      인터넷 없이, 무료로 사용            │
│    (로컬)         (처음 설치 필요)                   │
│                                                    │
│  [고급 설정 보기 ▼]                                 │
└────────────────────────────────────────────────────┘
```

### 프리셋 → 실제 모델 매핑

```typescript
const PRESET_TO_MODEL: Record<QualityPreset, ModelSelector> = {
  best_quality: {
    primary: 'anthropic/claude-opus-4-6',
    fallback: 'openai/gpt-4.1',
  },
  balanced: {
    primary: 'anthropic/claude-sonnet-4-6',
    fallback: 'openai/gpt-4.1-mini',
  },
  fast: {
    primary: 'anthropic/claude-haiku-4-5',
    fallback: 'openai/gpt-4.1-mini',
  },
  local: {
    primary: 'ollama/llama3.2',
    fallback: null,
  },
};
```

### Advanced Mode (토글 시 표시)

```tsx
function AdvancedModelSettings() {
  return (
    <details>
      <summary>고급 설정 (개발자용)</summary>
      <Select label="기본 모델" options={ALL_MODELS} />
      <Select label="Fallback 모델" options={ALL_MODELS} />
      <Input label="최대 예산 ($/월)" type="number" />
    </details>
  );
}
```

---

## 구현 Phase 계획

### Phase 1: QualityPreset 도메인 + config 연동

**새 파일**: `src/ds_agent/domain/value_objects/quality_preset.py`

```python
from enum import Enum

class QualityPreset(str, Enum):
    BEST_QUALITY = "best_quality"
    BALANCED = "balanced"
    FAST = "fast"
    LOCAL = "local"

PRESET_MODEL_MAP: dict[QualityPreset, dict] = {
    QualityPreset.BEST_QUALITY: {
        "primary": "anthropic/claude-opus-4-6",
        "fallback": ["openai/gpt-4.1"],
    },
    QualityPreset.BALANCED: {
        "primary": "anthropic/claude-sonnet-4-6",
        "fallback": ["openai/gpt-4.1-mini"],
    },
    QualityPreset.FAST: {
        "primary": "anthropic/claude-haiku-4-5",
        "fallback": ["openai/gpt-4.1-mini"],
    },
    QualityPreset.LOCAL: {
        "primary": "ollama/llama3.2",
        "fallback": [],
    },
}
```

**수정 파일**: `src/ds_agent/config/schema.py`

```python
class ProviderConfig(BaseModel):
    quality_preset: QualityPreset = QualityPreset.BALANCED
    default_model: str = "anthropic/claude-sonnet-4-6"
    # preset 선택 시 default_model 자동 업데이트
```

**수정 파일**: `src/ds_agent/api/config_manager.py`

```python
def set_quality_preset(self, preset: QualityPreset) -> None:
    """프리셋 선택 시 default_model 자동 설정."""
    model_config = PRESET_MODEL_MAP[preset]
    self.set("provider.quality_preset", preset.value)
    self.set("provider.default_model", model_config["primary"])
    self.set("provider.fallback_models", model_config["fallback"])
```

---

### Phase 2: Provider Health + Fallback 상태 표시

**새 RPC**: `provider.health`

```python
@router.get("/providers/status")
async def get_provider_status() -> dict:
    return {
        "providers": [
            {
                "id": "anthropic",
                "label": "Claude (Anthropic)",
                "status": "ok",       # ok | degraded | unavailable
                "latency_ms": 250,
                "has_credentials": True,
            },
            {
                "id": "ollama",
                "label": "내 컴퓨터 (Ollama)",
                "status": "unavailable",
                "has_credentials": True,
                "message": "Ollama가 실행되지 않았습니다",
            },
        ]
    }
```

**새 컴포넌트**: `ProviderStatusBadge.tsx`

```tsx
function ProviderStatusBadge({ status }: { status: ProviderStatus }) {
  return (
    <span className={`badge badge-${status}`}>
      {status === 'ok' ? '✓ 정상' :
       status === 'degraded' ? '⚠ 느림' : '✗ 연결 안 됨'}
    </span>
  );
}
```

---

### Phase 3: Fallback 발생 시 사용자 알림

```typescript
// WebSocket 이벤트: provider fallback 발생
{
  type: "provider_fallback",
  from: "anthropic/claude-opus-4-6",
  to: "openai/gpt-4.1",
  reason: "rate_limit"
}
```

```tsx
// 채팅 화면 상단 알림 바
function ProviderFallbackNotice({ event }: Props) {
  return (
    <Notice type="info">
      ⚡ 현재 빠른 응답을 위해 대체 AI를 사용 중입니다.
      분석 품질에는 영향이 없습니다.
    </Notice>
  );
}
```

---

## Quality Gate

- [x] Simple mode 프리셋 선택 → config 모델 자동 변경 확인
- [x] Provider health check RPC 응답 확인
- [x] Fallback 발생 시 사용자 알림 표시 확인
- [x] "모델 ID" 같은 기술 용어가 simple mode에서 보이지 않음
- [x] **자율 Agent 원칙**: 프리셋이 config를 설정하는 것이지, 코드가 LLM tool 선택을 제한하지 않음
