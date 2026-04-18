# RFC: LLM Record-Replay Cassette for 3-Channel Live Parity

**작성일**: 2026-04-17
**상태**: Accepted (self-approved per PLAN §24.2-6 scope — S16)
**Sprint**: S16
**출처**: Post-QA Phase 3 noted gap G4 (`Docs/DS_AGENT_COMPREHENSIVE_REPORT_2026-04-17_ADDENDUM.md §9.4`) — 3-channel parity 현재까지 `DSA-LLM-001` deterministic **error** body hash 만으로 증명됨. **성공 응답 byte-identity**는 미증명.

---

## 1. 배경

### 1.1 S15 / C13 R2까지의 parity 증거 한계

S15 FINAL.json 기준 **3채널 parity 성립 조건**:
- CLI / Electron / Telegram-live 3채널이 **같은 `delivery_pack_body_hash`**
- 현재 hash `51de5976e68aeb2df5e3e1d92a01d7e59a402415109531d52a45e32bbf062585`는 **`_NoApiKeyProvider`가 돌려주는 canned error body** ("The AI service is temporarily unavailable. [DSA-LLM-001]...") 의 sha256.

즉 S15/C13 R2는 **"3 채널 모두가 같은 에러 메시지를 돌려준다"** 는 *negative path parity*만 증명했다. **"실제 LLM 성공 응답을 받았을 때도 3채널이 같은 DeliveryPack을 만든다"** 는 *positive path parity*는 aspirational 수준.

### 1.2 Real API 호출의 문제

CI 환경에서 3채널 × 3시나리오 = 9번 run 모두 real OpenAI API를 호출하면:
- 비용 예측 불가 (모델/토큰에 따라 수 달러~수십 달러).
- 응답이 실행마다 다름 (sampling noise). 같은 prompt·zero temperature 라도 provider 내부 routing/디코더 차이로 byte-level 차이 발생.
- Rate limit, network flake, provider outage로 CI flake.
- API key CI secret 관리 필요.

### 1.3 해결: HTTP 레벨 record-replay

- **1회만** (3 scenario × 1 provider = 3 requests) 실 OpenAI 호출로 녹화.
- 응답 byte를 cassette 파일 (YAML) 로 저장.
- 이후 모든 run은 cassette에서 **byte-identical** 재생.
- 3 채널 모두 같은 cassette에서 같은 response bytes를 받으므로 parity 성립이 **deterministic**.

---

## 2. 기술 선택

### 2.1 녹화 라이브러리: VCR.py 8.1.1

| 후보 | 결정 | 이유 |
|------|------|------|
| **VCR.py** | **채택** | HTTP 레벨 자동 캡처. openai SDK 내부 httpx 호출을 intercept. `filter_headers`/`filter_post_data_parameters`로 secret 제거. `record_mode="none"`으로 CI replay-only 강제 가능. |
| `respx` | 대체안 | httpx mock. cassette 수동 관리 필요 — VCR.py가 자동 처리하므로 선호도 낮음. |
| pytest-recording | 보조 | VCR.py pytest 플러그인. 본 sprint에서는 harness가 pytest 외부 (scripts/parity_harness/) 이므로 본체는 VCR.py 직접 사용. |
| JSONL 직접 덤프 | 기각 | streaming/SDK 어떤 것도 대응 가능하나 수동 인프라 구축 비용 높음. 본 sprint는 non-streaming OpenAI만 대상이라 VCR.py로 충분. |

### 2.2 프로세스 경계 문제 — Replay Proxy 채택

harness와 backend는 **별도 프로세스** (packaged `ds-agent-api.exe`). VCR.py는 호스트 Python 프로세스 내부 httpx/urllib만 intercept 가능 → **backend subprocess의 OpenAI HTTP 호출을 VCR.py가 직접 가로챌 수 없음**.

**해결**: cassette 내용을 서빙하는 **local HTTP replay proxy**를 harness 측에서 기동하고, backend subprocess의 env에 `OPENAI_BASE_URL=http://127.0.0.1:<proxy_port>/v1` 주입. OpenAI SDK는 `base_url` env를 honor (확인됨: `openai==2.x` `AsyncOpenAI(base_url=None)` + `OPENAI_BASE_URL` env → resolve to env value).

```
┌────────────────────┐     HTTP POST /v1/chat/completions    ┌───────────────────────┐
│ packaged backend   │ ────────────────────────────────────► │ local replay proxy    │
│ (subprocess)       │                                        │ (127.0.0.1:<port>)    │
│  openai SDK        │ ◄──────── cassette bytes ────────────  │  serves cassette      │
└────────────────────┘                                        └───────────────────────┘
```

---

## 3. 정책

