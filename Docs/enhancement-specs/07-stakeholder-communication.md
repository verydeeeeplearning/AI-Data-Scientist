# 07. Stakeholder Communication Engine ??audience蹂??곗텧臾??꾨떖 ?붿쭊

**Status**: Current plan scope implemented (Phase 1 render path + Phase 2 dispatch/log/query/summary surface + Phase 3 pdf/theme/handoff foundation + Electron preview-selector/theme/provider surface + adapter hardening/signed smoke coverage landed)
Latest update (2026-04-16): TaskContract can now derive a persisted audience-aware `DeliveryPack`, render individual artifacts back into that pack via `render_delivery_artifact`, dispatch rendered artifacts through a policy-aware `dispatch_delivery` path, and query persisted dispatch records through `list_delivery_log`, `ds-agent delivery log`, and `GET /api/task-contracts/{task_id}/delivery/log`. The landed scope now includes typed delivery/narrative/template models, sync-compatible `AudienceRenderer`, markdown/ipynb/pptx/pdf exporters, static template registry support, `BuildDeliveryPackUseCase` / `RenderDeliveryArtifactUseCase` / `DispatchDeliveryUseCase` / `ListDeliveryLogUseCase`, a `DeliveryRouter` with policy checks and idempotent persisted dispatch logging, tenant/project override-aware `DeliveryPolicyEngine` resolution, SQLite-backed `delivery_log` + `v_delivery_summary` for persisted task-contract flows with JSONL fallback for non-SQLite contexts, pack-level summary metadata surfaced through CLI/API/tool log queries, an `LLMNarrativeGateway` for provider-backed structured narrative generation, active `LLMProvider` injection from agent runtime into TaskContract rendering, explicit standalone CLI/API provider-backed render opt-in with default-off policy and optional model override, env-configured real `email/slack/notion/confluence/jira/compliance` adapters with simulated fallback for unconfigured channels, filesystem-backed theme loading, readonly audit PDF rendering, `dry_run` support, TaskContract container/tool wiring, CLI delivery presenters, task-contract delivery HTTP routes, and an Electron Mission Brief delivery workspace wired through IPC/preload/task-contract hooks. Electron now also exposes `tenant` / `theme_id` pack builds plus provider-backed render toggle/model override, dedicated markdown/ipynb split preview, embedded PDF viewing, and manifest-backed PPTX gallery cards. The final hardening slice is also landed: `Confluence/Jira/Compliance` real adapters require explicit feature flags, `ComplianceAdapter` emits richer signed audit payloads with stricter signer/audience guards, and env-gated signed compliance smoke coverage is in place.
**Owner**: DS Agent Core Team
**Depends on**: 01-task-contract, 02-semantic-memory, 03-verifier-orchestrator, 04-autonomy-control-plane
**Related**: 짠7 of `ds-agent-enhancement-roadmap.md`, 湲곗〈 `tools/artifact_tools.py`

---

## 0. 2026-04-16 吏꾪뻾 ?곹솴

### 2026-04-16 Addendum

- Standalone provider-backed renderer opt-in is now wired for `ds-agent delivery render` and `POST /api/task-contracts/{task_id}/delivery-artifacts/{artifact_id}/render`. The policy is explicit default-off; `--model` / `model` overrides are only accepted when provider-backed rendering is turned on.
- Phase 3 foundation landed for the stakeholder renderer path: readonly PDF export, filesystem-backed theme loading, tenant propagation on pack build/record flows, and explicit `ml_handoff_spec` / `audit_trail` template metadata are now wired into the live TaskContract delivery pipeline.
- Mission Brief now consumes `deliveryLog.summary` directly, so the Electron preview-selector surface matches the backend/API/CLI summary payload.
- Mission Brief preview now also includes a rendered-artifact preview bridge: markdown/ipynb split panes, embedded PDF viewing, and manifest-backed PPTX gallery cards without leaving the delivery workspace.
- Mission Brief now also forwards `tenant` and `globalContext.theme_id` during pack build, exposes explicit provider-backed render opt-in with optional model override, and surfaces pack tenant/theme metadata in the preview pane so the Electron workspace matches the backend/API/CLI delivery controls.
- `Confluence` / `Jira` / `Compliance` real adapters now require explicit `DS_AGENT_CONFLUENCE_ENABLED`, `DS_AGENT_JIRA_ENABLED`, and `DS_AGENT_COMPLIANCE_ENABLED` flags; `DS_AGENT_DELIVERY_REAL_ADAPTERS_ENABLED=false` disables every real adapter at once.
- `ComplianceAdapter` now rejects unsigned or non-auditor payloads earlier and includes structured `file`, `policy`, `verification`, and `audit_context` fields in the outbound submission payload.
- Added env-gated signed compliance smoke coverage in `tests/integration/infrastructure/test_signed_compliance_smoke.py` via `DS_AGENT_RUN_SIGNED_DELIVERY_SMOKE=1`.
- Added an Electron contract regression for `src/main/task-contract-preview.ts`, covering local `markdown` / `ipynb` / `pdf` / `pptx` preview loading plus manifest fallback and unsupported-format handling.
- Added direct regression coverage for `audit_trail -> pdf -> compliance_system`, `ml_handoff_spec -> markdown -> confluence+jira`, PDF export, and Deloitte theme application.
- Verification addendum:
  - `pytest tests/unit/infrastructure/test_delivery_channel_adapters.py tests/unit/infrastructure/test_delivery_router.py tests/integration/test_audit_pipeline.py tests/integration/test_ml_handoff.py tests/integration/infrastructure/test_signed_compliance_smoke.py` -> **16 passed, 1 skipped**
  - `ruff check src/ds_agent/infrastructure/delivery/channel_adapters.py tests/unit/infrastructure/test_delivery_channel_adapters.py tests/unit/infrastructure/test_delivery_router.py tests/integration/test_audit_pipeline.py tests/integration/test_ml_handoff.py tests/integration/infrastructure/test_signed_compliance_smoke.py` -> **ok**
  - `mypy src/ds_agent/infrastructure/delivery/channel_adapters.py src/ds_agent/infrastructure/delivery/delivery_router.py` -> **ok**
  - `python -m compileall src/ds_agent/infrastructure/delivery/channel_adapters.py src/ds_agent/infrastructure/delivery/delivery_router.py tests/integration/infrastructure/test_signed_compliance_smoke.py` -> **ok**
  - `pytest tests/unit/infrastructure/test_pptx_exporter.py` -> **1 passed**
  - `pytest tests/unit/infrastructure/test_delivery_cli.py tests/unit/infrastructure/test_task_contract_api_routes.py` -> **12 passed**
  - `ruff check src/ds_agent/cli/delivery_cli.py src/ds_agent/api/routes/task_contracts.py src/ds_agent/presentation/delivery_presenters.py tests/unit/infrastructure/test_delivery_cli.py tests/unit/infrastructure/test_task_contract_api_routes.py` -> **ok**
  - `mypy src/ds_agent/cli/delivery_cli.py src/ds_agent/api/routes/task_contracts.py src/ds_agent/presentation/delivery_presenters.py` -> **ok**
  - `pytest tests/unit/infrastructure/test_pdf_exporter.py tests/unit/infrastructure/test_theme_apply.py tests/integration/test_audit_pipeline.py tests/integration/test_ml_handoff.py tests/unit/infrastructure/test_delivery_channel_adapters.py tests/unit/infrastructure/test_delivery_router.py tests/integration/infrastructure/test_delivery_roundtrip.py tests/unit/infrastructure/test_task_contract_container.py tests/unit/infrastructure/test_task_contract_api_routes.py tests/unit/infrastructure/test_delivery_cli.py` -> **28 passed**
  - `ruff check src/ds_agent/infrastructure/exporters src/ds_agent/infrastructure/task_contract_container.py src/ds_agent/application/dtos/task_contract.py src/ds_agent/application/services/task_contract_usecases.py src/ds_agent/api/routes/task_contracts.py src/ds_agent/cli/delivery_cli.py src/ds_agent/tools/task_contract_tools.py tests/unit/infrastructure/test_pdf_exporter.py tests/unit/infrastructure/test_theme_apply.py tests/integration/test_audit_pipeline.py tests/integration/test_ml_handoff.py` -> **ok**
  - `mypy src/ds_agent/infrastructure/exporters src/ds_agent/infrastructure/task_contract_container.py src/ds_agent/application/dtos/task_contract.py src/ds_agent/application/services/task_contract_usecases.py src/ds_agent/api/routes/task_contracts.py src/ds_agent/cli/delivery_cli.py src/ds_agent/tools/task_contract_tools.py` -> **ok**
  - `python -m compileall src/ds_agent/infrastructure/exporters src/ds_agent/infrastructure/task_contract_container.py src/ds_agent/application/dtos/task_contract.py src/ds_agent/application/services/task_contract_usecases.py src/ds_agent/api/routes/task_contracts.py src/ds_agent/cli/delivery_cli.py src/ds_agent/tools/task_contract_tools.py` -> **ok**
  - `cd electron && npm run test:contract:mission-brief` -> **PASS**
  - `cd electron && npm run test:contract:delivery-preview` -> **PASS**
  - `cd electron && npm run typecheck` -> **ok**
  - `cd electron && npm run build` -> **ok**

### Landed

- `src/ds_agent/domain/entities/delivery_pack.py`
  - Typed stakeholder artifact model ?뺤옣: `AudienceKind`, `ArtifactType`, `ArtifactFormat`, `ContentPolicy`, `DeliveryArtifact`, `DeliveryTemplate`, `NarrativeBlocks`, `NarrativeVerification`, `DesignTheme`.
  - 湲곗〈 TaskContract `delivery_pack` 寃쎈줈? ?명솚?섎룄濡?legacy `items` view瑜??좎??섎㈃??rendered artifact ??legacy item ?숆린?? duplicate audience 李⑤떒, auditor 媛뺤젣 ?뺤콉, executive chart cap 寃利앹쓣 異붽?.
- `src/ds_agent/application/services/audience_renderer.py`
  - persona prompt synthesis, template coercion, structured narrative parsing, verifier normalization, exporter fallback ?몄텧???ы븿??Phase 1 renderer core 援ы쁽.
  - ?꾩옱??deterministic/fake generator? real exporter瑜??④퍡 ?섏슜?섎뒗 sync surface?대ŉ, provider-backed narrative adapter瑜??섏쨷??遺숈씪 ???덇쾶 寃쎄퀎瑜??좎?.
  - exporter ?몄텧??signature-aware dispatch濡??뺣━??legacy/flexible exporter? strict `PptxExporter`瑜??④퍡 ?섏슜?섍퀬, `TemplateSpec` ??`DeliveryTemplate` coercion 寃쎄퀎??蹂닿컯.
- `src/ds_agent/application/services/task_contract_usecases.py`, `src/ds_agent/tools/task_contract_tools.py`
  - `BuildDeliveryPackUseCase` 諛?`build_delivery_pack` tool 寃쎈줈 異붽?.
  - `RenderDeliveryArtifactUseCase` 諛?`render_delivery_artifact` tool 寃쎈줈 異붽?濡?persisted `DeliveryPack` ?덉쓽 artifact瑜??ㅼ젣 ?뚯씪濡??뚮뜑?섍퀬 `rendered_uri`/verifier metadata/pack status瑜??ㅼ떆 ???
  - 湲곗〈 `record_delivery_pack` ?먮쫫? typed `artifacts` payload???섏슜?섎ŉ legacy `items` 湲곕컲 ?꾨즺 ?먯젙怨??명솚.
