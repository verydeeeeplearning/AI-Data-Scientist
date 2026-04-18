# P1-13: i18n (한국어) & 접근성 (a11y)

**우선순위**: P1
**요구사항 섹션**: 5.18
**상태**: Complete — i18n 완료, 접근성 1차 audit 완료 (2026-04-15)
**의존성**: 없음 (독립 구현)

## 접근성 1차 audit (2026-04-15)

modal/overlay 류 컴포넌트의 ARIA 노출 상태를 점검하고 부족한 부분 보강:

| 컴포넌트 | 변경 |
|---------|------|
| `SandboxApprovalModal.tsx` | 신규 작성 시 이미 `role="dialog"` + `aria-modal` + `aria-labelledby` + Esc=reject 배선 |
| `SandboxViolationToast.tsx` | `role="status"` + `aria-live="polite"` (스크린 리더가 toast 인지) |
| `FilePreviewModal.tsx` | `role="dialog"` + `aria-modal` + `aria-labelledby="file-preview-title"`, close 버튼 `aria-label` 추가 |
| `PlotGallery` plot modal | `role="dialog"` + `aria-modal` + `aria-labelledby="plot-gallery-title"` |
| `DiagnosticPanel.tsx` | 외곽을 `<main role="main" aria-labelledby="diagnostic-title">` 로 변경, decorative icon `aria-hidden="true"` |
| `DisconnectOverlay.tsx` | `role="alertdialog"` + `aria-modal` + `aria-labelledby` + `aria-describedby` |
| `SettingsPanel.tsx` | `role="dialog"` + `aria-modal` + `aria-labelledby="settings-title"`, 백드롭 `aria-hidden`, close 버튼 `aria-label` |

`npm run typecheck` clean.

### 잔존 (post-beta 가능)
- 진정한 focus trap (현재는 modal 열림 시 첫 element auto-focus 만 — Tab 키가 modal 밖으로 이동 가능)
- color contrast WCAG AA 자동 측정 (axe-core 등 도구 도입 시점에)
- 키보드 단축키 도움말 패널 (`?` 키로 표시 등)

---

## 2026-04-15 진행 상황

기존 `electron/src/renderer/stores/i18nStore.ts` (zustand 기반 locale + 번역 map)
이 이미 존재하여 react-i18next 대신 해당 store 를 확장하는 방향으로 통합했다.

| 항목 | 상태 | 구현 위치 |
|------|------|-----------|
| UI locale toggle (KO / EN) | ✅ 기존 | `stores/i18nStore.ts`, `SettingsPanel` Language section |
| Agent system prompt 언어 반영 | ✅ | `agent/prompt_builder.py` _LANGUAGE_INSTRUCTIONS + 필수 섹션 |
| AgentConfig.language 필드 | ✅ | `config/schema.py` (default `"ko"`) |
| 설정 변경 시 backend sync | ✅ | `SettingsPanel` handleLanguageChange → `config.set agent.language` |
| 부팅 시 backend locale 복원 | ✅ | `SettingsPanel` mount effect → `config.get` |
| Allowed config paths 등록 | ✅ | `routes/config.py`, `api/config_manager.py` persistent scope |
| 전체 UI 키 한국어 번역 | 부분 (주요 서피스) | `i18nStore` translations |
| a11y 기본 패스 (aria / focus / keyboard) | ⏳ 보류 | 별도 PR 권장 |
| axe-core CI 통합 | ⏳ 보류 | Playwright 통합 시 함께 |

---

## 아직 남은 작업

- 미번역 서피스 잔여: `ProjectPanel`, `AdminConsole`, `ConnectorWizard`, 워크플로/실험 패널 등
- a11y 패스: 모달 focus trap, 색상 외 상태 표시, 키보드 네비게이션 QA
- Agent 응답 언어 smoke E2E: ko 설정 → 질문 → 한국어 응답 확인
- axe-core CI 통합

## 2026-04-15 세션 추가 작업