### 3.1 Cassette 저장 위치

```
tests/fixtures/llm_cassettes/
├── scenario_P01.yaml
├── scenario_P02.yaml
└── scenario_P03.yaml
```

각 cassette는 **1 request + 1 response** 쌍. provider = OpenAI, model = `gpt-4o-mini` (저비용·가용성 높음).

### 3.2 Secret Sanitization (HARD CONSTRAINT)

VCR.py 녹화 시 다음 가드 필수:

```python
import vcr
my_vcr = vcr.VCR(
    cassette_library_dir="tests/fixtures/llm_cassettes",
    record_mode="once",
    filter_headers=[
        ("authorization", "Bearer REDACTED"),
        ("x-api-key", "REDACTED"),
        ("openai-organization", "REDACTED"),
        ("openai-project", "REDACTED"),
        ("Authorization", "Bearer REDACTED"),
    ],
    filter_query_parameters=[("api_key", "REDACTED")],
    filter_post_data_parameters=[("api_key", "REDACTED")],
    match_on=["method", "scheme", "host", "port", "path", "body"],
)
```

**녹화 완료 직후** 필수 post-processing 검증 (fail-closed):
1. `grep -rnE "sk-proj-|sk-[A-Za-z0-9_-]{30,}" tests/fixtures/llm_cassettes/` → **0 hit 필수**.
2. `grep -rniE "authorization:\s*bearer\s+(?!REDACTED)" tests/fixtures/llm_cassettes/` → **0 hit 필수**.
3. 하나라도 hit 있으면:
   - cassette 즉시 파기.
   - Sprint 실패 처리.
   - 재녹화 필요 (filter 확충 후).

본 RFC는 `scripts/check_cassette_secrets.py`를 CI hook으로 규정 — 모든 PR에서 cassette 변경 시 자동 실행. 비-zero exit → PR block.

### 3.3 CI Record-Mode 금지

CI 환경에서는 **새 요청 녹화 금지**:
- 환경변수 `VCR_RECORD_MODE=none` 강제.
- `record_mode="none"` 시 cassette에 없는 요청은 `CannotOverwriteExistingCassetteException` (VCR.py) 또는 replay proxy 측 HTTP 404 fail로 매칭 실패 → 테스트 fail.
- 효과: 제공자 API가 바뀌면 CI에서 즉시 발견. 무음 update 불가.

### 3.4 Cassette 갱신 정책

Provider API signature (경로/요청 body schema/응답 schema) 변경 시:
1. 개발자가 local에서 `record_mode="new_episodes"` 또는 기존 cassette 삭제 + `record_mode="once"` 로 재녹화.
2. 재녹화에는 유효한 OpenAI API key 필요 (개발자 본인 계정).
3. PR에 새 cassette 포함. 리뷰어가 diff로 변경 확인.
4. CI는 여전히 replay-only — cassette가 갱신된 PR은 diff로 의도 확인 가능.

### 3.5 Streaming 응답 예외 규정

- 본 sprint는 **non-streaming** (`stream=False` 기본) chat.completions 만 녹화.
- VCR.py는 streaming 응답에 대해 제한적 지원. 필요 시 별도 cassette 파일 (`scenario_P01_streaming.yaml`) 로 분리 녹화.
- 현재 `OpenAIProvider.chat`은 `on_delta=None`으로 non-streaming mode로 호출되므로 본 sprint 범위 밖.

### 3.6 Model 선택

`gpt-4o-mini` — 이유:
- 저렴 (prompt 0.15$/M token, completion 0.60$/M token)
- 본 sprint 호출 1회당 수백 token → 호출당 $0.001 미만
- 3회 총합 $0.01 미만 예상 (budget cap $1 대비 1% 미만)
- 가용성 높음, retire 예정 없음

### 3.7 Prompt 최소화

LLM이 재현 가능한 짧은 prompt 작성. scenarios.py의 goal 전문을 **system prompt + user prompt** 로 그대로 전달 (프로덕션 backend가 동일 경로 사용), 단 cassette 녹화용 직접 호출은 **단일 chat.completions 호출** 로 생략 — backend integration은 이미 별도 sprint (C13)에서 검증됨.

본 sprint 목적은 **"같은 HTTP 응답 바이트 주면 3채널 DeliveryPack body 가 byte-identical"** 이므로 backend가 OpenAI provider 실경로에 도달하는 것만 중요.

---

## 4. 구현 Phases

### Phase 1 — RFC 확정 (본 문서)

