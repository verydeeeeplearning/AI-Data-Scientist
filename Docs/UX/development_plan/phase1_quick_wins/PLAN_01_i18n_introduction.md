# PLAN 01: i18n ?袁⑹뿯 (??볥럢???怨쀪퐨)

**Status**: In Progress
**Started**: ??
**Last Updated**: 2026-04-19
**Phase**: 1 (Quick Wins)
**Estimated Effort**: 5?? ?臾믩씜??

**ROADMAP 筌띲끋釉?*: 吏?.12 i18n & ?臾롫젏????"UI i18n ?袁⑹뿯 (筌ㅼ뮇???"
**?온??Cross-cutting**: [`../cross_cutting/PLAN_01_accessibility.md`](../cross_cutting/PLAN_01_accessibility.md)

> **?夷?AI Agent ??덇땀**: 癰?PLAN????뽰삂??띾┛ ??[`SHARED/`](../SHARED/) ??`GLOSSARY.md`, `CONVENTIONS.md`, `INTEGRATION_POINTS.md`, `DECISIONS.md`, `DEVELOPMENT_LOG.md`, `ACTIVE_WORK.md` ??筌뤴뫀紐??類ㅼ뵥??랁?[`00_overview/06_AGENT_COORDINATION.md`](../00_overview/06_AGENT_COORDINATION.md) ??protocol???怨뺚뀲?? ?臾믩씜 ?袁⑥┷ ??吏?1 筌욊쑵六??곕뗄?? 吏?2 Notes & Learnings, 域밸챶?곫?SHARED??`DEVELOPMENT_LOG.md` / `ACTIVE_WORK.md` / `INTEGRATION_POINTS.md` ??獄쏆꼶諭??揶쏄퉮???뺣뼄.

---

## 1. 揶쏆뮇??

### 1.1 疫꿸퀡????살구
Electron renderer??筌뤴뫀諭?UI ??용뮞?紐? i18n ??살쨮 ?곕뗄???랁? ??볥럢???怨몃선/??곕궚??3揶?locale??筌왖?癒곕립?? ????癒?뮉 onboarding 筌???ｍ??癒?뮉 Settings?癒?퐣 locale???醫뤾문??뺣뼄. LLM ?臾먮뼗 ?紐꾨선?? UI ?紐꾨선??**??끸뵲**?怨몄뵠筌왖筌? ?醫됲뇣 ????癒?뮉 ??揶쎛筌왖 ?紐꾨선嚥??類ｌ졊??筌??紐꾧맒??獄쏆룆???

