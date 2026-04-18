# P1-08: Use-case 기반 온보딩

**우선순위**: P1 — Public Beta 품질
**요구사항 섹션**: 5.2
**상태**: Complete (Phase 1·2·3·4 + UX bridging 완료 · E2E 검증만 잔존)
**의존성**: P0-02 (secure credential), P0-03 (startup diagnostics)

---

## 구현 현황 (2026-04-14)

### 완료
- **Phase 1 Welcome + Use-case 선택** (`OnboardingWizard.tsx`)
  - 6개 use case 카드 (data_analysis / reporting / prediction / dashboard / sql_exploration / general)
  - 각 카드에 `starterPrompt`, `systemContext` 포함
  - 자율 Agent 원칙 명시한 카피 ("does not lock the agent into a fixed workflow")
- **Phase 2 연결 단계** — model groups 로 추상화 (oauth / free_api_key / api_key / local)
- **Phase 4 설정 반영 + 재실행**
  - `agent.use_case_hint` / `agent.use_case_context` config 저장
  - SettingsPanel 의 "Restart Onboarding" 버튼 → `configStore.resetOnboarding()`
    가 localStorage 의 `ds-agent-onboarded(-v2)` 키도 클리어
- **Backend wiring**: `AgentConfig.use_case_hint/context` (`config/schema.py`) →
  `agent_session_registry` → `create_agent` → `build_prompt_builder` →
  `PromptBuilder._build_use_case_context()` 가 system prompt 에 use-case section 주입.
  Hint humanizer (`Data Analysis`, `Sql Exploration` 등).
- **UX bridging — starter prompt → chat input pre-fill**
  - `configStore.pendingStarterPrompt` 슬롯 + `setPendingStarterPrompt` /
    `consumePendingStarterPrompt`
  - 온보딩 완료 시 wizard 가 선택한 use case 의 `starterPrompt` 를 store 에 stage
  - `ChatInput` 첫 mount 에서 한 번만 픽업 → 텍스트 채움 + focus + caret 이동.
    재마운트/HMR 에도 다시 발화 안 됨.
- **App.tsx ↔ wizard contract 정합화**
  - `OnboardingResult = { model, useCaseId, starterPrompt }` 타입 export.
  - 기존 `{model, qualityPreset}` destructuring 버그 제거 (qualityPreset 필드는 wizard 가
    더 이상 다루지 않음 — `useAgentStore.setQualityPreset` 호출도 제거).
- **Backend tests** (변경 없음, 기존 그대로 green)
  - `tests/unit/application/test_prompt_builder.py::test_use_case_context_included`
  - `tests/unit/infrastructure/test_agent_session_registry.py::test_create_agent_passes_use_case_context`
- **검증**: `tsc --noEmit` exit 0, unit 1280 pass.

### Phase 3 sample 데이터셋 (완료 2026-04-14)
- **샘플 자산** (`electron/resources/sample-data/`):
  - `sample_sales_data.csv` (40 rows, 8 cols — data_analysis / dashboard / sql_exploration / general)
  - `sample_customer_survey.csv` (35 rows — reporting)
  - `sample_churn_data.csv` (50 rows, churn 라벨 포함 — prediction)
  - `manifest.json` — use case → 파일/라벨/설명/스키마 매핑 (general fallback 포함)
- **번들링**: `electron/electron-builder.yml` 의 `extraResources` 에
  `resources/sample-data → sample-data` 추가. 설치된 앱에서는
  `process.resourcesPath/sample-data/` 로 접근.
- **Main process**: `electron/src/main/sample-data.ts`
  - `resolveSampleDataDir()` — dev (`__dirname/../../resources/sample-data`) vs
    packaged (`process.resourcesPath/sample-data`) 자동 분기.
  - `loadSampleForUseCase(id)` — manifest 캐시, base64 페이로드 반환,
    use case 미매핑 시 `general` fallback.
- **IPC**: `samples:loadForUseCase` 핸들러 (`electron/src/main/ipc.ts`),
  preload 에서 `electronAPI.loadSampleForUseCase(useCaseId)` 노출,
  `vite-env.d.ts` 타입 정의 갱신.
- **OnboardingWizard `done` 단계 듀얼 CTA**:
  - "Try with sample data" → `loadSampleForUseCase` → `rpc('files.upload')` →
    starter prompt 를 `Use the file ... that was just uploaded ...` 접두로 보강 →
    `setPendingStarterPrompt` → `onComplete`.
  - "I'll bring my own data" → 기존 흐름.
  - `electronAPI.loadSampleForUseCase` 미존재 시 sample CTA 자동 숨김 (web 호환).
- **자율 Agent 원칙 유지**: 코드는 분석 단계를 hard-code 하지 않음. sample 업로드 +
  starter prompt 만 채워주고, 실제 분석 흐름은 LLM 이 자율 결정.

### 잔존
- **E2E 자동화**: 패키지된 Electron 앱이 빌드된 환경에서만 의미. P0-05 / P0-06 Phase 2 와
  함께 Playwright 시나리오 추가 (sample 업로드 → 첫 분석 응답 도착까지 5 분 이내).