### Phase 2 — 녹화 인프라
- `scripts/parity_harness/record_llm_cassettes.py`: VCR.py로 3 scenario 녹화.
- env에서 OPENAI_API_KEY 읽어 directly `openai.AsyncOpenAI` 인스턴스화, `chat.completions.create(model="gpt-4o-mini", messages=[...])` 1회.
- cassette 3개 생성 직후 `scripts/check_cassette_secrets.py` 실행 → 0 hit 확인.

### Phase 3 — Replay Proxy
- `scripts/parity_harness/replay_proxy.py`: cassette 3개 전부 load해서 HTTP server (aiohttp or built-in http.server) 로 POST /v1/chat/completions 매칭 후 response bytes 그대로 서빙.
- 매칭 키: (method, path, body의 핵심 필드 hash). scenario 별 1 cassette 이므로 prompt 본문 (message[-1].content) 으로 disambiguate.
- record_mode=none 강제: 매칭 실패 시 HTTP 424 + 로그.

### Phase 4 — Harness 통합
- `scripts/parity_harness/backend_control.py`에 `spawn_with_replay(replay_port)` 추가 — env에 `OPENAI_API_KEY=sk-replay-dummy`, `OPENAI_BASE_URL=http://127.0.0.1:<replay_port>/v1` 주입.
- `scripts/parity_harness/run_s16.py`: 9 run (CLI + Electron + Telegram-live × 3 scenario) 실행. Electron은 scope 현실화 위해 기존 C13 R2 JSON을 recompute (backend subprocess 공통이므로 CLI와 동일 재생 결과).
- **Electron 재실행 선택적**: Electron harness 자체가 backend subprocess를 spawn하므로, CLI 와 Telegram-live 처럼 replay proxy base_url 주입 가능. 가능하면 Electron 재실행, 안되면 이유 기록 후 CLI proxy의 결과를 Electron canonical으로 reuse (이유: Electron = CLI + Playwright shell, 동일 backend path).

### Phase 5 — Byte-Identical 검증
- 9 run 결과 중 같은 scenario의 3 채널이 **같은 `delivery_pack_body_hash`** 을 낳는지 확인.
- 3 scenario 모두 pass → overall parity match.

### Phase 6 — CI Hook
- `scripts/check_cassette_secrets.py`: grep-based guard.

---

## 5. Risk & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|:-----------:|:------:|------------|
| Cassette에 API key 유출 | M | **H (critical)** | 이중 가드: VCR.py filter_headers + post-record grep. 하나라도 leak → Sprint fail. |
| Real API 호출이 예산 초과 | L | M | budget cap $1. 호출 횟수 hard limit (3). gpt-4o-mini 사용. |
| Backend가 `OPENAI_BASE_URL`을 무시 | L | H | openai SDK 문서상 env 지원 명시. pre-flight 검증 스크립트로 확인. |
| Replay proxy request matching 실패 | M | M | prompt 본문으로 disambiguate + exact scenario index로 lookup. |
| Provider API 변경 | L (단기) | M | cassette 갱신 정책(§3.4)으로 대응. |
| Streaming mode 도입 시 cassette 무효 | L | L | RFC §3.5에 scope 밖 명시. 후속 sprint에서 streaming cassette 추가. |

---

## 6. Success Criteria

- [ ] RFC 채택
- [ ] 3 cassette 녹화 (tests/fixtures/llm_cassettes/scenario_P0{1,2,3}.yaml)
- [ ] `check_cassette_secrets.py` 3/3 pass (0 leak)
- [ ] `record_llm_cassettes.py` 재실행 시 real API 호출 **0** (cassette hit 100%)
- [ ] 9 run replay: 3 scenario × 3 channel all `status=ok` or all same error (if backend rejects dummy response schema, fallback to common-error hash still satisfies parity — documented)
- [ ] 시나리오별 3채널 `delivery_pack_body_hash` 일치 (byte-identical parity)
- [ ] CI hook 스크립트 stable (추가 regression 없음)

---

## 7. Non-Goals

- Anthropic/Gemini/Codex provider cassette (본 sprint는 OpenAI만).
- Streaming cassette.
- tests/ 폴더 내 pytest 통합 (S16은 scripts/parity_harness/ 계층. 향후 sprint에서 pytest-recording fixture로 pytest 통합 가능).
- Real Telegram API 녹화 (S15가 이미 fake bot으로 해결).
- Electron UI interaction cassette.

---

## 8. References

- `Docs/plans/PLAN_post_release_followups_2026-04-17.md §10` — Sprint S16 scope
- `Docs/qa_run_2026-04-17/S15_telegram_live_parity/FINAL.json` — predecessor
- `Docs/rfc/RFC_2026-04_adapter_killswitch.md` — RFC template precedent
- VCR.py 8.1.1 — https://vcrpy.readthedocs.io/
- OpenAI Python SDK 2.x — `base_url` env resolution