- `src/ds_agent/tools/artifact_tools.py`
  - `render_stakeholder_artifact` tool 異붽?濡?markdown/ipynb/pptx Phase 1 renderer path瑜?濡쒖뺄 ?뚯씪 ?앹꽦源뚯? ?곌껐.
- `src/ds_agent/infrastructure/exporters/`
  - `markdown_exporter.py`, `ipynb_exporter.py`, `pptx_exporter.py`, `template_registry.py` 異붽?/蹂닿컯.
  - `src/ds_agent/infrastructure/artifact/pptx_exporter.py` compatibility wrapper 異붽?濡?湲곗〈/?좉퇋 import path瑜?紐⑤몢 ?섏슜.
- `assets/templates/registry.json`
  - `exec_brief`, `pm_memo`, `ds_note` 湲곕낯 ?쒗뵆由??덉??ㅽ듃由?異붽?.

- `src/ds_agent/infrastructure/delivery/delivery_router.py`, `src/ds_agent/infrastructure/delivery/channel_adapters.py`
  - `DeliveryRouter`, `DeliveryPolicyEngine`, `JsonlDeliveryDispatchLog`, `SqliteDeliveryDispatchLog`, env-configured real channel adapters 異붽?.
  - `SmtpEmailAdapter`, `SlackChannelAdapter`, `SlackDmAdapter`, `NotionPageAdapter`, `ConfluenceAdapter`, `JiraAdapter`, `ComplianceAdapter`瑜?援ы쁽?섍퀬, feature flag / missing-config ?곹솴?먯꽌 simulated adapter濡?fallback.
  - `ComplianceAdapter` payload??structured `file` / `policy` / `verification` / `audit_context` metadata瑜?異붽??섍퀬, `signed_by`, auditor audience, `speculative_claims=forbidden` guard瑜?媛뺤젣.
  - `(pack_id, artifact_id, channel)` idempotency, auditor signature gate, audience-channel allowlist, artifact rendered gate瑜??뺤콉 ?붿쭊?쇰줈 媛뺤젣.
- `src/ds_agent/runtime/delivery_policy_store.py`, `src/ds_agent/infrastructure/persistence/task_contract_store.py`
  - `DeliveryPolicy` 湲곕낯媛??꾩뿉 tenant/project override瑜???뒗 precedence ?댁꽍??異붽?.
  - TaskContract SQLite store??`delivery_log` table / `v_delivery_summary` view瑜?異붽??섎뒗 migration v10??諛섏쁺?섍퀬, persisted task-contract flow??SQLite dispatch log瑜?湲곕낯 ?ъ슜?섎룄濡??밴꺽.
- `src/ds_agent/infrastructure/delivery/llm_narrative_gateway.py`, `src/ds_agent/infrastructure/task_contract_container.py`, `src/ds_agent/agent/factory.py`
  - `LLMNarrativeGateway` ????怨? ?곕떽???`LLMProvider.chat()` 疫꿸퀡而?stakeholder narrative generation 野껋럥以덄몴??닌뗭겱.
  - OpenAI `json_object`, reasoning model `reasoning_effort=low`, Anthropic `thinking=False` ??쇱젟??JSON narrative ??됱젟?源딆넅.
  - agent runtime??active provider??TaskContract container嚥?雅뚯눘???곴퐣 tool-based stakeholder rendering?? ??쇱젫 provider???????롫즲嚥??怨뚭퍙.
- `src/ds_agent/application/services/task_contract_usecases.py`, `src/ds_agent/infrastructure/task_contract_container.py`, `src/ds_agent/tools/task_contract_tools.py`
  - `DispatchDeliveryUseCase` 諛?`dispatch_delivery` tool 寃쎈줈 異붽?.
  - artifact/channel subset dispatch, `approve_manual_review` override, `dry_run` evaluation, dispatch ?댄썑 pack status/event/version 媛깆떊??TaskContract 寃쎄퀎???곌껐.
- `src/ds_agent/cli/delivery_cli.py`, `src/ds_agent/presentation/delivery_presenters.py`
  - `ds-agent delivery build|render|dispatch` surface 異붽?.
  - inline/file analysis payload 濡쒕뵫, `KEY=VALUE` context parsing, build/render/dispatch human-readable output瑜?CLI 寃쎄퀎??怨좎젙.
- `src/ds_agent/api/routes/task_contracts.py`
  - `/api/task-contracts/{task_id}/delivery-pack/build`
  - `/api/task-contracts/{task_id}/delivery-artifacts/{artifact_id}/render`
  - `/api/task-contracts/{task_id}/delivery/dispatch`
  - Desktop/operator surface媛 typed delivery workflow瑜?吏곸젒 ?몄텧?????덈룄濡?湲곗〈 task-contract router??delivery action endpoint瑜?異붽?.

- `src/ds_agent/application/services/task_contract_usecases.py`, `src/ds_agent/tools/task_contract_tools.py`, `src/ds_agent/cli/delivery_cli.py`, `src/ds_agent/api/routes/task_contracts.py`
  - `ListDeliveryLogUseCase` / `list_delivery_log` tool / `ds-agent delivery log` / `GET /api/task-contracts/{task_id}/delivery/log` query surface 異붽?.
  - task/pack/artifact/channel/limit ?꾪꽣 湲곗??쇰줈 persisted dispatch records瑜?議고쉶?섍퀬 ?댁쁺?먯슜 presenter 異쒕젰源뚯? ?곌껐.

  - current pack 湲곗? `summary` metadata(pack status, artifact/rendered counts, sent/blocked/failed/duplicate counts, last attempt)瑜??④퍡 諛섑솚?섎룄濡??뺤옣.
- `electron/src/main/ipc.ts`, `electron/src/preload/index.ts`, `electron/src/renderer/vite-env.d.ts`, `electron/src/renderer/types/taskContract.ts`, `electron/src/renderer/hooks/useTaskContract.ts`
  - Electron `taskContract` bridge??build/render/dispatch/log-query IPC瑜?異붽??섍퀬, typed renderer model + delivery log state + Mission Brief action hook???곌껐.
- `electron/src/renderer/components/mission/MissionBriefPanel.tsx`, `electron/src/renderer/components/workflow/AudienceSelector.tsx`, `electron/src/renderer/components/workflow/DeliveryPackPreview.tsx`, `electron/src/renderer/components/workflow/ChannelInspector.tsx`
  - Mission Brief ?덉뿉??audience selection, pack build/rebuild, render input editing, dry-run/send CTA, rendered file reveal, pack preview, channel status, delivery log summary瑜?吏곸젒 ?ㅻ（??Electron preview-selector surface瑜?異붽?.
- `electron/src/main/ipc.ts`, `electron/src/main/task-contract-preview.ts`, `electron/src/preload/index.ts`, `electron/src/renderer/types/taskContract.ts`, `electron/src/renderer/components/workflow/ArtifactInlinePreview.tsx`
  - local rendered artifact preview IPC瑜?異붽??섍퀬, markdown/ipynb split preview, embedded PDF viewing, and manifest-backed PPTX gallery cards瑜?Mission Brief preview ?덉뿉??吏곸젒 ?몄텧.

### Verification

- `pytest tests/unit/application/test_delivery_pack_usecases.py tests/unit/infrastructure/test_delivery_router.py tests/unit/tools/test_task_contract_tools.py tests/unit/infrastructure/test_delivery_cli.py tests/unit/infrastructure/test_task_contract_api_routes.py tests/integration/infrastructure/test_delivery_roundtrip.py` ??**24 passed**

- `pytest tests/unit/application/test_delivery_pack_usecases.py tests/unit/infrastructure/test_delivery_router.py tests/unit/tools/test_task_contract_tools.py tests/unit/infrastructure/test_delivery_cli.py tests/unit/infrastructure/test_task_contract_api_routes.py` ??**20 passed**

- `pytest tests/unit/application/test_audience_renderer.py tests/unit/application/test_delivery_pack_usecases.py tests/unit/infrastructure/test_delivery_router.py tests/unit/infrastructure/test_delivery_cli.py tests/unit/infrastructure/test_task_contract_api_routes.py tests/unit/tools/test_task_contract_tools.py tests/unit/application/test_task_contract_usecases.py` ??**32 passed**
- `ruff check src/ds_agent/cli/delivery_cli.py src/ds_agent/presentation/delivery_presenters.py src/ds_agent/api/routes/task_contracts.py tests/unit/infrastructure/test_delivery_cli.py tests/unit/infrastructure/test_task_contract_api_routes.py` ??**ok**
- `mypy src/ds_agent/cli/delivery_cli.py src/ds_agent/presentation/delivery_presenters.py src/ds_agent/api/routes/task_contracts.py` ??**ok**

