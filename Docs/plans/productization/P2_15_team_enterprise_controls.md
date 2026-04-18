# P2-15: 팀 & 엔터프라이즈 제어

**우선순위**: P2 — Team/Enterprise Growth
**요구사항 섹션**: 5.16, 5.17
**상태**: **Deferred (post-beta)** — 2026-04-15 결정
**의존성**: P0~P1 모두 완료 후

---

## 연기 결정 (2026-04-15)

개인/팀 소규모 사용자 베타 런치 범위를 초과. 엔터프라이즈 조달 요구가 실제로
발생하는 시점에 재개. 이미 구현된 부분(organization_store, admin console 일부,
policy runtime)은 제거하지 않고 유지하되, **신규 feature 작업은 중단**한다.

재개 조건 예시:
- 유료 팀 플랜 고객 N개 이상 파일럿 중
- 엔터프라이즈 RFP/PoC 에서 SSO / audit log 가 필수 요건
- 개인 베타에서 "내 조직에도 깔고 싶다" 요청 반복 수집

재개 시 이 문서의 Phase 계획을 업데이트하고 INDEX 상태를 In Progress 로 복귀.

---

## 자율 Agent 원칙 확인

> 팀 정책 레이어는 agent의 내부 추론 흐름에 개입하지 않는다.
> agent는 여전히 자율적으로 실행하고, 정책 레이어가 외부 side effect(provider 선택, 데이터 전송, export)만 gate한다.

---

## 핵심 기능 범위

### 개인용 vs 팀용 경계

| 기능 | Personal | Team | Enterprise |
|------|----------|------|-----------|
| 공유 프로젝트 | ✗ | ✓ | ✓ |
| Provider allowlist | ✗ | ✓ | ✓ |
| 조직 예산 한도 | ✗ | ✓ | ✓ |
| 감사 로그 export | ✗ | ✓ | ✓ |
| SSO/SAML | ✗ | ✗ | ✓ |
| RBAC | ✗ | 기본 | 세부 |

---

## 구현 계획

### Phase 1: 공유 프로젝트 + 기본 RBAC

**새 Domain 엔티티**:

```python
@dataclass
class Organization:
    id: str
    name: str
    members: list[Member]
    settings: OrgSettings

@dataclass
class Member:
    user_id: str
    role: OrgRole  # admin | editor | viewer

class OrgRole(str, Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"

@dataclass
class OrgSettings:
    allowed_providers: list[str] = field(default_factory=list)  # 빈 리스트 = 모두 허용
    max_budget_usd_per_user: float | None = None
    external_data_transfer_allowed: bool = True
    export_allowed: bool = True
    connector_creation_allowed: bool = True
```

**접근 제어 미들웨어**:

```python
class OrgPolicyGate:
    """조직 정책 검사 — agent loop 외부에서만 동작."""

    def check_provider_allowed(self, provider: str, org: Organization) -> bool:
        if not org.settings.allowed_providers:
            return True  # 모두 허용
        return provider in org.settings.allowed_providers

    def check_budget(self, user_id: str, org: Organization) -> bool:
        if org.settings.max_budget_usd_per_user is None:
            return True
        usage = get_monthly_usage(user_id)
        return usage.total_cost_usd < org.settings.max_budget_usd_per_user
```

---

### Phase 2: 관리자 콘솔 UI

```tsx
function AdminConsole() {
  return (
    <div>
      <h2>조직 설정</h2>

      <section>
        <h3>AI Provider 제어</h3>
        <MultiSelect
          label="허용된 AI 서비스"
          options={ALL_PROVIDERS}
          hint="선택 안 하면 모두 허용"
        />
      </section>

      <section>
        <h3>예산 제어</h3>
        <Input label="사용자별 월간 한도 ($)" type="number" />
        <Input label="팀 전체 월간 한도 ($)" type="number" />
      </section>

      <section>
        <h3>데이터 정책</h3>
        <Toggle label="외부 AI 서비스로 데이터 전송 허용" />
        <Toggle label="결과물 Export 허용" />
        <Toggle label="커넥터 생성 허용" />
      </section>

      <section>
        <h3>멤버 관리</h3>
        <MemberTable members={org.members} onRoleChange={updateRole} />
        <Button onClick={inviteMember}>멤버 초대</Button>
      </section>
    </div>
  );
}
```

---

### Phase 3: 감사 로그 Export

```python
@router.get("/admin/audit-log/export")
async def export_audit_log(
    start_date: date, end_date: date,
    format: Literal["csv", "jsonl"] = "csv",
    current_user: User = Depends(require_admin),
) -> StreamingResponse:
    """조직 관리자만 접근 가능한 감사 로그."""
    records = audit_log.get_range(start_date, end_date, org_id=current_user.org_id)
    # 사용자별 분석 횟수, 비용, provider 사용 현황
```

---

### Phase 4: SSO (Enterprise — 장기)

- SAML 2.0 / OIDC 지원
- Active Directory 연동
- 관리자가 정책 중앙 배포

---

## 현재 구현 상태 (2026-04-14)

완료된 항목:

- `Organization`, `Member`, `OrgRole`, `OrgSettings` 도메인 엔티티 추가
- 조직 정책 저장소 및 월간 사용량 집계 추가
- `OrgPolicyGate`를 통한 provider allowlist / 예산 / 외부 전송 / export 차단 추가
- WebSocket RPC: `org.get`, `org.updateSettings`, `org.inviteMember`, `org.updateMemberRole`, `org.auditLogExport`
- HTTP 관리자 route: `/admin/audit-log/export`
- Settings 내 `AdminConsole` UI 추가

남은 항목:

- 공유 프로젝트 권한 모델 고도화
- SSO / SAML / OIDC
- 중앙 정책 배포와 대규모 조직 운영 UX

---

## Quality Gate

- [x] Provider allowlist 설정 시 다른 provider 사용 차단 확인
- [x] 사용자별 예산 한도 초과 시 차단 확인
- [x] admin 역할만 조직 설정 접근 가능 확인
- [x] 감사 로그 CSV export 동작 확인
- [x] **자율 Agent 원칙**: 정책 게이트가 agent의 내부 추론에 개입하지 않음 확인