- `i18nStore.t()` 가 `{{var}}` interpolation 지원. `t('sidebar.deleteConfirm', { name })` 패턴 사용 가능
- `FileUpload`: validation 에러 메시지, 상단 힌트, 초과 경고, 성공/실패 배너 전부 key 기반으로 전환
- `FileExplorer`: 헤더 · 빈 상태 · hover 액션(미리보기/내보내기/삭제) · confirm/alert 전부 한국어 지원, 아이콘 버튼에 `aria-label` 추가
- `PlotGallery`: 헤더, 빈 상태, 썸네일/모달 삭제 confirm + aria-label
- `UpdateNotification`: `.replace()` 수작업 대체, `t()` interpolation 사용
- 신규 sidebar.* 키 20+ 추가 (ko/en)

## 검증 완료

- `PromptBuilder(language="ko").build()` 결과 system content 에 한국어 지시 포함 (unit test 4개 추가)
- `PromptBuilder(language="en")` 결과에 English 지시 포함
- `agent.language` 가 `ALLOWED_CONFIG_PATHS` 및 `PERSISTENT_CONFIG_PATHS` 양쪽에 등록되어 있어 `config.set` 수용 + 디스크에 영속

---

## 개요

한국 시장 출시 시 영어 UI는 진입 장벽. 접근성은 기업 고객 조달 시 필수.

---

## 구현 Phase 계획

### Phase 1: i18n 프레임워크 설정 (Electron + React)

**라이브러리**: `react-i18next` + `i18next`

**새 파일**: `electron/src/renderer/i18n/index.ts`

```typescript
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import ko from './locales/ko.json';
import en from './locales/en.json';

i18n.use(initReactI18next).init({
  resources: { ko: { translation: ko }, en: { translation: en } },
  lng: navigator.language.startsWith('ko') ? 'ko' : 'en',  // 시스템 언어 감지
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});
```

**새 파일**: `electron/src/renderer/i18n/locales/ko.json`

```json
{
  "onboarding": {
    "welcome_title": "DS Agent에 오신 것을 환영합니다",
    "welcome_subtitle": "데이터 분석을 AI와 함께 쉽게 시작하세요",
    "use_case_question": "어떤 일을 하고 싶으신가요?",
    "connect_title": "AI 연결 방법을 선택하세요",
    "demo_mode_btn": "데모로 먼저 둘러보기"
  },
  "chat": {
    "input_placeholder": "데이터에 대해 무엇이든 물어보세요...",
    "send_btn": "전송",
    "thinking": "분석 중..."
  },
  "errors": {
    "DSA-AUTH-001": "API 키가 유효하지 않습니다. 설정에서 API 키를 확인하세요.",
    "DSA-LLM-001": "AI 서비스에 일시적인 문제가 있습니다. 잠시 후 다시 시도하세요.",
    "DSA-LLM-002": "이번 달 사용 한도에 도달했습니다.",
    "DSA-SAND-001": "코드가 허용되지 않은 파일에 접근하려 했습니다."
  },
  "settings": {
    "title": "설정",
    "api_keys": "API 키",
    "cost": "비용",
    "language": "언어",
    "theme": "테마",
    "dark": "다크",
    "light": "라이트",
    "system": "시스템 설정 따름"
  },
  "cost": {
    "this_month": "이번 달 사용",
    "budget": "한도",
    "cache_savings": "캐싱으로 {{amount}} 절약",
    "session": "세션",
    "today": "오늘"
  },
  "data": {
    "upload_hint": "파일을 여기에 끌어다 놓거나 클릭하여 선택하세요",
    "supported_formats": "지원 형식: CSV, Excel, Parquet, JSON",
    "preview_rows": "{{count}}행 미리보기",
    "null_values_notice": "일부 열에 빈 칸이 있습니다. AI가 자동으로 처리합니다."
  }
}
```

**사용법**:

```tsx
import { useTranslation } from 'react-i18next';

function ChatInput() {
  const { t } = useTranslation();
  return (
    <input
      placeholder={t('chat.input_placeholder')}
      aria-label={t('chat.input_placeholder')}
    />
  );
}
```

---

### Phase 2: Agent 응답 언어 반영

LLM 응답도 사용자 언어로 받아야 한다.

**수정 파일**: `src/ds_agent/config/schema.py`