- **샘플 데이터 i18n**: 현재는 영어 컬럼/코멘트. P1-13 (i18n) 진행 시 KO 변형 추가 가능.

---

---

## 자율 Agent 원칙 확인

> **이 온보딩은 LLM에게 hint를 주는 것이지 코드가 path를 분기시키는 게 아니다.**
> 사용자가 "CSV 분석"을 선택하면 그 정보가 system prompt context에 추가되어
> LLM이 자율적으로 해석한다. 코드는 고정 워크플로를 실행하지 않는다.

---

## 현재 상태

- 기본 OnboardingWizard 컴포넌트 존재
- 현재 온보딩: "어떤 모델/프로바이더 사용?" 중심
- 목표: "어떤 일을 하고 싶은지?" 중심으로 재설계

---

## 온보딩 흐름 설계

```
Step 1: Welcome          — 한 문장 가치 제안
Step 2: Use-case 선택    — 비기술 용어로 목적 선택 → system prompt hint 생성
Step 3: 데이터 연결      — API key / Google 로그인 / 로컬 LLM / 데모 모드
Step 4: 샘플 체험        — 예제 데이터셋으로 첫 분석 완료 (5분 이내)
Step 5: 완료             — 설정 화면 안내
```

### Step 2: Use-case 카드 (→ system prompt context로 변환)

```
[📊 데이터 분석]          [📋 Excel/리포트 작성]
"CSV나 Excel 파일을       "데이터를 깔끔한 보고서로
 탐색하고 싶어요"          만들고 싶어요"

[🔍 SQL 데이터 조회]      [🤖 예측 모델 만들기]
"DB에서 원하는            "고객 이탈이나 매출을
 데이터를 뽑고 싶어요"     예측하고 싶어요"

[📈 대시보드/차트]        [🔧 기타/직접 입력]
"데이터를 시각화하고       "원하는 방식으로
 싶어요"                   시작할게요"
```

**각 카드 선택 → system prompt에 추가되는 context**:
```python
USE_CASE_CONTEXT = {
    "data_analysis": "사용자는 주로 CSV/Excel 데이터 탐색에 관심이 있습니다. 기술 용어보다 쉬운 설명을 선호합니다.",
    "reporting": "사용자는 분석 결과를 보고서 형태로 받고 싶어합니다. 결과를 Markdown 표와 요약으로 제시하세요.",
    "prediction": "사용자는 머신러닝 모델링에 관심이 있습니다. 전문 용어 사용 시 간략히 설명을 추가하세요.",
    # ...
}
```

---

## 구현 Phase 계획

### Phase 1: Welcome + Use-case 선택

**수정 파일**: `electron/src/renderer/components/onboarding/`

**새 파일**: `OnboardingWizard.tsx` (기존 재설계)

```tsx
const ONBOARDING_STEPS = ['welcome', 'use_case', 'connect', 'sample', 'done'];

export function OnboardingWizard() {
  const [step, setStep] = useState<OnboardingStep>('welcome');
  const [selectedUseCase, setSelectedUseCase] = useState<UseCase | null>(null);

  return (
    <div className="onboarding-wizard" data-testid="onboarding-wizard">
      <ProgressBar steps={ONBOARDING_STEPS} current={step} />
      {step === 'welcome' && <WelcomeStep onNext={() => setStep('use_case')} />}
      {step === 'use_case' && (
        <UseCaseStep
          onSelect={(uc) => { setSelectedUseCase(uc); setStep('connect'); }}
        />
      )}
      {step === 'connect' && (
        <ConnectStep
          useCase={selectedUseCase}
          onDemoMode={() => setStep('sample')}
          onConnected={() => setStep('sample')}
        />
      )}
      {step === 'sample' && (
        <SampleStep useCase={selectedUseCase} onDone={() => setStep('done')} />
      )}
      {step === 'done' && <DoneStep />}
    </div>
  );
}
```

**새 파일**: `UseCaseStep.tsx`

```tsx
const USE_CASES: UseCaseCard[] = [
  {
    id: 'data_analysis',
    icon: '📊',
    title: '데이터 분석',
    description: 'CSV나 Excel 파일을 탐색하고 싶어요',
    samplePrompt: '업로드한 CSV 파일에서 주요 통계와 패턴을 찾아줘',
  },
  {
    id: 'reporting',
    icon: '📋',
    title: '리포트 작성',
    description: '데이터를 깔끔한 보고서로 만들고 싶어요',
    samplePrompt: '이 데이터를 팀장에게 보낼 수 있는 요약 보고서로 만들어줘',
  },
  // ... 나머지 카드
];

export function UseCaseStep({ onSelect }: { onSelect: (uc: UseCase) => void }) {
  return (
    <div>
      <h2>어떤 일을 하고 싶으신가요?</h2>
      <p className="text-muted">목적에 맞게 AI를 설정합니다. 나중에 언제든 변경할 수 있어요.</p>
      <div className="use-case-grid">
        {USE_CASES.map(uc => (
          <UseCaseCard key={uc.id} card={uc} onClick={() => onSelect(uc)} />
        ))}
      </div>
    </div>
  );
}
```