- `pytest tests/unit/infrastructure/test_delivery_policy.py tests/unit/infrastructure/test_delivery_router.py tests/integration/infrastructure/test_sqlite_task_contract_store.py tests/integration/infrastructure/test_delivery_roundtrip.py` -> **18 passed**
- `pytest tests/unit/application/test_delivery_pack_usecases.py tests/unit/tools/test_task_contract_tools.py tests/unit/infrastructure/test_delivery_router.py tests/unit/infrastructure/test_delivery_policy.py tests/integration/infrastructure/test_sqlite_task_contract_store.py tests/integration/infrastructure/test_delivery_roundtrip.py` -> **26 passed**
- `pytest tests/unit/infrastructure/test_llm_narrative_gateway.py tests/unit/infrastructure/test_task_contract_container.py tests/unit/application/test_audience_renderer.py tests/unit/infrastructure/test_delivery_cli.py tests/unit/tools/test_task_contract_tools.py tests/unit/infrastructure/test_task_contract_api_routes.py tests/unit/application/test_delivery_pack_usecases.py tests/integration/infrastructure/test_delivery_roundtrip.py` -> **25 passed**
- `pytest tests/unit/infrastructure/test_delivery_channel_adapters.py tests/unit/infrastructure/test_delivery_router.py` -> **12 passed**
- `pytest tests/unit/infrastructure/test_delivery_cli.py tests/unit/tools/test_task_contract_tools.py tests/unit/application/test_delivery_pack_usecases.py tests/unit/infrastructure/test_task_contract_api_routes.py tests/integration/infrastructure/test_delivery_roundtrip.py` -> **19 passed**
- `pytest tests/unit/infrastructure/test_delivery_channel_adapters.py tests/unit/infrastructure/test_delivery_router.py tests/unit/infrastructure/test_delivery_cli.py tests/unit/tools/test_task_contract_tools.py tests/unit/application/test_delivery_pack_usecases.py tests/unit/infrastructure/test_task_contract_api_routes.py tests/integration/infrastructure/test_delivery_roundtrip.py` -> **31 passed**
- `ruff check src/ds_agent/runtime/delivery_policy_store.py src/ds_agent/infrastructure/delivery src/ds_agent/infrastructure/persistence/task_contract_store.py src/ds_agent/infrastructure/task_contract_container.py tests/unit/infrastructure/test_delivery_policy.py tests/unit/infrastructure/test_delivery_router.py tests/unit/application/test_delivery_pack_usecases.py tests/unit/tools/test_task_contract_tools.py tests/integration/infrastructure/test_sqlite_task_contract_store.py tests/integration/infrastructure/test_delivery_roundtrip.py` -> **ok**
- `ruff check src/ds_agent/application/services/audience_renderer.py src/ds_agent/infrastructure/delivery/__init__.py src/ds_agent/infrastructure/delivery/llm_narrative_gateway.py src/ds_agent/infrastructure/task_contract_container.py src/ds_agent/agent/factory.py tests/unit/infrastructure/test_llm_narrative_gateway.py tests/unit/infrastructure/test_task_contract_container.py` -> **ok**
- `ruff check src/ds_agent/infrastructure/delivery/channel_adapters.py src/ds_agent/infrastructure/delivery/delivery_router.py src/ds_agent/infrastructure/delivery/__init__.py tests/unit/infrastructure/test_delivery_channel_adapters.py` -> **ok**
- `mypy src/ds_agent/runtime/delivery_policy_store.py src/ds_agent/infrastructure/delivery src/ds_agent/infrastructure/persistence/task_contract_store.py src/ds_agent/infrastructure/task_contract_container.py src/ds_agent/application/dtos/delivery.py src/ds_agent/application/ports/task_contract_support.py src/ds_agent/application/services/task_contract_usecases.py src/ds_agent/tools/task_contract_tools.py` -> **ok** (existing `pyproject.toml` unused override note unchanged)
- `python -m compileall src/ds_agent/runtime/delivery_policy_store.py src/ds_agent/infrastructure/delivery src/ds_agent/infrastructure/persistence/task_contract_store.py src/ds_agent/infrastructure/task_contract_container.py tests/unit/infrastructure/test_delivery_policy.py tests/unit/infrastructure/test_delivery_router.py tests/integration/infrastructure/test_sqlite_task_contract_store.py tests/integration/infrastructure/test_delivery_roundtrip.py` -> **ok**
- `cd electron && npm run typecheck` -> **ok**
- `cd electron && npm run build` -> **ok**

### Remaining

- Current planned scope implemented. Further work, if any, is rollout-specific adapter adoption rather than spec-deliverable gaps.

---

## 1. 諛곌꼍 諛?臾몄젣 ?뺤쓽

### 1.1 "寃곌낵瑜?留욏엳???щ엺蹂대떎 ?щ엺???吏곸씠???щ엺"

湲곗뾽 ?섍꼍?먯꽌 Data Scientist ??媛移섎뒗 "?뺣떟 紐⑤뜽"??留뚮뱶?????덉? ?딅떎.
媛숈? 遺꾩꽍 寃곌낵?쇰룄 **?꾧뎄?먭쾶**, **?대뼡 源딆씠濡?*, **?대뼡 ?щ㎎?쇰줈**, **?대뒓 梨꾨꼸濡?* ?꾨떖?섎뒓?먯뿉 ?곕씪
?섏궗寃곗젙???대젮吏嫄곕굹, 臾댁떆?섍굅?? 濡ㅻ갚?쒕떎.

?ㅼ쓬? ?ㅼ젣 ?꾩옣?먯꽌 諛섎났?섎뒗 ?ㅽ뙣 ?⑦꽩?대떎.

1. **Executive 媛 30?μ쭨由?二쇳뵾???명듃遺곸쓣 諛쏅뒗??** ??3遺?????쓣 ?ル뒗??
2. **PM ??ROC curve ? p-value 留??닿릿 蹂닿퀬?쒕? 諛쏅뒗??** ???ㅼ쓬 ?ㅽ봽由고듃 ?≪뀡?쇰줈 踰덉뿭?섏? 紐삵븳??
3. **ML Engineer 媛 markdown ?붿빟留?蹂닿퀬 ?쒕튃???쒖옉?쒕떎.** ??feature ?뺤쓽 遺덉씪移섎줈 ?꾨줈?뺤뀡 ?μ븷.
4. **Auditor 媛 "紐⑤뜽 ?깅뒫??醫뗭뒿?덈떎"?쇰뒗 異붿륫??臾몄옣??蹂몃떎.** ??洹쒖젣 ?꾨컲?쇰줈 ?꾩껜 ?꾨줈?앺듃 以묐떒.

臾몄젣??蹂몄쭏? "?섎굹???곗텧臾쇰줈 紐⑤뱺 ?щ엺??留뚯”?쒗궎?ㅻ뒗 ?쒕룄"???덈떎.

### 1.2 ?꾩옱 援ъ“???쒓퀎

?꾪뻾 DS Agent ???ㅼ쓬 ?꾧뎄濡??곗텧臾쇱쓣 ?앹꽦?쒕떎.

| ?꾧뎄 | ??븷 | ?쒓퀎 |
|------|------|------|
| `tools/artifact_tools.py::export_ipynb` | Jupyter notebook ?대낫?닿린 | audience 媛쒕뀗 ?놁쓬, ?먮낯 肄붾뱶/異쒕젰 洹몃?濡?|
| `tools/artifact_tools.py::export_pdf` | 蹂닿퀬??PDF | ?⑥씪 ?쒗뵆由? 紐⑤뱺 泥?쨷 ?숈씪 |
| `tools/artifact_tools.py::export_docx` | Word 臾몄꽌 | 議곗쭅 釉뚮옖??諛섏쁺 ????|
| `tools/artifact_tools.py::export_xlsx` | ?곗씠??吏????| ?レ옄留? narrative ?놁쓬 |
| (?놁쓬) | **PPTX ?щ씪?대뱶 ??* | 湲곗뾽 理쒖쥌 ?곗텧臾쇱? ?遺遺?PPT ?몃뜲 誘몄???|
| `runtime/outcome_delivery.py` | 梨꾨꼸 ?꾨떖 | ?⑥씪 梨꾨꼸, audience 遺꾧린 ?놁쓬 |

### 1.3 蹂??ㅽ럺??踰붿쐞

짠4 Autonomy Control Plane ?먯꽌 ?꾩엯??**Audience Persona 5醫?*(Junior Mentor / Peer DS / Senior / Executive / Auditor)??짠1 Task Contract ??`required_deliverables` ? 寃고빀?섏뿬,
?섎굹??遺꾩꽍 寃곌낵瑜?**蹂듭닔??泥?쨷 留욎땄 ?곗텧臾???* ?쇰줈 ?먮룞 蹂?샕룹쟾?ы븯???붿쭊???ㅺ퀎?쒕떎.

?듭떖 ?좉퇋 而댄룷?뚰듃????媛吏??

- **DeliveryPack** (domain entity) ??泥?쨷蹂??곗텧臾?踰덈뱾??遺덈? 紐낆꽭.
- **AudienceRenderer** (application use case) ??遺꾩꽍 寃곌낵 + audience profile ??泥?쨷 留욎땄 artifact.
- **PptxExporter** (infrastructure adapter) ??python-pptx 湲곕컲 ?щ씪?대뱶 ???앹꽦.
- **DeliveryRouter** (infrastructure adapter) ??梨꾨꼸蹂?dispatch (email / slack / notion / confluence / jira / compliance).

---

## 2. ?듭떖 ?뚯젣

1. **媛숈? 遺꾩꽍, ?ㅻⅨ ?꾨떖.** ?섎굹??`FinalAnalysis` ??N媛쒖쓽 artifact 濡?遺꾧린?섎ŉ, 媛?artifact ???낅┰?곸쑝濡??뚮뜑쨌寃利씲톎ispatch ?쒕떎.
2. **LLM = orchestrator, Renderer = formatter.** 泥?쨷蹂?narrative ??**LLM ???섎Ⅴ?뚮굹 ?꾨＼?꾪듃濡??앹꽦**?섎ŉ, ?뚮뜑?щ뒗 ?щ㎎???덉씠?꾩썐/李⑦듃留??대떦?쒕떎. 怨좎젙 ?쒗뵆由우뿉 媛믪쓣 苑귥븘 ?ｋ뒗 workflow automation ? 湲덉??쒕떎.
3. **Typed artifact.** 紐⑤뱺 ?곗텧臾쇱? `DeliveryPack` Pydantic 紐⑤뜽濡??쒗쁽?섍퀬, ?앹꽦쨌寃利씲룹??Β룹쟾???④퀎 紐⑤몢 ?숈씪 ?ㅽ궎留덈? 怨듭쑀?쒕떎.
4. **Narrative Verifier ???寃고빀.** 媛?artifact ???앹꽦 吏곹썑 짠3 Verifier 媛 怨쇱옣쨌?꾨씫???먭??섍퀬, `speculative_claims: forbidden` ??audience(?? auditor) ????댁꽌???섎뱶 寃뚯씠?몃줈 ?묐룞?쒕떎.
5. **梨꾨꼸? audience ??醫낆냽?쒕떎.** executive ?먭쾶 ipynb 瑜?蹂대궡吏 ?딄퀬, auditor ?먭쾶 slack DM ??蹂대궡吏 ?딅뒗?? `delivery_policy_store` 媛 留ㅽ븨???뚯쑀?쒕떎.
6. **PPTX ???쇨툒 ?쒕?.** 湲곗뾽 理쒖쥌 ?곗텧臾쇱쓽 ?뺣룄??鍮꾩쑉??PPT ?대?濡? pdf/docx ? ?숆툒?쇰줈 痍④툒?쒕떎.
7. **TDD + Clean Architecture.** 紐⑤뱺 phase ???ㅽ뙣 ?뚯뒪?몃? 癒쇱? ?묒꽦?섍퀬, domain ??application ??infrastructure ?쒖쑝濡?援ы쁽?쒕떎.

---

## 3. DeliveryPack ?꾩껜 ?ㅽ궎留?
### 3.1 YAML ?덉떆

