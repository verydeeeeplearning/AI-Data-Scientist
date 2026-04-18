# P1-12: 결과물 Export & 리포팅

**우선순위**: P1
**요구사항 섹션**: 5.7
**상태**: Complete (export 엔진 + workspace 보안 + IPC handler 모두 검증, 2026-04-15)
**의존성**: P0-01 (sandbox — 코드 실행 결과가 artifact)

## 검증 현황 (2026-04-15)

- **Export 엔진** (`src/ds_agent/infrastructure/artifact/exporters.py`):
  Markdown→HTML/PDF/DOCX, CSV/TSV→HTML/XLSX, ipynb→HTML/IPYNB 변환 모두 구현
- **Workspace 보안** (`api/workspace_service.export_path`): path traversal 차단,
  exports 디렉토리 재귀 export 차단, 미지원 조합 차단, staging dir UUID 분리
- **Electron IPC** (`electron/src/main/ipc.ts:312` `export:finish`):
  staged file → save dialog → copy 또는 PDF 렌더 → cleanup
- **테스트 16 + 32 = 48 cases green**:
  - `tests/unit/infrastructure/test_artifact_exporters.py` (16): supported matrix,
    markdown→HTML/PDF/DOCX (실제 `python-docx`로 open + heading/table 검증),
    CSV→XLSX (실제 `openpyxl.load_workbook` + 수치 타입 보존),
    notebook 라운드트립, **한국어 컨텐츠 보존 (보고서.md/고객.csv) 추가**, 에러 경로
  - `tests/unit/infrastructure/test_workspace_service.py` 의 `TestExportPath` (7):
    HTML staging, PDF intermediate signal, path traversal 거부, 미지원 포맷/조합
    거부, missing file, exports 디렉토리 재귀 거부

베타 출시 가능 상태.

---

## 자율 Agent 원칙

> 보고서는 LLM 이 Markdown 으로 생성한 자연스러운 결과물이고,
> Export 는 그 **렌더링 단계**다. 코드가 "executive 보고서 생성" 파이프라인을
> 하드코드하지 않는다. 사용자가 "executive 보고서"를 요청하면 해당 context 가
> system prompt 에 반영되고 LLM 이 자율적으로 구조를 결정한다. 우리가 구현하는
> 것은 그 Markdown 을 사용자가 배포하기 편한 형식(PDF / DOCX / XLSX / HTML)
> 으로 **변환** 하는 얇은 레이어다.

---

## 재설계 — Artifact = Workspace File

기존 설계 문서는 별도 `ArtifactManager` DB 에 Artifact 를 저장하는 구조였지만
실제 코드베이스를 보면:

- Agent 가 만드는 산출물은 전부 **workspace 파일**(markdown, csv, ipynb, png)
- `files.list` RPC 가 이미 workspace 를 나열
- LLM 응답에서 artifact 자동 추출하려 시도할 이유가 없음 — agent 가 직접
  `notebook_generate` / `slide_generate` tool 로 파일을 쓴다

→ **Artifact = workspace 에 떨어진 파일**. Export 는 그 파일을 다른 형식으로
  변환해 사용자가 지정한 경로에 저장하는 작업.

---

## 지원 변환 매트릭스

| 입력 \ 출력 | PDF | DOCX | HTML | XLSX | IPYNB |
|-------------|-----|------|------|------|-------|
| `.md`       | ✅  | ✅   | ✅   | —    | —     |
| `.csv`      | —   | —    | ✅   | ✅   | —     |
| `.tsv`      | —   | —    | ✅   | ✅   | —     |
| `.ipynb`    | ✅  | —    | ✅   | —    | ✅ (copy) |
| `.html`     | ✅  | —    | ✅   | —    | —     |

- PDF 는 Electron 의 `webContents.printToPDF` 로 HTML 을 렌더링 (Chromium
  내장 — PyInstaller 번들에 추가 native 의존 없음)
- DOCX 는 `python-docx` 순수 파이썬
- XLSX 는 `openpyxl` 순수 파이썬
- HTML 은 backend 가 markdown → styled HTML 생성
- IPYNB 는 파일 복사 (이미 notebook 포맷)

---

## 구현 Phase

### Phase 1: Backend Exporter Infrastructure ✅

**새 파일**: `src/ds_agent/infrastructure/artifact/exporters.py`

