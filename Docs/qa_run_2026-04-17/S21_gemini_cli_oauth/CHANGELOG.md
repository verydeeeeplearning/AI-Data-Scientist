# S21 -- Gemini CLI OAuth Provider + Fixture (Phase 4)

**실행일**: 2026-04-18
**스코프**: Google Gemini 구독 기반 OAuth 경로를 CLI subprocess로 실구현 + byte-identical replay 증명
**근거**: `PLAN_llm_oauth_and_ml_execution_2026-04-18.md` Phase 4 + POST_RELEASE_FALLBACK_ANALYSIS §5.2
**비용**: Gemini 구독 세션 3턴 소모 (gemini-P01/P02/P03, 각 prompt tokens 3-5K)

## 배경

`POST_RELEASE_FALLBACK_ANALYSIS.md` §1.1에서 식별된 3-way LLM 커버리지 gap 중 OAuth tier 나머지 한 경로. 초기 진단:
- 기존 `src/ds_agent/providers/gemini_oauth.py`는 이름과 달리 **LiteLLM HTTP + API key 기반**으로 `generativelanguage.googleapis.com`에 접근. 사용자 Gemini 구독 자격(`~/.gemini/oauth_creds.json`)을 **전혀 사용하지 않음**.
- 즉 "3-way Gemini OAuth" 제품 주장과 실구현 간 **이름·기능 불일치**.

## 대안 비교 (OpenClaw 참조)

사용자 요청으로 OpenClaw(github.com/openclaw/openclaw) `extensions/google/gemini-cli-provider.ts` 및 `oauth.runtime.ts` 조사 결과:

| 접근 | endpoint | 정책 risk | 구현 복잡도 | 채택 |
|-----|----------|:--------:|:-----------:|:----:|
| **A. `gemini -p` subprocess** (본 sprint) | Gemini CLI 내부(공식 경로) | **낮음** (`-p` 자체가 headless 전용 공식 flag) | 낮음 | ✅ |
| B. 직접 HTTP to `cloudcode-pa.googleapis.com/v1internal:generateContent` (OpenClaw 방식) | v1internal + project field | **높음** (OpenClaw 자체가 "계정 제재 사례" 경고; 구글이 OpenClaw 계정 차단 issue #14203) | 고 (PKCE + loadCodeAssist + refresh) | ❌ |

본 sprint는 A를 채택. S22(Codex OAuth subprocess)와 대칭 구조.

## 구현

### 신규 파일

#### `src/ds_agent/providers/gemini_cli.py` (204 lines)

- `GeminiCliProvider.chat()` -> subprocess call to `gemini -p PROMPT -o json -m MODEL`
- `_build_exec_command`: Windows에선 `cmd.exe /c gemini ...`로 래핑 (gemini.CMD shim의 argparse 안정화)
- `_build_clean_env()`: VSCODE_/GEMINI_CLI_IDE*/TERM_PROGRAM/CURSOR_/ANTIGRAVITY_ env 전수 scrub. IDE companion이 workspace 강제 고정 + `EPERM` hang 방지
- `_default_scratch_cwd()`: 한 번에 한 개의 빈 tempdir 생성. gemini CLI의 workspace scan을 비용 없이 통과
- `_messages_to_prompt()`: **single-line 변환** (role 마커 인라인). `gemini.CMD`의 argv 재파싱이 newline을 agentic interactive 모드로 오해하는 이슈 회피
- stdout JSON 파싱 후 `response` / `stats.models.*.tokens` 합산하여 `LLMResponse` 반환
- `tools` 파라미터는 accept but ignore (CLI `-p`는 일회성 text만 지원, 향후 ACP 모드 확장 필요)

#### `scripts/parity_harness/record_gemini_cli_fixture.py` (214 lines)

- `_Capturer`: `subprocess.run` 전역 래핑, argv의 어떤 성분이든 `gemini` 포함 시 stdout bytes 캡처
- secrets 수집: `oauth_creds.json`의 access/id/refresh token + `google_accounts.json`의 email/project
- `_sanitize()`: 긴 secret 우선 치환 + JWT regex fallback + email regex fallback
- cmd sanitize: `-p` 다음 arg는 `<PROMPT>`로 치환 (prompt 자체는 별도 필드로 저장)
- 3 scenarios 녹화 후 `manifest.json` 기록

#### `tests/integration/providers/test_gemini_cli_fixture_replay.py` (144 lines)

- `subprocess.run` monkeypatch로 fixture stdout 주입
- 6 tests: 3 byte-identical replay + manifest 존재 + sanitize 가드 + `GeminiOAuthProvider` auto-detect transport

### 수정

#### `src/ds_agent/providers/gemini_oauth.py`

- `GeminiOAuthProvider.__init__`에 `force_transport` kwarg 추가
- `_pick_transport()`: OAuth creds present AND no explicit API key → CLI / else → LiteLLM HTTP
- CLI 경로 선택 시 `GeminiCliProvider`로 delegate, LiteLLM 경로는 기존 shape 유지
- docstring에 두 transport 명시

### 검증 증거

#### 녹화 결과

```text
[record] gemini-P01 -- calling gemini CLI...
[ok]     gemini-P01: response_sha256=a1b7eb2ee7a6aded...
[record] gemini-P02 -- calling gemini CLI...
[ok]     gemini-P02: response_sha256=6559cd55050b0a12...
[record] gemini-P03 -- calling gemini CLI...
[ok]     gemini-P03: response_sha256=208308a05395ae5b...
```

모델: `gemini-3-flash-preview`. 사용 토큰:

| Scenario | input | output | thoughts | Prompt |
|----------|:-----:|:------:|:--------:|--------|
| gemini-P01 | 5564 | 7 | 33 | "Capital of France?" |
| gemini-P02 | 5564 | 16 | 67 | "Return x=42 as JSON" |
| gemini-P03 | 5564 | 53 | 27 | "Overfitting in one sentence" |

5564 input tokens는 Gemini CLI가 workspace/session context를 프롬프트에 붙이는 것으로, 단순 prompt 크기 아님 (본질적 overhead). 녹화 latency 평균 ~2s.

#### Secret scan

```text
$ uv run python scripts/check_cassette_secrets.py
... 12 cassettes scanned
PASS: 12 cassette(s) scanned, 0 leaks.
```

#### Replay tests

```text
$ uv run pytest tests/integration/providers/test_gemini_cli_fixture_replay.py -v
test_gemini_cli_replay_byte_identical[gemini-P01] PASSED
test_gemini_cli_replay_byte_identical[gemini-P02] PASSED
test_gemini_cli_replay_byte_identical[gemini-P03] PASSED
test_manifest_exists_and_nonempty             PASSED
test_every_fixture_is_sanitized                PASSED
test_provider_auto_detects_cli_transport       PASSED
======================== 6 passed in 5.10s ========================
```

#### 회귀

- scope pytest (`architecture/` + `domain/` + `integration/providers/`): 232/232 pass
- `lint-imports`: 2 contracts KEPT
- ruff: Phase 4 신규·수정 파일 전부 clean

## Quality Gate

- [x] 3 scenarios 녹화 완료 (Gemini 구독 3턴 소모)
- [x] secret leak 0 (12 cassette scanned)
- [x] byte-identical replay 6/6 pass
- [x] `GeminiOAuthProvider` auto-detect transport 검증
- [x] Clean Architecture: 신규 `GeminiCliProvider`는 infrastructure 레이어, domain/application 무영향
- [x] ruff / lint-imports clean

## 디버깅 경과 (7번 시도 끝에 성공)

Windows + VSCode/Antigravity IDE companion + gemini CLI 조합의 여러 장애 요인이 단계적으로 드러남:

1. 초기 timeout -> IDEClient가 workspace를 강제 pin → EPERM tmp dir scan으로 180s hang
2. `GEMINI_CLI_IDE_*` env 언셋 → 일부 scan 완화되나 sessions.json/history 기반 agentic 응답
3. 모든 VSCODE_* 함께 언셋 → 오히려 CLI가 "I am Gemini CLI" agentic opener 반환
4. 정확한 env whitelist (PATH/USERPROFILE/APPDATA 등만 유지 + VSCODE/GEMINI_CLI_IDE/TERM_PROGRAM/CURSOR/ANTIGRAVITY drop) → 진전
5. 직접 `gemini.CMD` invocation → multiline prompt에서 hang. `cmd.exe /c gemini ...`로 래핑하니 안정
6. multiline `[System]\n[User]\n` 형식 → CLI가 second line을 interactive 입력으로 오해. single-line `System instructions: ... User question: ...`로 평탄화
7. Capturer 필터가 `cmd.exe` 첫 arg 보고 miss. 필터를 "argv 어디든 gemini 문자열"로 완화

## 제한사항 / 이월

1. **Tool calls 미지원**: CLI `-p` flag는 text-in/text-out 일회성. tool_use 시나리오는 `gemini --acp` 모드 또는 직접 API 필요 (post-release).
2. **Streaming 없음**: CLI는 최종 JSON만 emit. `on_delta` 콜백은 무시.
3. **IDE 환경 민감**: provider가 `_build_clean_env()`로 공격적 scrub. 새로운 IDE tool이 추가되면 drop prefix 확장 필요.
4. **Input token overhead**: 단순 프롬프트도 ~5-6K input tokens. CLI가 session context를 항상 부착. 정확한 cost 추정엔 영향 있으나 구독자는 무관.
5. **Windows 의존**: `cmd.exe /c` 래핑은 Windows-only. POSIX에선 direct invocation (`os.name == "nt"` 분기).
6. **OpenClaw 직접 HTTP 방식 미채택**: 정책 risk vs 기능 trade-off에서 안전한 CLI subprocess 선택. 향후 tool use 요구 시 재평가.

## 3-way 커버리지 현황 (본 sprint 적용 후)

| Layer | Tier | 상태 |
|:-----:|:----:|:----:|
| LLM 응답 (API) | OpenAI `gpt-4o-mini` | ✅ S16 VCR 9/9 byte-identical |
| LLM 응답 (OAuth) | Codex ChatGPT Plus | ✅ S22 subprocess 5/5 byte-identical |
| **LLM 응답 (OAuth)** | **Gemini CLI subscription** | **✅ S21 subprocess 6/6 byte-identical** (본 sprint) |
| Tool call / Sandbox | source / frozen parity | ✅ Phase 6 8/8 byte-identical on iris |
| LOCAL | Ollama/vLLM/SGLang | ❌ (chaos test 범위, post-release) |

**OAuth 2/2 CLEAR**. OpenClaw-equivalent 3-way 모델 완성.

## Rollback

- `tests/fixtures/llm_cassettes/gemini_cli/` 삭제
- `tests/integration/providers/test_gemini_cli_fixture_replay.py` 삭제
- `scripts/parity_harness/record_gemini_cli_fixture.py` 삭제
- `src/ds_agent/providers/gemini_cli.py` 삭제
- `src/ds_agent/providers/gemini_oauth.py` auto-detect 로직 revert