```yaml
delivery_pack:
  pack_id: dp_2026_0415_001
  task_id: TC-2026-042
  generated_at: 2026-04-15T14:30:00Z
  source_analysis_id: fa_2026_0415_034
  confidence: 0.82
  signed_by: ds-agent@org.local
  signature: sha256:9ab...e1

  global_context:
    project: churn_q2_2026
    data_cutoff: 2026-04-10
    verifier_snapshot: vr_0034

  artifacts:
    - artifact_id: art_exec_01
      type: exec_brief
      audience: executive
      format: pptx
      content_policy:
        max_pages: 3
        structure: [situation, finding, impact, recommendation, decision_needed]
        technical_detail: minimal
        chart_count_range: [2, 3]
        tone: decisive
        speculative_claims: flagged
      template_ref: tpl/exec_brief/v3
      delivery_channel: [email, slack_dm]
      dispatch_mode: auto
      receivers:
        - role: cxo
          resolver: org_directory

    - artifact_id: art_pm_01
      type: pm_action_memo
      audience: pm
      format: markdown
      content_policy:
        structure: [summary, next_actions, eta, trade_offs, dependencies]
        include_jira_links: true
        tone: actionable
      template_ref: tpl/pm_memo/v2
      delivery_channel: [slack_channel, notion_page]
      dispatch_mode: auto

    - artifact_id: art_ds_01
      type: ds_experiment_note
      audience: ds_peer
      format: ipynb
      content_policy:
        structure: [hypothesis, methodology, results, caveats, reproducibility]
        include_code: true
        include_verifier_results: true
        tone: precise
      template_ref: tpl/ds_note/v4
      delivery_channel: [git_pr]
      dispatch_mode: manual_review

    - artifact_id: art_ml_01
      type: ml_handoff_spec
      audience: ml_engineer
      format: markdown
      content_policy:
        structure: [model_card, serving_config, monitoring_setup, rollback_plan]
        include_feature_registry_refs: true
      template_ref: tpl/ml_handoff/v2
      delivery_channel: [confluence, jira_ticket]
      dispatch_mode: manual_review

    - artifact_id: art_audit_01
      type: audit_trail
      audience: auditor
      format: pdf
      content_policy:
        structure: [data_provenance, access_log, policy_compliance, approval_chain, lineage]
        speculative_claims: forbidden
        tone: neutral
      template_ref: tpl/audit/v1
      delivery_channel: [compliance_system]
      dispatch_mode: auto_with_signature
```

### 3.2 Pydantic 紐⑤뜽 (domain)

```python
# src/domain/entities/delivery_pack.py
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class AudienceKind(str, Enum):
    EXECUTIVE = "executive"
    PM = "pm"
    DS_PEER = "ds_peer"
    ML_ENGINEER = "ml_engineer"
    AUDITOR = "auditor"
    JUNIOR_MENTEE = "junior_mentee"


class ArtifactType(str, Enum):
    EXEC_BRIEF = "exec_brief"
    PM_ACTION_MEMO = "pm_action_memo"
    DS_EXPERIMENT_NOTE = "ds_experiment_note"
    ML_HANDOFF_SPEC = "ml_handoff_spec"
    AUDIT_TRAIL = "audit_trail"


class ArtifactFormat(str, Enum):
    PPTX = "pptx"
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    IPYNB = "ipynb"
    MARKDOWN = "markdown"


class DeliveryChannel(str, Enum):
    EMAIL = "email"
    SLACK_DM = "slack_dm"
    SLACK_CHANNEL = "slack_channel"
    NOTION_PAGE = "notion_page"
    CONFLUENCE = "confluence"
    JIRA_TICKET = "jira_ticket"
    GIT_PR = "git_pr"
    COMPLIANCE_SYSTEM = "compliance_system"


class SpeculativeClaimsPolicy(str, Enum):
    ALLOWED = "allowed"
    FLAGGED = "flagged"
    FORBIDDEN = "forbidden"


class ContentPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    structure: list[str]
    max_pages: int | None = None
    chart_count_range: tuple[int, int] | None = None
    technical_detail: Literal["minimal", "balanced", "deep"] = "balanced"
    tone: Literal["decisive", "actionable", "precise", "neutral", "mentoring"] = "precise"
    include_code: bool = False
    include_verifier_results: bool = False
    include_jira_links: bool = False
    include_feature_registry_refs: bool = False
    speculative_claims: SpeculativeClaimsPolicy = SpeculativeClaimsPolicy.FLAGGED


class DeliveryReceiver(BaseModel):
    model_config = ConfigDict(frozen=True)
    role: str
    resolver: Literal["org_directory", "static_list", "task_contract"]
    static_addresses: list[str] = Field(default_factory=list)


class DeliveryArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: str
    type: ArtifactType
    audience: AudienceKind
    format: ArtifactFormat
    content_policy: ContentPolicy
    template_ref: str
    delivery_channel: list[DeliveryChannel]
    dispatch_mode: Literal["auto", "auto_with_signature", "manual_review"] = "manual_review"
    receivers: list[DeliveryReceiver] = Field(default_factory=list)
    rendered_uri: str | None = None
    verifier_report_id: str | None = None


class DeliveryPack(BaseModel):
    model_config = ConfigDict(frozen=True)

    pack_id: str
    task_id: str
    source_analysis_id: str
    generated_at: datetime
    confidence: float = Field(ge=0.0, le=1.0)
    signed_by: str
    signature: str | None = None
    global_context: dict[str, str]
    artifacts: list[DeliveryArtifact]

    def artifact_for(self, audience: AudienceKind) -> DeliveryArtifact | None:
        for a in self.artifacts:
            if a.audience == audience:
                return a
        return None
```

### 3.3 遺덈? 議곌굔

- `DeliveryPack` ? ?앹꽦 ??遺덈?(`frozen=True`). ?섏젙???꾩슂?섎㈃ ??pack_id 濡?踰꾩쟾??
- ?숈씪 `audience` ?????以묐났 artifact 湲덉? (validator).
- `auditor` audience ??artifact ??諛섎뱶??`speculative_claims=forbidden` 怨?`dispatch_mode=auto_with_signature`.
- `executive` audience ??artifact ??`chart_count_range` ?곹븳? 5瑜?珥덇낵?????녿떎.

---

## 4. Artifact ?좏삎 ?곸꽭

### 4.1 exec_brief (format: pptx, audience: executive)

**紐⑹쟻**: C-level ?섏궗寃곗젙沅뚯옄媛 3遺??덉뿉 "臾댁뾿??寃곗젙?댁빞 ?섎뒗吏" ?뚯븙.

| ??ぉ | 媛?|
|------|-----|
| 理쒕? 遺꾨웾 | 3 ?щ씪?대뱶 (??댄? ?쒖쇅) |
| ?꾩닔 ?뱀뀡 | situation / finding / impact / recommendation / decision_needed |
| 李⑦듃 | 2~3 媛? 媛?李⑦듃??**?섎굹???レ옄 硫붿떆吏**留?媛吏꾨떎 |
| 湲곗닠??源딆씠 | p-value, AUC, loss 怨≪꽑 ??湲덉?. ROI, expected_impact, risk 以묒떖 |
| ??| ?⑥젙??decisive). "~?????덉뒿?덈떎" ??"~?⑸땲??~?꾩슂?⑸땲?? |
| speculative_claims | flagged (Verifier 媛 諛쒓껄 ??slide footer ??寃쎄퀬 ?쒖떆) |

?щ씪?대뱶 怨④꺽:
1. **Situation + Finding** ????以??붿빟 + KPI 1媛?2. **Impact** ???덉긽 ?곹뼢 湲덉븸/吏??+ 1 李⑦듃
3. **Recommendation + Decision Needed** ??3媛??듭뀡 + 沅뚭퀬??+ 湲고븳

### 4.2 pm_action_memo (format: markdown ??notion_page, audience: pm)

**紐⑹쟻**: ?ㅼ쓬 ?ㅽ봽由고듃??援ъ껜???≪뀡 ?꾩씠???앹꽦.

| ??ぉ | 媛?|
|------|-----|
| 湲몄씠 | 300~600 ?⑥뼱 |
| ?꾩닔 ?뱀뀡 | summary / next_actions / eta / trade_offs / dependencies |
| next_actions | 泥댄겕諛뺤뒪 由ъ뒪?? 媛???ぉ??梨낆엫?먃룰린?쑣텷ira 留곹겕 |
| trade_offs | ???뺤떇 (option / benefit / risk / cost) |
| ??| actionable. 紐⑤뱺 臾몄옣? ?숈궗濡??쒖옉?섍굅??吏덈Ц ?뺥깭 湲덉? |
| include_jira_links | true ??TaskContract.linked_tickets ?먮룞 ?쎌엯 |

### 4.3 ds_experiment_note (format: ipynb, audience: ds_peer)

**紐⑹쟻**: ?숇즺 DS 媛 ?ы쁽쨌寃?졖룸퉬?먰븷 ???덈뒗 ?ㅽ뿕 ?명듃.

| ??ぉ | 媛?|
|------|-----|
| ?꾩닔 ?뱀뀡 | hypothesis / methodology / results / caveats / reproducibility |
| ? 援ъ꽦 | markdown ??code ??output ?쒖꽌 ?꾧꺽 ?좎? |
| ?ы쁽??| seed, data snapshot hash, library versions, git commit SHA |
| caveats | Narrative Verifier 媛 flag ??紐⑤뱺 ??ぉ ?ы븿 (?④린吏 ?딆쓬) |
| include_verifier_results | true ??留덉?留??뱀뀡??verifier_report ?뚯씠釉?|
| ??| precise. 二쇱옣蹂대떎 "愿痢?/ 議곌굔 / 寃곌낵" ?쒖꽌 |

### 4.4 ml_handoff_spec (format: markdown ??confluence + jira, audience: ml_engineer)

**紐⑹쟻**: 紐⑤뜽 ?쒕튃쨌?댁쁺 ?멸퀎.

| ?뱀뀡 | ?댁슜 |
|------|------|
| model_card | ?낅젰 ?ㅽ궎留? 異쒕젰 ?ㅽ궎留? ?숈뒿 ?곗씠??踰붿쐞, 怨듭젙??吏??|
| serving_config | latency SLO, batch vs online, GPU ?붽뎄?ы빆, autoscaling 湲곗? |
| monitoring_setup | drift 吏?? alert threshold, dashboard 留곹겕 |
| rollback_plan | trigger 議곌굔, ?댁쟾 踰꾩쟾 artifact URI, ?뚯슂 ?쒓컙 異붿젙 |

- `include_feature_registry_refs: true` ??Feature Store entity ID 瑜?紐낆떆.
- Confluence ??蹂몃Ц, Jira ??"ML Handoff: <model_name>" ticket ?먮룞 ?앹꽦 (留곹겕 援먯감 ?쎌엯).

### 4.5 audit_trail (format: pdf, audience: auditor)

**紐⑹쟻**: 洹쒖젣쨌媛먯궗 ?붽뎄 利앸튃.

| ?뱀뀡 | ?댁슜 |
|------|------|
| data_provenance | 紐⑤뱺 ?곗씠???뚯뒪 lineage (source ??transform ??feature ??model) |
| access_log | ?ㅽ뻾 ?쒖젏??沅뚰븳쨌IAM ?ㅻ깄??|
| policy_compliance | Autonomy Policy Engine (짠4) ?됯? 寃곌낵 |
| approval_chain | ?뱀씤?먃룻??꾩뒪?ы봽쨌signature |
| lineage | Semantic Memory (짠2) ??lineage_graph snapshot |

- `speculative_claims: forbidden` ??Verifier 媛 ?섎굹?쇰룄 flag ?섎㈃ generation ?ㅽ뙣濡?媛꾩＜, pack ?곹깭 `rejected`.
- `dispatch_mode: auto_with_signature` ???쒕챸 ?ㅻ줈 PDF ?댁떆 ?쒕챸 ??compliance_system ???쒖텧.
- PDF ???몄쭛 遺덇?(readonly), ?고듃 ?꾨쿋???꾩닔.

---

## 5. AudienceRenderer ?ㅺ퀎

### 5.1 ??븷