### 1.2 ?源껊궗 疫꿸퀣?
- [ ] 筌뤴뫀諭?揶쎛??UI ??용뮞?硫? i18n ?????궢 (??롫굡?꾨뗀逾?0椰?
- [ ] ko/en/ja 3揶?locale ?袁⑹읈 甕곕뜆肉?(ko ?怨쀪퐨, ja??LLM ?癒?짗 甕곕뜆肉?+ 野꺜??
- [ ] Locale ?袁れ넎 ????륁뵠筌왖 ??덉쨮?⑥쥙臾???곸뵠 筌앸맩??獄쏆꼷??
- [ ] CJK ????꾨７ 筌ㅼ뮇???(font-feature-settings, line-height 鈺곌퀣??
- [ ] ?袁⑥뵭 ???癒?짗 野꺜??(CI fail)

### 1.3 Out of Scope
- LLM ?臾먮뼗 ?紐꾨선 揶쏅벡??(??? system prompt嚥?筌ｌ꼶???
- RTL ?紐꾨선 筌왖??(癰귢쑬猷?phase)
- ??덉읅 plural rules??癰귣벊????냈??곷뮞 (疫꿸퀡??plural筌?

---

## 2. ?????揶쎛燁?& ?源껊궗 筌왖??

| 筌왖??| Baseline | Phase 1 ?ル굝利???筌뤴뫚紐?| 筌β돦??|
|------|----------|---------------------|------|
| ??볥럢??UI ???????쑴??| 25% | > 525% (??볥럢 IP) | locale ?醫뤾문 telemetry |
| ??볥럢???????D7 retention | 筌β돦???븍뜃? | +225%p (?怨몃선 UI ???? | analytics |
| "UI???怨몃선揶쎛 ??롫연 ??덈뼄" ??곕굡獄?| ?類ㅺ쉐 | 0椰?| in-app feedback |

ROADMAP mapping: §6.5 Accessibility — "Korean UI adoption > 50%"

---

## 3. ?袁⑹삺 ?怨밴묶 ?브쑴苑?

### 3.1 ?袁れ넺
- LLM ?臾먮뼗: ko/ja/en 筌뤴뫀紐?筌왖??(`prompt_builder` 筌ｌ꼶??
- UI ??용뮞?? ?怨몃선筌? 筌뤴뫀紐??뚮똾猷??곕뱜????롫굡?꾨뗀逾?
- `electron/src/renderer/stores/i18nStore.ts` ??store-backed locale metadata / translation baseline / `ko|en|ja` ?꾪솚???대? ?쒓났?섏?留?full i18next migration ? ?꾩쭅 誘몄셿猷?- ??용뮞???브쑬???곕뗄?? 300??00揶???(??삳쐭, 甕곌쑵?? ??곌볼, 筌롫뗄?놅쭪?)

### 3.2 揶??브쑴苑?
- **i18n ??깆뵠?됰슢??뵳?沃섎챶猷??*: react-i18next, formatjs ??沃섎챷苑뺟㎉?
- **string ?곕뗄???袁㏓럡 ?봔??*: ?癒?짗 ?곕뗄???袁⑥뵭 野꺜?????뵠?袁⑥뵬????곸벉
- **甕곕뜆肉???곌쾿???쨮???봔??*: ?袁? ??堉멨칰?甕곕뜆肉??곕떽?/野꺜??묐막筌왖 沃섎챷??

---

## 4. Clean Architecture 筌띲끋釉?

癰?疫꿸퀡??? [`../00_overview/02_CLEAN_ARCHITECTURE_MAPPING.md`](../00_overview/02_CLEAN_ARCHITECTURE_MAPPING.md) ???뚢뫀源??륁뱽 ?怨뺚뀲??

| ??됱뵠??| ?뚮똾猷??곕뱜 | 筌?굞??|
|--------|----------|------|
| **Domain** | `renderer/domain/locale.ts` (?醫롪퐬) | `Locale` 揶?揶쏆빘猿? supported locale enum, validation |
| **Application** | `renderer/application/locale/setLocale.ts`, `detectLocale.ts` | locale 癰궰野? ??뽯뮞??locale ?곕뗀以?|
| **Infrastructure** | `renderer/infrastructure/i18n/i18nClient.ts`, `localeStorage.ts` | i18next ?紐꾨뮞??곷뮞 wrapping, localStorage ?怨몃꺗 |
| **Presentation** | `renderer/components/settings/LocaleSelector.tsx`, `useTranslation` hook | UI ?뚮똾猷??곕뱜, ??|

### 4.1 Port Interface (?袁⑥컭?紐꾩뵠 ?類ㅼ벥)

```typescript
// renderer/domain/ports/translationPort.ts
export interface TranslationPort {
  t(key: string, params?: Record<string, unknown>): string;
  changeLocale(locale: Locale): Promise<void>;
  getCurrentLocale(): Locale;
  onLocaleChange(handler: (locale: Locale) => void): () => void;
}
```

`i18next` ?닌뗭겱筌ｋ???`infrastructure/i18n/i18nextAdapter.ts` ???袁⑺뒄.

---

## 5. ?怨쀬뵠??筌뤴뫀??& ?紐낃숲??륁뵠??

### 5.1 Locale ?袁⑥컭??揶쏆빘猿?

```typescript
// renderer/domain/locale.ts
export type LocaleCode = 'ko' | 'en' | 'ja';

export class Locale {
  static readonly KO = new Locale('ko', '??볥럢??, 'ko-KR');
  static readonly EN = new Locale('en', 'English', 'en-US');
  static readonly JA = new Locale('ja', '?瓘?띷쾬?, 'ja-JP');

  static all(): Locale[] { return [Locale.KO, Locale.EN, Locale.JA]; }
  static fromCode(code: string): Locale { /* validation + lookup */ }

  private constructor(
    readonly code: LocaleCode,
    readonly displayName: string,
    readonly bcp47: string,
  ) {}
}
```

### 5.2 ????쇱뵠獄?域뱀뮇??

```
<feature>.<sub_feature>.<element>[.<state>]
```

??됰뻻:
- `mission.header.budget.label` ??"??됯텦"
- `mission.header.budget.warning` → "예산 80% 도달"
- `chat.message.copy.success` ??"癰귣벊沅??
- `onboarding.step1.title` ??"?얜똻毓????랁???좎몵?醫???"

### 5.3 甕곕뜆肉????뵬 ?닌듼?

```
electron/src/renderer/locales/
????? ko/
??  ????? common.json      # 甕곌쑵?? ?⑤벏????る?
??  ????? mission.json     # Mission ?怨몃열
??  ????? chat.json        # Chat ?怨몃열
??  ????? onboarding.json
??  ????? settings.json
??  ?遺??? ...
????? en/
??  ?遺??? (??덉뵬 ?닌듼?
?遺??? ja/
    ?遺??? (??덉뵬 ?닌듼?
```

namespace ?브쑵釉룡에?lazy loading 揶쎛??

### 5.4 ??뽯뮞??locale ?곕뗀以?

```typescript
// renderer/application/locale/detectLocale.ts
export function detectInitialLocale(opts: {
  systemLocale: string,    // navigator.language
  storedLocale?: string,   // localStorage
  fallback: LocaleCode,
}): Locale {
  if (opts.storedLocale) return Locale.fromCode(opts.storedLocale);
  const code = opts.systemLocale.split('-')[0];
  if (['ko', 'en', 'ja'].includes(code)) return Locale.fromCode(code);
  return Locale.fromCode(opts.fallback);
}
```

---

## 6. ???뮞???袁⑥셽

癰?疫꿸퀡??? [`../00_overview/03_TEST_STRATEGY.md`](../00_overview/03_TEST_STRATEGY.md) ????????怨뺚뀲??

| ???뮞???ル굝履?| ????| ?뚣끇苡?뵳?? |
|------------|------|----------|
| Unit (Domain) | `Locale`, `detectInitialLocale` | 100% |
| Unit (Application) | `setLocale` use case | >=90% |
| Integration | `LocaleSelector` + i18nextAdapter | ???뼎 野껋럥以?|
| E2E | Onboarding 筌???ｍ?癒?퐣 locale ?醫뤾문, ?袁⑷퍥 UI ??볥럢????뽯뻻 | golden path |
| ??볦퍟 ??? | Mission Header / Chat / Settings ko/en/ja 3??| ?뚮똾猷??곕뱜癰?|
| i18n ?袁⑥뵭 野꺜??| `i18next-parser` CI step | 0揶?|

### 6.1 ???뼎 ??μ맄 ???뮞??

```typescript
// renderer/domain/locale.test.ts
describe('Locale', () => {
  it('筌왖??locale 3??, () => {
    expect(Locale.all()).toHaveLength(3);
  });
  it('沃섎챷????꾨뗀諭??throw', () => {
    expect(() => Locale.fromCode('zh')).toThrow();
  });
});

// renderer/application/locale/detectLocale.test.ts
describe('detectInitialLocale', () => {
  it('???貫留?locale???怨쀪퐨 ????, () => {
    expect(detectInitialLocale({ systemLocale: 'en-US', storedLocale: 'ko', fallback: 'en' }))
      .toEqual(Locale.KO);
  });
  it('???貫留?揶???곸몵筌???뽯뮞??locale', () => {
    expect(detectInitialLocale({ systemLocale: 'ja-JP', fallback: 'en' }))
      .toEqual(Locale.JA);
  });
  it('筌왖?癒곕릭筌왖 ??낅뮉 ??뽯뮞??locale?? fallback', () => {
    expect(detectInitialLocale({ systemLocale: 'fr-FR', fallback: 'en' }))
      .toEqual(Locale.EN);
  });
});
```

---

## 7. ?닌뗭겱 Phase (RED ??GREEN ??REFACTOR)

### Sub-Phase 1.1: ??깆뵠?됰슢??뵳??袁⑹뿯 + Domain (1??

#### RED
- [ ] `renderer/domain/locale.test.ts` ?臾믨쉐 (??吏?.1 ???뮞??
- [ ] `renderer/application/locale/detectLocale.test.ts` ?臾믨쉐
- [ ] ??쎈뻬: 筌뤴뫀紐?fail ?類ㅼ뵥

#### GREEN
- [ ] `pnpm add i18next react-i18next i18next-browser-languagedetector`
- [ ] `pnpm add -D i18next-parser`
- [ ] `renderer/domain/locale.ts` ?臾믨쉐
- [ ] `renderer/application/locale/detectLocale.ts` ?臾믨쉐
- [ ] ???뮞??pass ?類ㅼ뵥

#### REFACTOR
- [ ] `LocaleCode` ????놁뱽 `Locale.code` ?癒?퐣 ?곕뗀以??롫즲嚥??類ｂ봺
- [ ] JSDoc ?곕떽?

### Sub-Phase 1.2: Infrastructure ?????+ i18nextAdapter (1??

#### RED
- [ ] `renderer/infrastructure/i18n/i18nextAdapter.test.ts` ?臾믨쉐
  - ??뺢돌?귐딆궎: changeLocale ??t() 野껉퀗??癰궰野?
  - ??뺢돌?귐딆궎: ?袁⑥뵭 ??삳뮉 missingKeyHandler ?紐꾪뀱

#### GREEN
- [ ] `renderer/infrastructure/i18n/i18nextAdapter.ts` ?臾믨쉐 (`TranslationPort` ?닌뗭겱)
- [ ] `renderer/infrastructure/i18n/index.ts` ?癒?퐣 setup ??λ땾 export
- [ ] `App.tsx` ?癒?퐣 setup ?紐꾪뀱

#### REFACTOR
- [ ] `i18nStore` ??`useTranslation` ??곗쨮 ?袁れ넎 (疫꿸퀣????쇳렩??딅꽑 ??볤탢)
- [ ] React.Suspense fallback 筌ｌ꼶??

### Sub-Phase 1.3: 甕곕뜆肉????뵬 ?곕뗄??+ ??볥럢??1筌?(2??

#### RED
- [ ] `i18next-parser.config.js` ?臾믨쉐 + CI step ?곕떽?
- [ ] CI ??쎈뻬 ???袁⑥뵭 ??detect

#### GREEN
- [ ] ?癒?짗 ?곕뗄????쎈뻬 ??en namespace ???뵬 ??밴쉐
- [ ] **??롫짗 ?臾믩씜**: ???뼎 ?遺얇늺 ??용뮞??i18n ??살쨮 ?대Ŋ猿?(?怨쀪퐨??뽰맄):
  1. ChatPanel
  2. Sidebar
  3. Mission Header (PLAN_02?? ??덈뻻 筌욊쑵六???
  4. Settings
  5. Onboarding
  6. Approval modal
- [ ] ??볥럢??甕곕뜆肉??臾믨쉐 (??롫짗 + glossary 疫꿸퀣?)
- [ ] ??곕궚??甕곕뜆肉?(LLM ?癒?짗 + 野꺜?? ?袁⑸떄??

#### REFACTOR
- [ ] ??筌뤿굝梨??뚢뫀源???????野꺜??
- [ ] 餓λ쵎????????

### Sub-Phase 1.4: LocaleSelector + Settings ???? (1??

#### RED
- [ ] `renderer/components/settings/LocaleSelector.test.tsx` ?臾믨쉐
  - ??????changeLocale ?紐꾪뀱
  - ?袁⑹삺 locale ??뽯뻻
  - ??삳궖????삵돩 揶쎛??

#### GREEN
- [x] `LocaleSelector` 而댄룷?뚰듃 ?묒꽦 (?꾩옱 custom selector surface)
- [x] Settings panel???듯빀
- [x] localStorage ?곸냽

#### REFACTOR
- [ ] ?臾롫젏???癒? (aria-label, role)

### Sub-Phase 1.5: Onboarding 筌???ｍ?+ CJK ????꾨７ (1??

#### RED
- [ ] E2E: Onboarding 筌?筌욊쑴????locale ?醫뤾문 ?遺얇늺 ?紐꾪뀱 野꺜筌?

#### GREEN
- [x] Onboarding step 0??locale ?좏깮 異붽?
- [ ] CJK ?怨좊뱜 ?곕떽? (Noto Sans CJK KR/JP), Tailwind config??font-family ?곕떽?
- [ ] CSS: `font-feature-settings`, line-height per locale

#### REFACTOR
- [ ] ??뽯뮞??locale ?癒?짗 揶쏅Ŋ?嚥?default ?醫뤾문

### Sub-Phase 1.6: CI / ??? ??됱읈筌?(0.5??

- [ ] CI??`i18next-parser --fail-on-warnings` ?곕떽?
- [ ] ??볦퍟 ??? baseline ?곕떽? (ko/en/ja 揶쏄낫而?
- [ ] missingKeyHandler 揶쎛 telemetry嚥?reporting

---

## 8. ??됱춳 野껊슣???

癰?phase??[`../00_overview/05_DEFINITION_OF_DONE.md 吏? Phase DoD`](../00_overview/05_DEFINITION_OF_DONE.md) ??筌뤴뫀諭??????筌띾슣???곷튊 ??뺣뼄.

### 癰?PLAN ?諭곸넅 野껊슣???
- [ ] `i18next-parser` ?袁⑥뵭 ??0揶?
- [ ] 筌뤴뫀諭?揶쎛????용뮞?硫? ko/en?癒?퐣 ?怨몄쟿????뽯뻻 (??롫짗 野꺜筌?
- [ ] CJK locale?癒?퐣 layout overflow ??곸벉 (??볦퍟 ???)
- [ ] Locale ?袁れ넎 ??React re-render ?類ㅺ맒
- [ ] LocaleSelector keyboard 鈺곌퀣??揶쎛??
- [x] localStorage ?곸냽

---

## 9. ?귐딅뮞??& 嚥▲끇媛?

### 癰?PLAN ?귐딅뮞??
| ID | ?귐딅뮞??| ?袁れ넅 |
|----|--------|------|
| U-03 (?袁⑸열) | ??볥럢??甕곕뜆肉???됱춳 ????| ?袁ⓓ?甕곕뜆肉???롅?+ glossary ?온?? ???????곕굡獄?筌?쑬瑗?|
| T-05 (?袁⑸열) | ?袁⑥뵭 ??살쨮 ?怨론?fallback ?紐꾪뀱 | `i18next-parser` CI fail-on-warnings + ?怨???missingKeyHandler ???뵝 |
| T-06 (?袁⑸열) | CJK ??용뮞??疫뀀챷??筌△뫁?졿에?layout overflow | ko/ja ??볦퍟 ??? baseline 揶쏅벡??|
| ?醫됲뇣-A | i18n ?袁⑹뿯??疫꿸퀣???뚮똾猷??곕뱜 ??? ?醫딆뻣 | sub-phase癰?PR ?브쑵釉? 揶?PR ??볦퍟 ??? 野꺜筌?|

### 嚥▲끇媛?
- **?봔??嚥▲끇媛?*: ?諭??namespace 甕곕뜆肉??袁⑥뵭 ??i18next???癒?짗??곗쨮 fallback locale ???????癒?짗
- **?袁ⓦ늺 嚥▲끇媛?*: i18next provider ??볤탢 + ?뚮똾猷??곕뱜 ??용뮞?紐껊뮉 commit history嚥?癰귣벊??
- **?怨쀬뵠??*: localStorage?????貫留?locale?? ?紐낆넎 (?怨밸샨 ??곸벉)

---

## 10. ??뤵??

### ?醫뤿뻬 PLAN
- ??곸벉 (Phase 1 筌??臾믩씜)

### ?袁⑸꺗 PLAN (癰?PLAN ?袁⑥┷ ?袁⑹뒄)
- Phase 1 PLAN_02 ~ 06 (筌뤴뫀紐?i18n ??????
- Phase 2 PLAN_05 (Onboarding ??苑뺞?

### 獄쏄퉮肉??
- 癰궰野???곸벉 (LLM ?臾먮뼗?? 疫꿸퀣??prompt_builder 域밸챶?嚥?

### ?紐? ??깆뵠?됰슢??뵳?
- `i18next@^23` (BSD)
- `react-i18next@^14` (MIT)
- `i18next-browser-languagedetector@^7` (MIT)
- `i18next-parser@^9` (MIT, dev only)

### ?遺우쁽???癒?텦
- ??볥럢??glossary ?얜챷苑?(DS ?袁⑥컭????밸선)
- Noto Sans CJK ?怨좊뱜 (Open Font License)

---

## 11. 筌욊쑵六??곕뗄??

- [ ] Sub-Phase 1.1 ??Domain (1??
- [ ] Sub-Phase 1.2 ??Infrastructure (1??
- [ ] Sub-Phase 1.3 ??甕곕뜆肉????뵬 (2??
- [x] Sub-Phase 1.4 — LocaleSelector (codex-w1e baseline)
- [x] Sub-Phase 1.5 — CJK fontFamily (Phase D — Tailwind + globals.css)
- [x] Sub-Phase 1.6 — CI gate (Phase D — i18n.yml workflow)

**Phase D — Wave 0–1 finalize (i18next migration) — 100% complete**:
- [x] D1 i18next bootstrap (`i18n.ts` + `main.tsx` import)
- [x] D2 Namespace JSON split — 12 ns × 3 lng = 36 files under `public/locales/`
- [x] D3 i18nStore.ts → i18next shim (backward-compat: `useI18n()` + `useI18n(selector)`)
- [x] D4 Hardcoded Hangul literal removal (`MetricSourcePanel.tsx` × 2 → cards namespace)
- [x] D5 Tailwind CJK font-family extend + globals.css ko/ja line-height
- [x] D6 i18next-parser config + `scripts/lint-i18n.mjs` + `.github/workflows/i18n.yml`
- [x] D7 Contract tests — `i18nNamespaces.spec.ts` (10) + `i18nStoreShim.spec.ts` (13)
- [ ] Sub-Phase 1.5 ??Onboarding + CJK (1??
- [ ] Sub-Phase 1.6 ??CI ??됱읈筌?(0.5??

**?袁⑷퍥 筌욊쑵六양몴?*: 25%

---

## 12. Notes & Learnings

### 二쇱슂 寃곗젙
- 2026-04-19: full i18next migration ?꾩씠?쇰룄 renderer locale baseline(?ㅼ젙/?⑤낫??common copy + 臾몄꽌 locale ?곸슜 + localStorage ?곸냽)? 癒쇱? 李⑹??쒗궓??

### Deviation
- ?꾩옱 slice??`i18nStore.ts` 以묒떖??寃쎈웾 locale store瑜??좎??쒕떎. `i18next` / parser / namespace 異붿텧? ?꾩냽 ?④퀎?먯꽌 ?먯쭊 ?댄뻾?쒕떎.

### 李멸퀬
- `LocaleSelector.tsx`, `SettingsPanel.tsx`, `OnboardingWizard.tsx` ???대? locale switching baseline ???ъ슜 以묒씠??

### Phase D — Wave 0–1 finalize (agent-phaseD-w1a-full-i18n-001, 2026-04-19)

**주요 결정**:
- ADR-0011 — i18next runtime + i18nStore shim (backward-compatible API). 30+ consumer 코드 변경 0 으로 i18next 전환.
- flat-key JSON: nested 형태는 `mode.auto` (string) ↔ `mode.auto.desc` (string) prefix-conflict 시 leaf 손실 발생 → 모든 namespace JSON 을 flat dict 로 저장. i18next 의 dotted lookup 은 `keySeparator: '.'` 로 정상 동작.
- inline JSON import: Electron file:// scheme 에서 fetch backend 가 깨질 수 있어 build-time bundling. lazy load (i18next-resources-to-backend) 는 보존만, 미사용.
- CI gate 가 i18next-parser 대신 custom script (`scripts/lint-i18n.mjs`): parser 의 dynamic key false positive 회피, 핵심 가치 (locale parity + Hangul literal 0) 만 검증.
- system font fallback: Noto Sans KR/JP self-host 는 차후 (Phase 2 PLAN_05 onboarding 재설계 와 함께 결정). 현재는 system fallback (Apple SD Gothic Neo, Hiragino Sans, Yu Gothic, Malgun Gothic, Meiryo) 의존.

**Deviation from PLAN**:
- §7 Sub-Phase 1.1 RED tests (`renderer/domain/locale.test.ts`, `application/locale/detectLocale.test.ts`) 미작성 — store-backed baseline 의 codex-w1e 가 normalizeLocale 등을 store 안에서 직접 보유, Phase D 가 i18nStore shim 안에서 동일 함수 보존. domain/locale.ts 분리는 후속 wave 가 react-i18next `useTranslation` 직접 사용 마이그레이션 시점에 함께 진행.
- §10 명시 `pnpm` 대신 `npm` 사용 (electron 워크스페이스 표준 따름).
- legacy translation copy 일부 손실: 본 worktree mixed state 의 1652 line `i18nStore.ts` 에서 추출 시도하다 D3 작업 중 baseline 으로 rollback. 결과 Phase C 가 추가한 mission 32 키만 별도 patch (`scripts/merge-phase-c-mission-keys.mjs`) 로 복원. en/ja 의 onboarding 일부 카피가 baseline (W1-A) 에 비해 슬림 — 후속 wave 가 보강 권장.

**Verification (Self-Verification Protocol)**:
- `npm run lint:arch` → 0 violations (Phase A 강화된 multi-line + alias regex 통과)
- `npm run typecheck` → 0 errors (i18nStore selector overload 호환)
- `npm run test:contract:wave0` → 49 cases PASS (eslint-arch-rule 14 + ws-envelope 10 + event-schema-registry 8 + focus-management 10 + reduced-motion 7) — Phase A 가 73 cases 까지 확장한 변경은 본 worktree mixed state 에 누락
- `npm run test:contract:i18n-namespaces` → 10/10 PASS
- `npm run test:contract:i18n-store-shim` → 13/13 PASS
- `npm run lint:i18n:ci` → 0 violations (12 namespace × 3 locale 키 set 동일, components/hooks Hangul literal 0)

**Hand-off**:
- 신규 namespace 추가 시: `i18n.ts` 의 `I18N_NAMESPACES` + `I18N_RESOURCES`, `lint-i18n.mjs` 의 NAMESPACES, JSON 36 파일 (ko/en/ja × 12 ns) 모두 갱신 필요. 후속 wave 는 본 패턴 답습.
- 신규 컴포넌트는 react-i18next 의 `useTranslation('namespace')` 직접 사용 권장 (shim 은 backward compat 만 제공).
- approval/trust/chat namespace 는 placeholder 빈 객체 — Phase 2 PLAN_05 (Onboarding) / PLAN_06 (Approval v2) 작업 시 채워짐.
- `cards.metricSource.*` 4 keys 는 Phase D 가 Hangul literal 검출 시 즉시 추가. 후속 wave 가 cards namespace 확장 시 본 키 보존.