---

### Phase 2: 연결 단계 (모델/프로바이더 추상화)

**원칙**: "모델"/"프로바이더" 단어 사용 금지. 대신 "AI 연결 방법" 사용.

**새 파일**: `ConnectStep.tsx`

```tsx
const CONNECTION_OPTIONS = [
  {
    id: 'anthropic',
    label: 'Claude (Anthropic)',
    description: '가장 정확합니다. Anthropic API 키가 필요합니다.',
    badge: '추천',
    inputLabel: 'API 키 입력',
    helpUrl: 'https://ds-agent.app/help/anthropic-key',
  },
  {
    id: 'openai',
    label: 'ChatGPT (OpenAI)',
    description: 'OpenAI API 키가 있다면 바로 사용할 수 있습니다.',
    inputLabel: 'API 키 입력',
  },
  {
    id: 'local',
    label: '내 컴퓨터에서 실행',
    description: '인터넷 없이, 무료로 사용할 수 있습니다. 처음 설치에 시간이 걸립니다.',
    badge: '무료',
    action: 'install_ollama',
  },
  {
    id: 'demo',
    label: '데모로 먼저 둘러보기',
    description: 'API 키 없이도 샘플 데이터로 체험할 수 있습니다.',
    badge: '빠른 시작',
  },
];
```

---

### Phase 3: 샘플 체험 (첫 성공 경험)

선택한 use-case에 맞는 샘플 데이터셋을 자동으로 로드하고 첫 분석을 guided로 실행.

**자율 Agent 원칙**: 코드가 분석 단계를 hard-code하지 않음.
샘플 데이터를 업로드하고, use-case에 맞는 starter prompt를 chat input에 pre-fill.
LLM이 자율적으로 분석 진행.

**새 파일**: `SampleStep.tsx`

```tsx
const SAMPLE_DATA: Record<UseCase['id'], SampleDataset> = {
  data_analysis: {
    filename: 'sample_sales_data.csv',
    label: '3개월 매출 데이터 (예시)',
    starterPrompt: '이 파일에서 어떤 제품이 가장 많이 팔렸는지 알려줘',
  },
  reporting: {
    filename: 'sample_customer_survey.csv',
    label: '고객 만족도 조사 결과 (예시)',
    starterPrompt: '이 설문 결과를 경영진에게 보고할 수 있는 요약 보고서로 만들어줘',
  },
  prediction: {
    filename: 'sample_churn_data.csv',
    label: '고객 이탈 데이터 (예시)',
    starterPrompt: '이 데이터로 이탈 가능성이 높은 고객을 예측하는 모델을 만들어줘',
  },
};

export function SampleStep({ useCase, onDone }: Props) {
  const dataset = SAMPLE_DATA[useCase?.id ?? 'data_analysis'];

  return (
    <div>
      <h2>첫 분석을 시작해볼게요!</h2>
      <SampleFilePreview dataset={dataset} />
      <p>아래 질문을 AI에게 보내면 바로 분석이 시작됩니다:</p>
      <div className="starter-prompt-preview">
        <q>{dataset.starterPrompt}</q>
      </div>
      <Button onClick={() => launchChatWithPrompt(dataset)} variant="primary">
        분석 시작하기 →
      </Button>
    </div>
  );
}
```

**샘플 데이터 파일 위치**: `electron/resources/sample-data/`

---

### Phase 4: 온보딩 재실행 + 설정 반영

```tsx
// 설정 화면에서 언제든 재실행 가능
function SettingsPanel() {
  return (
    <Button variant="ghost" onClick={restartOnboarding}>
      온보딩 다시 시작
    </Button>
  );
}

// use-case 선택 → config에 저장
async function saveUseCaseSelection(useCase: UseCase) {
  await window.dsAgent.config.set('agent.use_case_hint', useCase.id);
  await window.dsAgent.config.set('agent.use_case_context', USE_CASE_CONTEXT[useCase.id]);
}
```

**수정 파일**: `src/ds_agent/config/schema.py`

```python
class AgentConfig(BaseModel):
    # 기존 필드들
    use_case_hint: str | None = None       # 온보딩에서 선택한 use case
    use_case_context: str | None = None    # LLM system prompt에 추가될 context
```

---

## Quality Gate

- [ ] E2E: 온보딩 화면이 첫 실행 시 자동으로 표시됨
- [ ] E2E: use-case 선택 후 system prompt에 context 반영 확인
- [ ] E2E: 데모 모드로 샘플 데이터 분석 완료 (5분 이내)
- [ ] E2E: 온보딩 완료 후 채팅 화면 전환 확인
- [ ] UX: "모델", "프로바이더", "API" 같은 기술 용어가 use-case/connect step에서 보이지 않음
- [ ] **자율 Agent 원칙**: use-case 선택이 코드 flow 분기가 아닌 LLM context 제공임을 확인