- ?낅젰: `FinalAnalysis` + `AudienceProfile`(짠4) + `ContentPolicy` + `TemplateRef`.
- 異쒕젰: `RenderedArtifact` DTO (format 蹂?bytes/path + narrative blocks + chart refs).
- **LLM ?몄텧? renderer 媛 ?섑뻾**?섎릺, ?꾨＼?꾪듃 議곕┰怨?異쒕젰 ?ㅽ궎留?寃利앹쓣 梨낆엫吏꾨떎.

### 5.2 ?대? ?뚯씠?꾨씪??
```
AudienceRenderer.render(analysis, profile, policy, template_ref):
    1. persona_prompt  = PersonaPromptBuilder.build(profile, policy)
    2. content_prompt  = AnalysisSummarizer.brief(analysis, depth=policy.technical_detail)
    3. skeleton        = TemplateRegistry.load(template_ref).skeleton_for(policy.structure)
    4. llm_response    = LLMGateway.complete(
                            system=persona_prompt,
                            user=content_prompt + skeleton,
                            response_schema=NarrativeBlocks)
    5. verified        = NarrativeVerifier.check(llm_response, policy.speculative_claims)
    6. charts          = ChartRenderer.render_each(llm_response.chart_specs)
    7. assembled       = FormatAssembler.for(format).assemble(llm_response, charts, template_ref)
    8. return RenderedArtifact(bytes=assembled, blocks=verified.blocks, verifier_report=verified.report)
```

### 5.3 ?섎Ⅴ?뚮굹 ?꾨＼?꾪듃 議곕┰

짠4 ??`AudiencePersona` 瑜??ъ궗?⑺븳?? 媛?persona ??怨좎젙 system prompt fragment 瑜?媛吏꾨떎.

```python
PERSONA_PROMPTS = {
    AudienceKind.EXECUTIVE: """
You are briefing a C-level decision maker. Rules:
- Maximum 3 bullet points per slide.
- Every number must be tied to business impact (won, %, days).
- Never mention p-values, AUC, or model names.
- End with a single decision question.
""",
    AudienceKind.DS_PEER: """
You are writing for a senior data scientist peer who will reproduce your work. Rules:
- State hypothesis, data, method, result, caveat in this exact order.
- Include all statistical caveats. Do not hide negative findings.
- Assume the reader can read code.
""",
    AudienceKind.AUDITOR: """
You are writing for a regulatory auditor. Rules:
- State only what is directly supported by logs or verifier output.
- Zero speculation. If uncertain, write "Not observed" rather than inferring.
- Cite every claim with a lineage_id.
""",
    # ...
}
```

Renderer ??persona prompt ??`ContentPolicy` 濡쒕????뚯깮???고????쒖빟(理쒕? ?좏겙, 援ъ“ ?ㅽ궎留? tone)???㏓텤??理쒖쥌 system prompt 瑜?留뚮뱺?? **Renderer ?먯껜??遺꾩꽍 濡쒖쭅? ?녿떎** ??遺꾩꽍? LLM ?? 寃利앹? Verifier 媛.

### 5.4 異쒕젰 ?ㅽ궎留?(NarrativeBlocks)

LLM ? ?먯쑀 ?띿뒪?멸? ?꾨땶 援ъ“???묐떟??諛섑솚?쒕떎.

```python
class NarrativeBlock(BaseModel):
    section: str                 # e.g., "situation"
    title: str
    body_md: str
    chart_specs: list[ChartSpec]
    citations: list[str]         # lineage_id ?먮뒗 verifier_finding_id

class NarrativeBlocks(BaseModel):
    blocks: list[NarrativeBlock]
    overall_tone: str
    flagged_claims: list[str]
```

???ㅽ궎留덈? 洹몃?濡?LLM ?묐떟 schema 濡??꾨떖?섏뿬, renderer 媛 ?뚯떛 ?ㅽ뙣/?꾨씫??利됱떆 媛먯??쒕떎.

---

## 6. PPTX ?먮룞 ?앹꽦 ?뚯씠?꾨씪??
### 6.1 ?뚯씠?꾨씪??
```
DeliveryPack.exec_brief
    ??AudienceRenderer.render(audience=executive, format=pptx)
    ??NarrativeBlocks  +  ChartSpec list
    ??ChartRenderer (matplotlib) ??PNG (300dpi, sRGB)
    ??PptxExporter (python-pptx)
    ?쒋? load master template (tpl/exec_brief/v3.pptx)
    ?쒋? apply DesignSystem (theme: org_theme_deloitte_v2)
    ?쒋? for each block: create slide, insert text frames + chart image
    ?쒋? insert footer with confidence / signature / verifier flags
    ?붴? save to artifacts/exec_brief_<pack_id>.pptx
    ??PdfRasterizer (optional, libreoffice headless) ??PDF fallback
    ??DeliveryRouter
```

### 6.2 肄붾뱶 ?ㅼ?移?
```python
# src/infrastructure/exporters/pptx_exporter.py
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor


class PptxExporter:
    def __init__(self, theme: DesignTheme, master_loader: PptxMasterLoader) -> None:
        self._theme = theme
        self._loader = master_loader

    def export(self, artifact: DeliveryArtifact, narrative: NarrativeBlocks,
               charts: list[RenderedChart], output_dir: Path) -> Path:
        prs = self._loader.load(artifact.template_ref)
        self._apply_theme(prs, self._theme)

        for block in narrative.blocks:
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            self._write_title(slide, block.title)
            self._write_body(slide, block.body_md)
            for spec in block.chart_specs:
                chart_path = self._find_chart(charts, spec.chart_id)
                slide.shapes.add_picture(str(chart_path),
                                         Inches(5), Inches(2),
                                         width=Inches(4.5))

        self._append_footer(prs, artifact, narrative.flagged_claims)
        out = output_dir / f"exec_brief_{artifact.artifact_id}.pptx"
        prs.save(out)
        return out

    def _apply_theme(self, prs: Presentation, theme: DesignTheme) -> None:
        # accent color 援먯껜, ?고듃 ?곸슜, 留덉뒪????댄? 而щ윭 ??        ...
```

### 6.3 ?붿옄???쒖뒪??
`DesignTheme` ? 議곗쭅蹂??뚮쭏瑜?異붿긽?뷀븳??

```python
class DesignTheme(BaseModel):
    theme_id: str
    primary_color: str        # e.g., "#86BC25" (Deloitte)
    secondary_color: str
    font_heading: str
    font_body: str
    chart_palette: list[str]
    logo_path: str | None = None
```

湲곕낯 ?뚮쭏 ??醫낆쓣 ?ы븿?쒕떎.

- `theme/default_v1` ???뚯궗 以묐┰.
- `theme/deloitte_v1` ??primary `#86BC25`, font "Open Sans".

議곗쭅蹂??뚮쭏??`assets/themes/<theme_id>/` ??JSON + ppt master + ?고듃濡????

### 6.4 李⑦듃 ?뚮뜑留?洹쒖튃

- matplotlib ?⑥씪 figure, ?⑥씪 axes. Sparkline / multi-panel 湲덉? (executive ?쒖젙).
- ?됱긽? `DesignTheme.chart_palette` ?먯꽌留?異붿텧.
- ?쒕ぉ? "臾댁뾿???쇰쭏?? ?뺥깭濡?媛뺤젣 (?? "Churn Q2 +3.1pp").
- 異??덉씠釉??고듃 14pt ?댁긽.

---

## 7. DeliveryRouter

### 7.1 ??븷

?섎굹??`DeliveryPack` ??artifact ?⑥쐞濡?遺꾪빐?섏뿬 **梨꾨꼸 ?대뙌??*?먭쾶 ?꾩엫?쒕떎. 湲곗〈 `runtime/outcome_delivery.py` 瑜??뺤옣?쒕떎.

```python
# src/infrastructure/delivery/delivery_router.py
class DeliveryRouter:
    def __init__(self, adapters: dict[DeliveryChannel, ChannelAdapter],
                 policy: DeliveryPolicyEngine,
                 log: DeliveryLog) -> None: ...

    def dispatch(self, pack: DeliveryPack) -> DeliveryResult:
        results = []
        for artifact in pack.artifacts:
            for channel in artifact.delivery_channel:
                if not self._policy.allow(pack, artifact, channel):
                    self._log.record_blocked(pack, artifact, channel)
                    continue
                adapter = self._adapters[channel]
                receipt = adapter.send(artifact, pack.global_context)
                self._log.record(receipt)
                results.append(receipt)
        return DeliveryResult(pack_id=pack.pack_id, receipts=results)
```

### 7.2 梨꾨꼸 ?대뙌??
| Channel | Adapter | ?뱀씠?ы빆 |
|---------|---------|----------|
| `email` | `SmtpEmailAdapter` | attachments 吏?? HTML body with summary |
| `slack_dm` | `SlackDmAdapter` | 300???붿빟 + 泥⑤?, ??곸? receivers.resolver |
| `slack_channel` | `SlackChannelAdapter` | thread 吏?? reactions ?섏쭛 ??feedback loop |
| `notion_page` | `NotionPageAdapter` | ?섏씠吏 ?앹꽦 ?먮뒗 ?낅뜲?댄듃 |
| `confluence` | `ConfluenceAdapter` | space_key, parent_page ?꾩슂 |
| `jira_ticket` | `JiraAdapter` | project_key, issue_type ?ㅼ젙 |
| `git_pr` | `GitPrAdapter` | repo / branch / reviewers |
| `compliance_system` | `ComplianceAdapter` | ?쒕챸??PDF 留??섏슜, rejection ???ъ떆??湲덉? |

媛??대뙌?곕뒗 `ChannelAdapter` port ?명꽣?섏씠?ㅻ? 援ы쁽?쒕떎.

```python
class ChannelAdapter(Protocol):
    def send(self, artifact: DeliveryArtifact,
             context: dict[str, str]) -> DeliveryReceipt: ...
```

### 7.3 ?ъ떆?꾩? idempotency

