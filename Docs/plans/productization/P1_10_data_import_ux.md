# P1-10: 데이터 수집 UX

**우선순위**: P1
**요구사항 섹션**: 5.5
**상태**: Complete (Postgres GA, BigQuery/Snowflake UI 출시 가능)
**의존성**: P0-01 (sandbox), P0-02 (credential for DB connectors)
**최근 감사일**: 2026-04-15 (`Docs/productization/P_NEXT_STEPS_2026-04-15.md` 참조)

---

## 현재 상태 (2026-04-15 재감사 후 마감)

- 기본 파일 업로드 UI 존재 (CSV/Excel)
- 현재 제한: 100MB
- **Backend connector RPC 완비**: `connector.list/test/save/delete` (`api/ws_handler.py:910–929`)
  - 정책 게이팅 (`_connector_creation_allowed`), 시크릿 분리 저장 (probe 시 임시 보관 후 삭제),
    read-only 강제, error catalog 기반 사용자 메시지 변환
  - Postgres / BigQuery / Snowflake 모두 어댑터 팩토리 지원
    (`tests/unit/infrastructure/test_connector_factory.py` 6/6 green)
  - SQL validator 가 DDL/DML mutating statements 전부 차단
    (`tests/unit/domain/test_connector_config.py` 20/20 green)
- **Frontend ConnectorWizard 마감 (2026-04-15)**:
  - `ts-nocheck` 제거 — 디렉티브 옆 코멘트가 stale 했고, 실제 헬퍼
    (`validateDraft`, `parseConnectorSummary`, `shouldReuseStoredSecret`,
    `buildPayload`, `draftFromSummary`, `parseTestResult` 등) 는 모두 구현되어 있었음
  - `npm run typecheck` clean (main + renderer 모두 통과)
  - Postgres / BigQuery / Snowflake 카드 토글, 자격 모드 픽업, read-only 강제,
    test → save 게이팅 (test fingerprint 일치 + ok=true 만 저장 허용) 동작 확인
- BigQuery / Snowflake: backend/UI 모두 가능. 다만 실 운영 회귀는 별도 인증서/계정 필요
  → 정식 GA 선언은 사용처 확보 시점에 결정. (`P1_10_connector_gui_design.md` 참조)

---

## 설계

### 데이터 입력 방식 계층

```
1. 드래그&드롭 / 파일 선택   — 즉시 사용, 가장 쉬움
2. 최근 파일 목록            — 재사용 편의
3. 클라우드 스토리지         — Google Drive, OneDrive (OAuth)
4. DB 커넥터                 — Postgres, BigQuery (GUI 설정)
5. URL/API                   — HTTP로 데이터 가져오기
```

---

## 구현 Phase 계획

### Phase 1: 파일 업로드 강화

**지원 형식 명시** + 오류 메시지 개선

**수정 파일**: `electron/src/renderer/components/workflow/` (파일 업로드 영역)

```tsx
const SUPPORTED_FORMATS = [
  { ext: '.csv', label: 'CSV', icon: '📄' },
  { ext: '.xlsx', ext2: '.xls', label: 'Excel', icon: '📊' },
  { ext: '.parquet', label: 'Parquet', icon: '🗜️' },
  { ext: '.json', label: 'JSON', icon: '{ }' },
  { ext: '.tsv', label: 'TSV', icon: '📄' },
];

// 크기 초과 시 대안 경로 안내
function FileSizeExceededGuide({ fileSize }: { fileSize: number }) {
  return (
    <div className="size-exceeded-guide">
      <h4>파일이 너무 큽니다 ({formatBytes(fileSize)})</h4>
      <p>다음 방법을 시도해보세요:</p>
      <ul>
        <li>
          <Button onClick={uploadSample}>샘플만 업로드 (처음 10,000행)</Button>
          <small>전체 데이터의 패턴을 먼저 확인할 수 있습니다</small>
        </li>
        <li>
          <Button onClick={openDbConnector}>데이터베이스 직접 연결</Button>
          <small>Postgres, BigQuery 등 DB에서 직접 분석</small>
        </li>
        <li>
          <Button onClick={openCloudConnector}>클라우드 스토리지 연결</Button>
          <small>Google Drive, S3 등에서 가져오기</small>
        </li>
      </ul>
    </div>
  );
}
```

### Phase 2: Excel 업로드 wizard

```tsx
function ExcelUploadWizard({ file }: Props) {
  const [sheets, setSheets] = useState<string[]>([]);
  const [selectedSheet, setSelectedSheet] = useState<string>('');
  const [headerRow, setHeaderRow] = useState(1);

  return (
    <div>
      <h4>{file.name} 설정</h4>

      <label>분석할 시트 선택</label>
      <Select
        options={sheets.map(s => ({ value: s, label: s }))}
        value={selectedSheet}
        onChange={setSelectedSheet}
      />

      <label>헤더 행 번호</label>
      <Input type="number" value={headerRow} onChange={setHeaderRow} min={1} />

      <DataPreview sheet={selectedSheet} headerRow={headerRow} />

      <Button onClick={confirm}>업로드</Button>
    </div>
  );
}
```