```python
class AgentConfig(BaseModel):
    language: str = "ko"  # 시스템 언어 기본값
    # ...
```

**수정 파일**: Agent system prompt

```python
def build_system_prompt(config: DSAgentConfig) -> str:
    lang_instruction = {
        "ko": "모든 응답은 한국어로 작성하세요. 코드 주석도 한국어로.",
        "en": "Respond in English.",
        "ja": "すべての回答を日本語で書いてください。",
    }.get(config.agent.language, "Respond in English.")

    return f"{DS_AGENT_BASE_PROMPT}\n\n{lang_instruction}"
```

---

### Phase 3: 언어 설정 UI

**새 파일**: `electron/src/renderer/components/settings/LanguageSettings.tsx`

```tsx
export function LanguageSettings() {
  const { i18n } = useTranslation();

  const LANGUAGES = [
    { code: 'ko', label: '한국어' },
    { code: 'en', label: 'English' },
  ];

  return (
    <FormField label={t('settings.language')}>
      <Select
        options={LANGUAGES}
        value={i18n.language}
        onChange={async (lang) => {
          await i18n.changeLanguage(lang);
          await window.dsAgent.config.set('agent.language', lang);
        }}
      />
    </FormField>
  );
}
```

---

### Phase 4: 접근성 (a11y) 기본 패스

**체크리스트 기반 작업**:

**1. ARIA 레이블**

```tsx
// Before
<button onClick={send}>→</button>

// After
<button onClick={send} aria-label={t('chat.send_btn')}>→</button>
```

**2. 포커스 관리**

```tsx
// 다이얼로그 열릴 때 첫 번째 요소로 포커스 이동
function Modal({ onClose }: Props) {
  const firstFocusRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { firstFocusRef.current?.focus(); }, []);

  // ESC 키로 닫기
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <button ref={firstFocusRef} onClick={onClose} aria-label="닫기">×</button>
      ...
    </div>
  );
}
```

**3. 색상에만 의존하지 않는 정보 전달**

```tsx
// Before: 색상만으로 상태 표시
<div className={`badge ${status === 'ok' ? 'green' : 'red'}`} />

// After: 색상 + 텍스트 + 아이콘
<div className={`badge badge-${status}`} role="status">
  {status === 'ok' ? '✓ 정상' : '✗ 오류'}
</div>
```

**4. 키보드 네비게이션**

```tsx
// 드롭다운 메뉴 키보드 지원
function DropdownMenu({ children }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div
      role="menu"
      onKeyDown={(e) => {
        if (e.key === 'ArrowDown') focusNextItem();
        if (e.key === 'ArrowUp') focusPrevItem();
        if (e.key === 'Enter' || e.key === ' ') activateItem();
        if (e.key === 'Escape') setOpen(false);
      }}
    >
      {children}
    </div>
  );
}
```

**5. axe-core 자동 검사 통합**

**새 파일**: `electron/src/renderer/a11y-check.ts` (개발 모드에서만)

```typescript
if (import.meta.env.DEV) {
  import('axe-core').then(({ default: axe }) => {
    axe.run().then((results) => {
      if (results.violations.length > 0) {
        console.error('A11y violations:', results.violations);
      }
    });
  });
}
```

**CI 접근성 테스트**:

```typescript
// Playwright + axe
import { checkA11y, injectAxe } from 'axe-playwright';

test('chat page has no a11y violations', async ({ page }) => {
  await injectAxe(page);
  await checkA11y(page, undefined, {
    detailedReport: true,
    detailedReportOptions: { html: true },
  });
});
```

---

## Quality Gate

- [ ] 한국어 UI로 전체 온보딩 완료 가능
- [ ] 시스템 언어 한국어 시 앱 자동으로 한국어 표시
- [ ] agent 응답이 선택한 언어로 출력 (system prompt 반영)
- [ ] axe-core 기준 critical violations 0개
- [ ] 모든 대화형 요소에 aria-label 존재
- [ ] 키보드만으로 핵심 기능(업로드, 채팅, 설정) 사용 가능
- [ ] 색상 없이도 상태(오류/성공/경고) 구분 가능