- 媛?`dispatch` ?쒕룄??`(pack_id, artifact_id, channel)` ?ㅻ줈 idempotency 蹂댁옣.
- ?ㅽ뙣 ??吏??backoff (理쒕? 5??, 5??珥덇낵 ??`delivery_log.status = failed_permanent`.
- `auditor` ??곸? ?ъ떆??湲덉? (以묐났 ?쒖텧 諛⑹?) ???⑥씪 ?쒕룄 ???ㅽ뙣 ???멸컙 媛쒖엯 ?붿껌.

---

## 8. Delivery Policy

### 8.1 policy_engine 怨쇱쓽 愿怨?
짠4 Autonomy Control Plane ??`AutonomyPolicyEngine` ??"??pack ??auto dispatch ?대룄 ?섎뒗媛" 瑜??먮떒?쒕떎.
DeliveryRouter ??梨꾨꼸蹂??몃? 洹쒖튃??`DeliveryPolicyEngine` ???꾩엫?쒕떎.

```python
class DeliveryPolicyEngine:
    def allow(self, pack: DeliveryPack,
              artifact: DeliveryArtifact,
              channel: DeliveryChannel) -> PolicyDecision: ...
```

### 8.2 delivery_policy_store ?ㅽ궎留?
```yaml
# config/delivery_policy.yaml
default:
  executive:
    allowed_channels: [email, slack_dm]
    max_recipients: 5
    require_approval: true
  auditor:
    allowed_channels: [compliance_system]
    require_signature: true
    require_approval: true
  ds_peer:
    allowed_channels: [git_pr, slack_channel]
    require_approval: false
  pm:
    allowed_channels: [slack_channel, notion_page, email]
    require_approval: false
  ml_engineer:
    allowed_channels: [confluence, jira_ticket]
    require_approval: false

tenant_overrides:
  acme_corp:
    executive:
      allowed_channels: [email]   # Slack 湲덉?
```

### 8.3 ?뺤콉 ?됯? ?쒖꽌

1. tenant override
2. project override (TaskContract ?덈꺼)
3. default
4. ?뺤콉 嫄곕? ??`delivery_log.status = blocked_by_policy` 湲곕줉 + ?멸컙 ?뱀씤 ?붿껌.

---

## 9. Clean Architecture 留ㅽ븨

| ?덉씠??| 而댄룷?뚰듃 | ?뚯씪 |
|--------|----------|------|
| Domain | `DeliveryPack`, `DeliveryArtifact`, `ContentPolicy`, `AudienceKind`, `DeliveryChannel` | `src/domain/entities/delivery_pack.py` |
| Domain | `NarrativeBlock`, `NarrativeBlocks`, `ChartSpec` | `src/domain/entities/narrative.py` |
| Domain | `DesignTheme` value object | `src/domain/value_objects/design_theme.py` |
| Domain | Port: `ChannelAdapter`, `LlmGateway`, `NarrativeVerifierPort`, `ChartRendererPort` | `src/domain/interfaces/` |
| Application | `AudienceRenderer` use case | `src/application/usecases/audience_renderer.py` |
| Application | `BuildDeliveryPack` use case | `src/application/usecases/build_delivery_pack.py` |
| Application | `DispatchDelivery` use case | `src/application/usecases/dispatch_delivery.py` |
| Application | DTOs: `RenderedArtifact`, `DeliveryReceipt`, `DeliveryResult` | `src/application/dtos/delivery.py` |
| Infrastructure | `PptxExporter`, `PdfExporter`, `IpynbExporter`, `MarkdownExporter` | `src/infrastructure/exporters/` |
| Infrastructure | `SmtpEmailAdapter`, `SlackDmAdapter`, `NotionPageAdapter`, ... | `src/infrastructure/delivery/` |
| Infrastructure | `DeliveryRouter` | `src/infrastructure/delivery/delivery_router.py` |
| Infrastructure | `TemplateRegistry`, `PptxMasterLoader`, `MatplotlibChartRenderer` | `src/infrastructure/rendering/` |
| Infrastructure | SQLite repo for delivery_packs | `src/infrastructure/persistence/delivery_pack_repo.py` |
| Presentation | Electron `AudienceSelector`, `DeliveryPackPreview` | `ui/components/workflow/` |
| Presentation | CLI `ds delivery ...` subcommand | `cli/commands/delivery.py` |

**Dependency Rule 泥댄겕**:
- `AudienceRenderer` ??`LlmGateway` Protocol ?먮쭔 ?섏〈 (?ㅼ젣 provider 紐⑤쫫).
- `PptxExporter` ??python-pptx 瑜?import ?대룄 ?섏?留? domain/application ?대뼡 ?뚯씪??pptx 瑜?import ?섏? ?딅뒗??
- `DeliveryPack` ? pydantic ???몃? ?섏〈??0.

---

## 10. 二쇱슂 ?꾧뎄 / ?좎뒪耳?댁뒪

### 10.1 `build_delivery_pack` (@tool)

```python
@tool
def build_delivery_pack(
    task_id: str,
    analysis_id: str,
    audiences: list[AudienceKind] | None = None,
    tenant: str = "default",
) -> DeliveryPackSummary:
    """
    TaskContract.required_deliverables ? policy 濡쒕???DeliveryPack 紐낆꽭瑜??앹꽦?쒕떎.
    ?ㅼ젣 ?뚮뜑留곸? ?섑뻾?섏? ?딅뒗??(紐낆꽭留?諛섑솚).
    """
```

### 10.2 `render_artifact` (@tool)

```python
@tool
def render_artifact(pack_id: str, artifact_id: str) -> RenderedArtifactSummary:
    """?⑥씪 artifact 瑜??뚮뜑留곹븳?? ?대??곸쑝濡?AudienceRenderer ?몄텧."""
```

### 10.3 `dispatch_delivery` (@tool)

```python
@tool
def dispatch_delivery(
    pack_id: str,
    channels: list[DeliveryChannel] | None = None,
    dry_run: bool = False,
) -> DeliveryResult:
    """DeliveryRouter 瑜??듯빐 dispatch. dry_run ?대㈃ policy check 源뚯?留??섑뻾."""
```

### 10.4 `AudienceRenderer` use case

- ?⑥씪 artifact ?뚮뜑留곸쓽 以묒떖.
- ?낅젰: analysis + audience profile + policy + template_ref.
- 異쒕젰: `RenderedArtifact` (bytes, blocks, verifier_report, chart_refs).

### 10.5 `PptxExporter` adapter

- format=pptx ??紐⑤뱺 artifact ??理쒖쥌 議곕┰.
- DesignTheme ?곸슜, master 濡쒕뱶, chart ?대?吏 ?쎌엯.

### 10.6 異붽? tool

| Tool | ?ㅻ챸 |
|------|------|
| `preview_delivery_pack` | ?뚮뜑留??놁씠 媛?artifact ??skeleton 怨??덉긽 ?섏씠吏 ??諛섑솚 |
| `approve_delivery` | manual_review ?곹깭 artifact 瑜??뱀씤 (human gate) |
| `revoke_delivery` | ?대? dispatch ??artifact 痍⑥냼 ?쒕룄 (梨꾨꼸蹂?吏???щ? ?ㅻ쫫) |
| `list_delivery_log` | ?뱀젙 task/pack ??dispatch ?대젰 議고쉶 |

---

## 11. SQLite ?ㅽ궎留?(migration v10)

### 11.1 ?뚯씠釉??뺤쓽

```sql
-- migrations/v10_delivery_pack.sql

CREATE TABLE delivery_packs (
    pack_id              TEXT PRIMARY KEY,
    task_id              TEXT NOT NULL,
    source_analysis_id   TEXT NOT NULL,
    generated_at         TEXT NOT NULL,
    confidence           REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    signed_by            TEXT NOT NULL,
    signature            TEXT,
    global_context_json  TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'draft'
                          CHECK (status IN ('draft','rendered','dispatched','rejected')),
    tenant               TEXT NOT NULL DEFAULT 'default',
    FOREIGN KEY (task_id) REFERENCES task_contracts(task_id)
);

CREATE INDEX idx_delivery_packs_task ON delivery_packs(task_id);
CREATE INDEX idx_delivery_packs_status ON delivery_packs(status);

CREATE TABLE delivery_artifacts (
    artifact_id          TEXT PRIMARY KEY,
    pack_id              TEXT NOT NULL,
    artifact_type        TEXT NOT NULL,
    audience             TEXT NOT NULL,
    format               TEXT NOT NULL,
    content_policy_json  TEXT NOT NULL,
    template_ref         TEXT NOT NULL,
    delivery_channels_json TEXT NOT NULL,
    dispatch_mode        TEXT NOT NULL,
    rendered_uri         TEXT,
    verifier_report_id   TEXT,
    render_status        TEXT NOT NULL DEFAULT 'pending'
                          CHECK (render_status IN ('pending','rendered','failed')),
    UNIQUE (pack_id, audience),
    FOREIGN KEY (pack_id) REFERENCES delivery_packs(pack_id) ON DELETE CASCADE
);

CREATE INDEX idx_delivery_artifacts_audience ON delivery_artifacts(audience);

CREATE TABLE delivery_log (
    log_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    pack_id              TEXT NOT NULL,
    artifact_id          TEXT NOT NULL,
    channel              TEXT NOT NULL,
    attempted_at         TEXT NOT NULL,
    status               TEXT NOT NULL
                          CHECK (status IN ('sent','failed_transient','failed_permanent',
                                            'blocked_by_policy','pending_approval')),
    receipt_ref          TEXT,
    error_message        TEXT,
    idempotency_key      TEXT NOT NULL UNIQUE,
    FOREIGN KEY (artifact_id) REFERENCES delivery_artifacts(artifact_id) ON DELETE CASCADE
);

CREATE INDEX idx_delivery_log_pack ON delivery_log(pack_id);
CREATE INDEX idx_delivery_log_status ON delivery_log(status);
```

### 11.2 酉?
```sql
CREATE VIEW v_delivery_summary AS
SELECT
    p.pack_id,
    p.task_id,
    p.status,
    COUNT(a.artifact_id) AS artifact_count,
    SUM(CASE WHEN a.render_status='rendered' THEN 1 ELSE 0 END) AS rendered_count,
    MAX(l.attempted_at) AS last_attempt
FROM delivery_packs p
LEFT JOIN delivery_artifacts a ON a.pack_id = p.pack_id
LEFT JOIN delivery_log l ON l.pack_id = p.pack_id
GROUP BY p.pack_id;
```

---

## 12. UX

### 12.1 Electron

- **AudienceSelector** (`components/workflow/AudienceSelector.tsx`)
  - 泥댄겕諛뺤뒪 由ъ뒪?? executive / pm / ds_peer / ml_engineer / auditor / junior_mentee.
  - 媛???ぉ ?놁뿉 ?덉긽 梨꾨꼸怨?遺꾨웾 誘몃━蹂닿린.
  - TaskContract.required_deliverables 湲곕컲 湲곕낯 ?좏깮.

- **DeliveryPackPreview** (`components/workflow/DeliveryPackPreview.tsx`)
  - ?? 媛?artifact ??format 蹂??꾨━酉?
  - pptx: ?щ씪?대뱶 ?몃꽕??媛ㅻ윭由?
  - markdown / ipynb: split view (skeleton vs ?뚮뜑 寃곌낵).
  - pdf: PDF.js 酉곗뼱.
  - ?곷떒??Verifier flag 諭껋? (怨쇱옣/?꾨씫/speculative).

- **ChannelInspector** ??媛?梨꾨꼸???덉긽 ?섏떊?먃룹젙梨?寃곌낵쨌?뱀씤 ?꾩슂 ?щ?瑜???以꾩뵫 蹂댁뿬以??

- **Dispatch CTA** ??`Send all` / `Send selected` / `Dispatch to sandbox`(?대? dry-run) ??媛?踰꾪듉.

### 12.2 CLI

```
ds delivery build    <task_id> --analysis <id> [--audiences exec,pm,ds]
ds delivery render   <pack_id> [--artifact <id>]
ds delivery preview  <pack_id> [--format pptx]
ds delivery dispatch <pack_id> [--channels email,slack_dm] [--dry-run]
ds delivery log      <pack_id>
ds delivery approve  <pack_id> <artifact_id>
```

紐⑤뱺 紐낅졊? `--json` ?뚮옒洹몃줈 湲곌퀎 ?먮룆 異쒕젰 ?쒓났.

---

## 13. ?쒗뵆由??먯궛 愿由?
### 13.1 ????꾩튂

```
assets/
?쒋?? templates/
??  ?쒋?? exec_brief/
??  ??  ?쒋?? v1.pptx
??  ??  ?쒋?? v2.pptx
??  ??  ?붴?? v3.pptx        # ?꾩옱
??  ?쒋?? pm_memo/
??  ??  ?붴?? v2.md
??  ?쒋?? ds_note/
??  ??  ?붴?? v4.ipynb
??  ?쒋?? ml_handoff/
??  ??  ?붴?? v2.md
??  ?붴?? audit/
??      ?붴?? v1.pdf.jinja
?붴?? themes/
    ?쒋?? default_v1/
    ??  ?쒋?? theme.json
    ??  ?붴?? fonts/
    ?붴?? deloitte_v1/
        ?쒋?? theme.json
        ?쒋?? master.pptx
        ?붴?? fonts/
```

### 13.2 踰꾩???洹쒖튃

- ?쒗뵆由우? 遺덈?. ?섏젙 ??諛섎뱶??`vN+1` 濡????뚯씪.
- `template_ref` ??`<family>/<version>` ?뺤떇 (?? `tpl/exec_brief/v3`).
- `TemplateRegistry` ??`assets/templates/registry.json` ?먯꽌 ?꾩옱 ?좏슚 踰꾩쟾 吏묓빀??愿由?
- deprecated ?쒗뵆由우? ??젣?섏? ?딄퀬 `registry.json` ??`deprecated: true` 濡??쒖떆.

### 13.3 ?뚮쭏 而ㅼ뒪?곕쭏?댁쫰

?뚮꼳?멸? ?먯껜 ?뚮쭏瑜?二쇱엯?섎젮硫?

1. `assets/themes/<tenant_id>_<n>/theme.json` 異붽?.
2. `config/tenant_overrides.yaml` ?먯꽌 `default_theme: <tenant_id>_<n>` ?좎뼵.
3. PptxExporter 媛 ?먮룞?쇰줈 ???뚮쭏 濡쒕뱶.

### 13.4 ?먯궛 寃利?
- CI ?먯꽌 紐⑤뱺 `.pptx` master ?뚯씪??python-pptx 濡??댁뼱 理쒖냼 ?щ씪?대뱶 ?샕톖ayout ??寃利?
- 紐⑤뱺 ?고듃 ?쇱씠?좎뒪 ?뚯씪 議댁옱 ?뺤씤.

---

## 14. TaskContract ???怨꾩빟

### 14.1 ?먮쫫

```
TaskContract (짠1)
    ?쒋? required_deliverables: [executive_pptx, pm_memo, ml_handoff, audit_pdf]
    ?쒋? stakeholders: [...]
    ?붴? deadline: ...
          ??BuildDeliveryPack use case
    ?쒋? required_deliverables ??DeliveryArtifact 珥덉븞
    ?쒋? stakeholders         ??DeliveryReceiver
    ?붴? deadline             ??dispatch ?ㅼ?以꾨쭅 hint
          ??DeliveryPack (draft)
          ??AudienceRenderer (per artifact)
          ??DeliveryPack (rendered)
          ??DeliveryRouter
          ??DeliveryPack (dispatched)  +  delivery_log
          ??TaskContract.status ??"delivered" (짠1 ??state machine)
```

### 14.2 留ㅽ븨 洹쒖튃

| TaskContract ?꾨뱶 | DeliveryPack ?꾨뱶 |
|-------------------|-------------------|
| `task_id` | `task_id` |
| `required_deliverables[i].type` | `artifacts[i].type` |
| `required_deliverables[i].audience` | `artifacts[i].audience` |
| `stakeholders[*]` | `artifacts[*].receivers` (role 留ㅼ묶) |
| `compliance_level` | `artifacts[?audience=auditor].content_policy.speculative_claims` |
| `sensitivity_level` | DeliveryPolicyEngine ?낅젰 |

### 14.3 ?쇨???寃利?
`BuildDeliveryPack` ? ?ㅼ쓬??蹂댁쬆?쒕떎.

1. `required_deliverables` ??紐⑤뱺 ??ぉ??pack ??議댁옱.
2. ??갑?? pack ?먮쭔 ?덇퀬 contract ???녿뒗 artifact ???먮윭.
3. stakeholder 以?留ㅼ묶?섏? ?딆? receiver ??寃쎄퀬.

---

## 15. 援ы쁽 Phases (TDD)

媛?phase ??Red ??Green ??Refactor ?쒖꽌. 紐⑤뱺 phase ??quality gate 瑜??듦낵?댁빞 ?쒕떎.

### Phase 1: 湲곗큹 (DeliveryPack + AudienceRenderer + PPTX)

**紐⑺몴**: exec_brief(pptx) / ds_experiment_note(ipynb) / pm_action_memo(markdown) 3醫낆쓣 ?뚮뜑留곹븯怨?濡쒖뺄 ?뚯씪濡???ν븳?? dispatch ???꾩쭅 ?놁쓬.

**RED**
- `tests/unit/domain/test_delivery_pack.py` ??DeliveryPack 遺덈??? 以묐났 audience 嫄곕?, auditor 媛뺤젣 ?뺤콉.
- `tests/unit/application/test_audience_renderer.py` ??LLM stub 二쇱엯, NarrativeBlocks ?뚯떛 ?ㅽ뙣 ???덉쇅.
- `tests/unit/infrastructure/test_pptx_exporter.py` ??master load, ?щ씪?대뱶 媛쒖닔, footer ?쎌엯 (python-pptx ?쎄린 寃利?.

**GREEN**
- domain 紐⑤뜽 + pydantic validator 援ы쁽.
- `AudienceRenderer` 援ы쁽 (LlmGateway Protocol, ChartRendererPort Protocol).
- `PptxExporter`, `IpynbExporter`, `MarkdownExporter` 理쒖냼 援ы쁽.
- `TemplateRegistry` ?뺤쟻 濡쒕뜑.

**REFACTOR**
- persona prompt ?곸닔??
- chart palette ?곸닔??

**Quality Gate**
- ?⑥쐞 ?뚯뒪??>= 90%.
- domain ?몃? ?섏〈??0.
- pptx / ipynb / md 媛곴컖 ?섑뵆 怨좎젙 ?낅젰 ??snapshot ?쇱튂.

---

### Phase 2: ?뺤옣 (蹂듭닔 梨꾨꼸 dispatch)

**紐⑺몴**: DeliveryRouter + 4媛?梨꾨꼸 ?대뙌??email, slack_dm, slack_channel, notion_page) + DeliveryPolicyEngine + delivery_log.

**RED**
- `tests/unit/infrastructure/test_delivery_router.py` ??policy block, 梨꾨꼸蹂?遺꾧린, idempotency key 異⑸룎.
- `tests/integration/test_delivery_roundtrip.py` ??媛??대뙌?곕? fake 濡?援ы쁽, pack ??dispatch ??log ?꾩껜 寃쎈줈.
- `tests/unit/infrastructure/test_delivery_policy.py` ??default / tenant override / project override ?곗꽑?쒖쐞.

**GREEN**
- `DeliveryRouter`, `DeliveryPolicyEngine` 援ы쁽.
- 4媛??대뙌???ㅼ젣 援ы쁽 + fake 援ы쁽 (?뚯뒪?몄슜).
- SQLite migration v10 ?곸슜.

**REFACTOR**
- ?ъ떆??濡쒖쭅 異붿텧 (`RetryPolicy`).
- ?대뙌??怨듯넻 ?먮윭 留ㅽ븨.

**Quality Gate**
- Integration test ?듦낵.
- idempotency key 異⑸룎 ??0嫄?以묐났 dispatch.
- auditor artifact ??????ъ떆???쒕룄 ???뺤콉 嫄곕? ?뺤씤.

---

### Phase 3: ?쒗뵆由?而ㅼ뒪?곕쭏?댁쫰 + ml_handoff + audit_trail

**紐⑺몴**: ml_handoff_spec (confluence + jira) / audit_trail (pdf + compliance_system) ?꾩껜 寃쎈줈 + ?뚮꼳???뚮쭏.

**RED**
- `tests/integration/test_audit_pipeline.py` ??speculative claim ?ы븿 analysis ??auditor artifact ?앹꽦 ?ㅽ뙣 ?뺤씤.
- `tests/integration/test_ml_handoff.py` ??confluence + jira ?숈떆 dispatch, ?묐갑??留곹겕.
- `tests/unit/infrastructure/test_theme_apply.py` ??deloitte_v1 濡쒕뵫, primary_color ?곸슜.

**GREEN**
- `PdfExporter` (audit?? readonly, ?고듃 ?꾨쿋??.
- `ConfluenceAdapter`, `JiraAdapter`, `ComplianceAdapter`.
- Theme 濡쒕뜑.
- Electron AudienceSelector / DeliveryPackPreview / ChannelInspector.
- CLI `ds delivery` subcommand.

**REFACTOR**
- Renderer ?대? ?뚯씠?꾨씪???④퀎 異붿텧.
- Dispatch ?ㅽ뙣 ???щ엺 媛쒖엯 ?뚮┝ 寃쎈줈 ?쇱썝??

**Quality Gate**
- E2E (fixture analysis ??5醫?artifact ??5梨꾨꼸 dry-run) ?깃났.
- auditor 媛뺤젣 ?쒕챸 寃利?
- UI snapshot test ?듦낵.

---

## 16. ?뚯뒪???꾨왂

### 16.1 怨꾩링蹂??꾨왂

| 怨꾩링 | ?뚯뒪???좏삎 | ?ъ씤??|
|------|-------------|--------|
| Domain | ?⑥쐞 | validator, immutability, 遺덈? 議곌굔 |
| Application | ?⑥쐞 (Fake LlmGateway / Fake Verifier) | ?꾨＼?꾪듃 議곕┰ ?뺥솗?? ?먮윭 寃쎈줈 |
| Infrastructure | ?⑥쐞 + ?듯빀 | python-pptx ?ㅼ젣 ?몄텧, ?몃? API ??fake |
| E2E | ?쒕굹由ъ삤 | TaskContract ??DeliveryPack ??dispatched ?꾩껜 寃쎈줈 |

### 16.2 ?ㅽ궎留?寃利?
- 紐⑤뱺 artifact ?뚮뜑留?寃곌낵??`RenderedArtifact` DTO 濡?利됱떆 ?뚯떛?섎ŉ, ?뚯떛 ?ㅽ뙣???뚯뒪???ㅽ뙣濡?媛꾩＜.
- pptx: `python-pptx` 濡??댁뼱 ?щ씪?대뱶 ?? layout, ?띿뒪??議댁옱 ?뺤씤.
- ipynb: `nbformat.validate` ?듦낵 ?뺤씤.
- pdf: PyPDF2 濡??띿뒪??異붿텧 ???꾩닔 ?뱀뀡 ?ㅼ썙??議댁옱.

### 16.3 Snapshot ?뚯뒪??
- 怨좎젙 遺꾩꽍 寃곌낵 + 怨좎젙 seed ???뚮뜑 寃곌낵瑜?snapshot ?쇰줈 ???(諛붿씠?덈━ 李⑥씠媛 ?꾨땶 **援ъ“ ?댁떆**).
- pptx: ?щ씪?대뱶蹂?`(title, body_text_hash, chart_count, footer_hash)` ?쒗뵆.
- markdown: ?뱀뀡 ?ㅻ뜑 ?쒖꽌 + 湲몄씠 泥댄겕??

### 16.4 ?뚭? 媛먯?: 怨쇱옣/?꾨씫

- `NarrativeVerifier` (짠3) ? ?곕룞. Renderer 異쒕젰? 諛섎뱶??Verifier 瑜??듦낵?댁빞 ?쒕떎.
- ?뚯뒪?몃뒗 "analysis ???녿뒗 二쇱옣??artifact 媛 ?ы븿" / "analysis ???덈뒗 以묐???caveat 瑜?artifact 媛 ?꾨씫" ???쒕굹由ъ삤瑜?fixture 濡?怨좎젙.
- auditor artifact ??speculative 二쇱옣???섎굹?쇰룄 ?ㅼ뼱媛硫??뚯뒪???ㅽ뙣.

### 16.5 遺???깅뒫

- exec_brief ?⑥씪 ?뚮뜑留?< 30珥?(LLM ?몄텧 ?ы븿, p95).
- 5媛?artifact 蹂묐젹 ?뚮뜑留?< 90珥?(p95).
- dispatch (5梨꾨꼸) < 10珥?

### 16.6 蹂댁븞

- ?대뙌??fake ???ㅼ젣 ?먭꺽利앸챸 ?묎렐 遺덇?.
- delivery_log ??誘쇨컧?뺣낫 ?곗씠?붿? ?뚭? ?뚯뒪??

---

## 17. ?섏〈??諛??듯빀 吏??
### 17.1 ?몃? ?쇱씠釉뚮윭由?
| ?쇱씠釉뚮윭由?| ?⑸룄 | 怨꾩링 |
|-----------|------|------|
| `python-pptx` | PPTX ?앹꽦 | infrastructure |
| `matplotlib` | 李⑦듃 ?뚮뜑留?| infrastructure |
| `reportlab` | PDF (audit) | infrastructure |
| `nbformat` | ipynb ?앹꽦 | infrastructure |
| `slack_sdk` | Slack ?대뙌??| infrastructure |
| `notion-client` | Notion ?대뙌??| infrastructure |
| `atlassian-python-api` | Confluence / Jira | infrastructure |
| `pydantic >= 2` | domain 紐⑤뜽 | domain |

### 17.2 ?대? ?듯빀 吏??
| ?ㅽ럺 | ?듯빀 ?댁슜 |
|------|-----------|
| 01 TaskContract | `required_deliverables` ??pack ?앹꽦, ?꾨즺 ??contract status ?꾩씠 |
| 02 Semantic Memory | `lineage_id` 李몄“, audit_trail.lineage ?뱀뀡 ?뚯뒪 |
| 03 Verifier Orchestrator | 紐⑤뱺 artifact ???뚮뜑 吏곹썑 Verifier ?듦낵 ?꾩닔 |
| 04 Autonomy Control Plane | AudiencePersona ?ъ궗?? PolicyEngine ?뱀씤 |
| 05 Evaluation Harness | dispatch ?깃났瑜?/ ?섏떊???쇰뱶諛??섏쭛 |

### 17.3 ?ㅼ젙

- `config/delivery_policy.yaml` ???뺤콉.
- `config/channels.yaml` ??梨꾨꼸 ?먭꺽利앸챸 ?덊띁?곗뒪 (鍮꾨?? vault).
- `config/themes.yaml` ???뚮꼳?몃퀎 湲곕낯 ?뚮쭏.

---

## 18. ?깃났 湲곗? (DoD)

1. ?섎굹??`FinalAnalysis` 濡쒕???5醫?audience artifact 媛 媛??щ㎎?쇰줈 ?뚮뜑留곷맂??
2. exec_brief pptx ??`theme_id` 瑜?諛붽씀硫??됱긽쨌?고듃媛 利됱떆 諛섏쁺?쒕떎.
3. auditor artifact ??speculative claim ??諛쒓껄?섎㈃ pack ?곹깭媛 `rejected` 濡??꾩씠?섍퀬 dispatch ?섏? ?딅뒗??
4. DeliveryRouter ???숈씪 (pack, artifact, channel) 議고빀????踰?dispatch ?섏? ?딅뒗??(idempotency).
5. TaskContract.required_deliverables ???좎뼵??紐⑤뱺 artifact 媛 pack ??議댁옱?섏? ?딆쑝硫?`BuildDeliveryPack` ???ㅽ뙣?쒕떎.
6. ?⑥쐞 + ?듯빀 ?뚯뒪??而ㅻ쾭由ъ? domain ??95%, application ??90%, infrastructure ??75%.
7. CLI `ds delivery dispatch --dry-run` ??紐⑤뱺 ?뺤콉 ?먯젙??JSON ?쇰줈 異쒕젰?쒕떎.
8. Electron AudienceSelector ?먯꽌 audience 瑜?蹂寃쏀븯硫??숈씪 analysis 濡??щ젋?붾쭅?섎ŉ, ?댁쟾 pack ? ??pack_id 濡?踰꾩쟾?낅맂??
9. Verifier ?뚭? ?뚯뒪???명듃(怨쇱옣/?꾨씫 fixture) 20嫄댁씠 紐⑤몢 ?먯??쒕떎.

---

## 19. 由ъ뒪??諛?濡ㅻ갚

### 19.1 由ъ뒪??
| 由ъ뒪??| ?뺣쪧 | ?곹뼢 | ?꾪솕 |
|--------|------|------|------|
| LLM ??persona 吏?쒕? 臾댁떆?섍퀬 以묐┰ ?띿뒪??諛섑솚 | 以?| 以?| structured output schema 媛뺤젣 + Verifier ?ш?利?|
| python-pptx 媛 蹂듭옟??master ?덉씠?꾩썐 ?먯긽 | 以?| 以?| master ?붿씠?몃━?ㅽ듃, CI ?먯꽌 golden master 鍮꾧탳 |
| 議곗쭅 ?뚮쭏 ?고듃 ?쇱씠?좎뒪 ?꾨컲 | ??| ??| ?고듃 ?쇱씠?좎뒪 ?깅줉 泥댄겕由ъ뒪?? CI 寃利?|
| 梨꾨꼸 ?대뙌???μ븷濡?dispatch ?꾨씫 | 以?| ??| ?ъ떆??+ ?곴뎄 ?ㅽ뙣 ???멸컙 ?뚮┝ |
| auditor ??PDF 媛 ?몄쭛 媛???곹깭濡??좎텧 | ??| 留ㅼ슦 ??| readonly ?뚮옒洹?+ signature, e2e ?뚯뒪??怨좎젙 |
| executive pptx 媛 李⑦듃 怨쇰??섎줈 3??珥덇낵 | 以?| 以?| content_policy validator + Verifier ??length_guard |
| speculative claim ??exec ?⑹뿉???덉슜?섏뼱 ?먮떒 ?쒓끝 | 以?| 以?| flagged ?뺤콉 ??footer 寃쎄퀬 媛뺤젣, UI 諭껋? |
| Slack/Notion API rate limit | 以?| ??| 梨꾨꼸蹂??좏겙 踰꾪궥 |

### 19.2 濡ㅻ갚 ?꾨왂

| Phase | 濡ㅻ갚 諛⑸쾿 |
|-------|-----------|
| Phase 1 | ???뚯씪留?異붽? ???뚯씪 ??젣 + migration v10 誘몄쟻????臾몄젣?놁쓬 |
| Phase 2 | DeliveryRouter 湲곕낯 dispatch 鍮꾪솢???뚮옒洹?`delivery.router.enabled=false` 濡?利됱떆 李⑤떒 |
| Phase 3 | ?뚮꼳???뚮쭏 二쇱엯 ?ㅽ뙣 ??default ?뚮쭏 fallback, ???대뙌?곕뒗 feature flag 濡?off |

- SQLite migration ? backward-compatible (?좉퇋 ?뚯씠釉붾쭔 異붽?).
- DeliveryPack ????뚮뜑??Router ? ?낅┰?대?濡? ?μ븷 ???뚮뜑留??좎??섍퀬 dispatch ??off 媛??

---

## 20. Open Questions

1. **Slide ?댁꽕(narration) ?ㅽ겕由쏀듃**瑜?pptx ? ?④퍡 ?앹꽦?댁빞 ?섎뒗媛? (?뚯쓽?먯꽌 ?쎌쓣 ???덈뒗 留먰뭾???띿뒪??
2. **?ㅺ뎅??吏??* ???????숈떆 ?뚮뜑留곸쓣 ?숈씪 pack ??duplicate artifact 濡?泥섎━?좎?, `locale` ?띿꽦?쇰줈 ?⑥씪 artifact 濡?泥섎━?좎?.
3. **?멸컙 ?몄쭛 猷⑦봽** ???뚮뜑 ???щ엺???섏젙??寃곌낵瑜??ㅼ떆 pack ????뼱??寃껋씤媛, ?꾨땲硫?"human_override_uri" 濡쒕쭔 異붿쟻??寃껋씤媛.
4. **?섏떊??諛섏쓳 ?섏쭛** (Slack ?대え吏, ?대찓???대엺) ??짠5 Evaluation Harness ?쇰뱶諛??좏샇濡??먮룞 二쇱엯??寃껋씤媛.
5. **compliance_system ??諛섎젮 ?꾨줈?좎퐳** ??媛먯궗 履쎌뿉??諛섎젮??artifact 瑜??ъ젣異쒗븷 ?? ??pack ??留뚮뱾?댁빞 ?섎뒗吏 湲곗〈 pack ??mutable 濡??꾪솚?좎?.
6. **李⑦듃 ?묎렐??* ???됰㏏ ?붾젅??/ ALT text ?먮룞 ?앹꽦??紐⑤뱺 audience ??媛뺤젣?좎?, executive ?먮쭔 媛뺤젣?좎?.
7. **Template DSL** ??pptx master ?몄뿉 markdown skeleton ?쒗뵆由우쓣 Jinja 濡??몄?, ?꾩슜 DSL 濡??몄?.
8. **紐⑤컮???꾨━酉?* ??Electron ??紐⑤컮?쇱뿉??exec_brief 瑜??붿빟 移대뱶濡?異뺤빟 ?뚮뜑留곹븷吏.
9. **鍮꾩슜 ?쒖뼱** ??LLM ?몄텧??audience ??1?뚮줈 ?쒗븳?좎?, ?뱀뀡蹂꾨줈 ?몄텧?좎? (?덉쭏 vs 鍮꾩슜 trade-off).
10. **踰꾩쟾 異⑸룎** ???숈씪 task ??????쒕줈 ?ㅻⅨ audience 媛 ?쒕줈 ?ㅻⅨ ?쒖젏??analysis ?ㅻ깄?룹쓣 李몄“?????덇쾶 ?덉슜?좎?.

---

**End of Spec 07 ??Stakeholder Communication Engine**
