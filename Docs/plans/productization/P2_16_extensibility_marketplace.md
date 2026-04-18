# P2-16: 확장성 & 스킬 마켓플레이스

**우선순위**: P2 — Platform Growth (장기)
**요구사항 섹션**: 5.19
**상태**: **Deferred (post-beta)** — 2026-04-15 결정
**의존성**: P0-01 (sandbox), P1~P2 완료 후

---

## 연기 결정 (2026-04-15)

베타 런치 범위 밖. 마켓플레이스는 유저 기반과 3rd-party 스킬 제작자 모두
부족한 시점에 구축해도 공급이 수요를 못 따라간다. 기존 내부 skill hub 구현은
유지하되 **퍼블릭 마켓플레이스 작업은 중단**.

재개 조건 예시:
- 베타 사용자들이 자체 스킬 제작 요구 반복 제기
- 파트너사와 통합 스킬 공급 계약
- 사용자 100+ 규모에서 skill 공유 pain point 확인

---

## 자율 Agent 원칙 확인

> 스킬은 LLM에게 절차적 지식을 제공하는 Markdown 파일이다.
> 코드가 스킬을 강제 실행하지 않는다. LLM이 자율적으로 어떤 스킬을 참고할지 결정한다.
> 사용자 커스텀 스킬도 동일한 원칙 — Markdown + 선택적 tool 정의.

---

## 설계

### 스킬 구조 (기존과 동일)

```markdown
---
name: 재고 분석
description: 재고 데이터에서 부족 위험 품목을 식별
tools: [execute_code, read_file, create_chart]
author: user
version: 1.0.0
---

# 재고 분석 스킬

재고 데이터가 주어지면 다음 절차를 따릅니다:

1. 재고 회전율 계산
2. 평균 판매량 대비 현재 재고 비율 확인
3. 위험 임계치(30일 이하) 기준으로 품목 분류
...
```

---

## 구현 Phase 계획

### Phase 1: 사용자 스킬 GUI (Custom Skill Manager)

**새 파일**: `electron/src/renderer/components/settings/SkillManager.tsx`

```tsx
export function SkillManager() {
  const { data: skills } = useSkills();

  return (
    <div>
      <div className="skills-header">
        <h3>AI 스킬</h3>
        <Button onClick={openImportDialog}>스킬 가져오기</Button>
        <Button onClick={openCreateDialog}>새 스킬 만들기</Button>
      </div>

      <div className="skills-list">
        {skills?.map(skill => (
          <SkillCard key={skill.id} skill={skill}>
            <Toggle
              checked={skill.enabled}
              onChange={(enabled) => toggleSkill(skill.id, enabled)}
              label="활성화"
            />
            <Button size="sm" onClick={() => editSkill(skill)}>편집</Button>
            <Button size="sm" variant="danger" onClick={() => deleteSkill(skill.id)}>삭제</Button>
          </SkillCard>
        ))}
      </div>
    </div>
  );
}
```

**스킬 편집기**:

```tsx
function SkillEditor({ skill, onSave }: Props) {
  // Markdown 에디터 (Monaco Editor 또는 CodeMirror)
  return (
    <div>
      <Input label="스킬 이름" value={skill.name} />
      <Input label="설명" value={skill.description} />
      <MonacoEditor
        language="markdown"
        value={skill.content}
        onChange={setContent}
      />
      <div className="preview">
        <h4>미리보기</h4>
        <MarkdownRenderer content={content} />
      </div>
      <Button onClick={() => onSave(skill)}>저장</Button>
    </div>
  );
}
```

---

### Phase 2: 스킬 권한 모델 (샌드박스 연동)

사용자 스킬이 사용할 수 있는 tool 목록을 명시해야 한다.

```yaml
# 스킬 YAML 헤더
---
name: 외부 API 조회
tools: [execute_code, http_request]
permissions:
  network: [api.exchange-rate.host]  # 허용 호스트 명시
  filesystem: [workspace]            # workspace만 허용 (기본값)
---
```

스킬 실행 시 P0-01 sandbox에 이 permissions가 전달됨:
```python
sandbox_policy = SandboxPolicy(
    workspace_dir=...,
    approved_hosts=skill.permissions.network,  # 스킬 선언 호스트만 허용
)
```

---

### Phase 3: 마켓플레이스 (장기)

**스킬 등록 흐름**:
1. 사용자가 스킬 작성
2. GitHub Gist 또는 공식 레지스트리에 공유
3. 마켓플레이스에서 검색/설치

**마켓플레이스 UI (장기)**:

```tsx
function Marketplace() {
  return (
    <div>
      <SearchInput placeholder="스킬 검색... (예: 재무, 마케팅, 제조)" />
      <CategoryFilter categories={['비즈니스', '금융', '제조', '마케팅', ...]} />
      <SkillGrid>
        {skills.map(skill => (
          <MarketplaceSkillCard key={skill.id} skill={skill}>
            <Button onClick={() => installSkill(skill)}>설치</Button>
          </MarketplaceSkillCard>
        ))}
      </SkillGrid>
    </div>
  );
}
```

**심사 정책 (필요)**:
- 스킬에 악성 코드 포함 금지
- network permissions 검토
- 커뮤니티 신고 → 관리자 검토

---

### Phase 4: DB Connector Extension SDK (장기)

서드파티가 새 connector를 개발할 수 있는 인터페이스:

```python
class ConnectorPlugin(ABC):
    """서드파티 DB connector 개발 인터페이스."""

    @property
    @abstractmethod
    def connector_type(self) -> str: ...

    @abstractmethod
    def test_connection(self, config: dict) -> ConnectionTestResult: ...

    @abstractmethod
    def execute_query(self, config: dict, query: str) -> QueryResult: ...

    @abstractmethod
    def get_schema(self, config: dict) -> SchemaInfo: ...
```

---

## 현재 구현 상태 (2026-04-14)

완료된 항목:

- `SkillManager` GUI 추가: 생성 / 편집 / 활성화 / 삭제 / Markdown import
- Markdown preview 추가
- 원격 URL 기반 스킬 설치 추가
- 스킬 YAML 헤더의 `tools`, `permissions`, `enabled` 파싱 및 저장 지원
- 스킬 permissions를 샌드박스 네트워크 allowlist에 전달

남은 항목:

- 공개 마켓플레이스 검색 / 카테고리 / 설치 UX
- 스킬 심사 정책과 신고 플로우
- DB Connector Extension SDK

---

## Quality Gate

- [x] 사용자 스킬 작성 → 저장 → agent가 자율적으로 활용 확인
- [x] 스킬 permissions가 sandbox에 올바르게 전달 확인
- [x] 스킬 활성화/비활성화 즉시 반영 확인
- [x] **자율 Agent 원칙**: 스킬은 agent가 참고하는 것이지, 코드가 스킬을 강제 실행하지 않음 확인