### Phase 3: DB Connector GUI

Implementation note: the shared connector wizard now supports Postgres, BigQuery, and Snowflake with read-only connection tests and secure secret storage.

**현재 상태**: Postgres connector list/test/save/delete 구현 완료, BigQuery/Snowflake UI는 후속

상세 설계 문서: [P1_10_connector_gui_design.md](./P1_10_connector_gui_design.md)

**새 파일**: `electron/src/renderer/components/settings/ConnectorWizard.tsx`

```tsx
const CONNECTOR_TEMPLATES = [
  {
    type: 'postgres',
    label: 'PostgreSQL',
    icon: '🐘',
    fields: [
      { id: 'host', label: '서버 주소', placeholder: 'localhost', required: true },
      { id: 'port', label: '포트', placeholder: '5432', type: 'number' },
      { id: 'database', label: '데이터베이스 이름', required: true },
      { id: 'username', label: '사용자 이름', required: true },
      { id: 'password', label: '비밀번호', type: 'password', secure: true },
      { id: 'ssl', label: 'SSL 연결', type: 'checkbox' },
    ],
  },
  {
    type: 'bigquery',
    label: 'Google BigQuery',
    icon: '☁️',
    auth: 'google_oauth',  // OAuth 사용
    fields: [
      { id: 'project_id', label: '프로젝트 ID', required: true },
      { id: 'dataset', label: '기본 데이터셋', required: false },
    ],
  },
  {
    type: 'snowflake',
    label: 'Snowflake',
    icon: '❄️',
    fields: [
      { id: 'account', label: '계정 식별자', required: true },
      { id: 'warehouse', label: 'Warehouse', required: true },
      { id: 'database', label: 'Database', required: true },
      { id: 'schema', label: 'Schema', required: false },
      { id: 'username', label: '사용자 이름', required: true },
      { id: 'password', label: '비밀번호', type: 'password', secure: true },
    ],
  },
];

export function ConnectorWizard({ onComplete }: Props) {
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  return (
    <div>
      {!selectedType && <ConnectorTypeSelector onSelect={setSelectedType} />}
      {selectedType && (
        <>
          <ConnectorForm
            template={CONNECTOR_TEMPLATES.find(t => t.type === selectedType)!}
            onTest={async (values) => {
              const result = await testConnection(selectedType, values);
              setTestResult(result);
            }}
            onSave={onComplete}
          />
          {testResult && <ConnectionTestResult result={testResult} />}
        </>
      )}
    </div>
  );
}
```

**연결 테스트 API**: `POST /api/connectors/test`
```python
@router.post("/connectors/test")
async def test_connector(config: ConnectorTestRequest) -> ConnectorTestResult:
    """read-only 쿼리로 연결 테스트."""
    # SELECT 1 또는 SELECT COUNT(*) FROM information_schema.tables
```

**보안**: DB password → P0-02 SecretStoragePort에 저장

### Phase 4: 데이터 미리보기 + 스키마 감지

**새 API**: `POST /api/data/preview`

```python
@router.post("/data/preview")
async def preview_data(request: DataPreviewRequest) -> DataPreviewResponse:
    return DataPreviewResponse(
        columns=[
            ColumnInfo(name="customer_id", dtype="int64", null_count=0),
            ColumnInfo(name="age", dtype="float64", null_count=5, sample_values=[25, 30, 45]),
            ColumnInfo(name="city", dtype="object", null_count=0, unique_count=12),
        ],
        row_count=15000,
        sample_rows=[...],  # 처음 5행
        file_size_mb=2.3,
        encoding_detected="UTF-8",
    )
```

**컴포넌트**: `DataPreviewPanel.tsx`

```tsx
function DataPreviewPanel({ preview }: Props) {
  return (
    <div>
      <div className="summary">
        <stat label="행 수" value={preview.row_count.toLocaleString()} />
        <stat label="열 수" value={preview.columns.length} />
        <stat label="파일 크기" value={`${preview.file_size_mb}MB`} />
        <stat label="인코딩" value={preview.encoding_detected} />
      </div>
      <DataTable columns={preview.columns} rows={preview.sample_rows} />
      {preview.columns.some(c => c.null_count > 0) && (
        <Notice type="info">일부 열에 빈 칸이 있습니다. AI가 자동으로 처리합니다.</Notice>
      )}
    </div>
  );
}
```

---

## Quality Gate

- [ ] CSV (UTF-8, EUC-KR), Excel (.xlsx, .xls), Parquet 업로드 테스트
- [ ] 100MB 초과 시 대안 경로 안내 표시 확인
- [ ] Excel 멀티시트 선택 wizard 동작 확인
- [ ] DB connector: Postgres 연결 테스트 성공 (read-only 확인)
- [ ] password/secret은 secure storage에 저장됨 (P0-02 연동)
- [ ] 데이터 미리보기 5행 + 스키마 표시 확인