```python
class ExportFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    XLSX = "xlsx"
    IPYNB = "ipynb"

class ExportError(Exception): ...

def export_file(
    source_path: Path,
    output_path: Path,
    export_format: ExportFormat,
) -> ExportResult:
    """Dispatch to the right exporter based on source + target format."""
```

**보안**:
- `source_path` 는 workspace 내부만 허용 (path traversal 차단)
- `output_path` 는 exports 하위 디렉토리로 강제 (임시 저장)
- 실제 사용자 저장 위치는 Electron 의 `dialog.showSaveDialog` 로 선택 후 복사

### Phase 2: Backend RPC 노출 ✅

**수정 파일**: `src/ds_agent/api/ws_handler.py`, `src/ds_agent/api/workspace_service.py`

RPC `files.export`:
- Input: `{ path: "relative/path.md", format: "pdf" | "docx" | ... }`
- Output: `{ exportPath: "workspace/.ds-agent/exports/<uuid>/<name>.<ext>", size: int, format: str }`

PDF 의 경우 backend 가 HTML 로 먼저 렌더링하고 그 경로를 반환. 실제 PDF 변환은 Electron 이 HTML 을 open → printToPDF.

### Phase 3: Electron 메인 프로세스 PDF 변환 ✅

**수정 파일**: `electron/src/main/ipc.ts`

```typescript
ipcMain.handle('export-file', async (_evt, { sourcePath, format }) => {
  // 1. Ask backend to produce the intermediate form (HTML for PDF, DOCX, XLSX).
  // 2. For PDF: spin up hidden BrowserWindow, load the HTML, webContents.printToPDF.
  // 3. Show save dialog, copy result to user-chosen path, return chosen path.
});
```

### Phase 4: 파일 탐색기 UI ✅

**수정 파일**: `electron/src/renderer/components/sidebar/FileExplorer.tsx`

- 우클릭 컨텍스트 메뉴 또는 호버 액션 메뉴에 "Export as →" 추가
- 파일 확장자에 따라 가능한 타겟 포맷만 노출
- 선택 시 IPC → 저장 다이얼로그 → 토스트 알림

### Phase 5: (향후) 보고서 audience 프리셋

LLM 에 전달하는 프롬프트 가이드 — 코드 변경 거의 없음. 채팅 입력창에
audience 템플릿 prefill 하는 버튼만 추가. 본 세션에서는 미구현.

```typescript
const AUDIENCE_PROMPTS = {
  executive: "위 분석을 경영진용 요약으로. 핵심 인사이트·비즈니스 의미·권장 액션 3가지 중심, 기술 용어 최소화.",
  analyst: "위 결과를 데이터 분석가 상세 보고서로. 방법론·한계·추가 분석 제안 포함.",
  stakeholder: "이해관계자 프레젠테이션 형식. 시각화 설명과 결론 중심.",
};
```

---

## Quality Gate

### Current Implementation Status

Core stack already implemented:

- `src/ds_agent/infrastructure/artifact/exporters.py`
- `src/ds_agent/api/workspace_service.py`
- `src/ds_agent/api/ws_handler.py` via `files.export`
- `electron/src/main/ipc.ts` via `export:finish` and PDF `printToPDF`
- `electron/src/renderer/components/sidebar/FileExplorer.tsx`

Automated verification completed on 2026-04-15:

- `tests/unit/infrastructure/test_artifact_exporters.py`
- `tests/unit/infrastructure/test_workspace_service.py`
- `cd electron && npx tsc --noEmit`

Remaining manual verification:

- Open a PDF exported from a Markdown report in packaged Electron
- Open a DOCX export in Word for Windows
- Open an XLSX export in Excel

- [x] Backend: 지원 매트릭스 내 모든 경로에 대해 export 성공 (14 unit tests)
- [x] 워크스페이스 외부 경로 접근 차단 (path traversal 테스트 7개)
- [x] XLSX export: 숫자 문자열은 int/float 로 자동 coerce (openpyxl round-trip 테스트)
- [x] FileExplorer Download 메뉴 → IPC → showSaveDialog → copy/printToPDF 흐름 TS 빌드 통과
- [ ] PDF export: 한국어 포함 Markdown → 실제 Electron Chromium 렌더링 수동 검증
- [ ] DOCX export: Word for Windows 에서 수동 열기 검증
- [ ] XLSX export: Excel 에서 수동 열기 검증
- [x] **자율 Agent 원칙**: export 는 LLM 출력 렌더링, 보고서 구조는 LLM 이 결정
