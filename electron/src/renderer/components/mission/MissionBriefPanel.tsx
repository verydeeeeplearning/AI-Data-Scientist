import { useEffect, useMemo, useState } from 'react';
import { AssumptionDrawer } from './AssumptionDrawer';
import { ContractEditor } from './ContractEditor';
import { CreateContractModal } from './CreateContractModal';
import {
  buildDeliveryGlobalContext,
  formatRenderResultNotice,
  normalizeDeliveryTenant,
  parseMissionArtifactGate,
  parseMissionArtifactGateError,
  parseMissionCheckGate,
  parseMissionCheckGateError,
  parseMissionChannelGate,
  parseMissionChannelGateError,
  resolveProviderBackedRenderOptions,
  resolveThemeId,
  type MissionArtifactGateStatus,
  type MissionCheckGateStatus,
  type MissionChannelGateStatus,
} from './missionBriefModel';
import { useTaskContract } from '../../hooks/useTaskContract';
import { useChatStore } from '../../stores/chatStore';
import { AudienceSelector, type AudienceSelectionOption } from '../workflow/AudienceSelector';
import { ChannelInspector } from '../workflow/ChannelInspector';
import { DeliveryPackPreview } from '../workflow/DeliveryPackPreview';
import type {
  DeliveryArtifactView,
  TaskContractErrorDetailView,
  TaskContractCreatePayload,
  TaskContractStatus,
  TaskContractView,
} from '../../types/taskContract';

const STATUS_STYLES: Record<TaskContractStatus, string> = {
  draft: 'bg-sky-500/15 text-sky-300 border-sky-500/40',
  agreed: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/40',
  in_progress: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
  review: 'bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/40',
  closed: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
  abandoned: 'bg-rose-500/15 text-rose-300 border-rose-500/40',
};

function defaultAnalysisDraft(contract: TaskContractView): string {
  return JSON.stringify(
    {
      summary: contract.contract.business_goal,
      decision: contract.goal_brief?.decision_to_make ?? 'State the decision needed.',
      recommendation: 'State the recommended action and expected impact.',
      next_actions: [],
    },
    null,
    2,
  );
}

function parseAnalysisDraft(value: string): Record<string, unknown> | string {
  const trimmed = value.trim();
  if (!trimmed) {
    return { summary: 'No analysis summary provided.' };
  }

  try {
    const parsed = JSON.parse(trimmed);
    if (parsed && typeof parsed === 'object') {
      return parsed as Record<string, unknown>;
    }
  } catch {
    return value;
  }

  return value;
}

function buildAudienceOptions(contract: TaskContractView): AudienceSelectionOption[] {
  const grouped = new Map<
    string,
    { deliverableTypes: Set<string>; formats: Set<string>; artifact?: DeliveryArtifactView | null }
  >();

  for (const deliverable of contract.contract.required_deliverables) {
    const current = grouped.get(deliverable.audience) ?? {
      deliverableTypes: new Set<string>(),
      formats: new Set<string>(),
      artifact: contract.delivery_pack?.artifacts.find(
        (artifact) => artifact.audience === deliverable.audience,
      ) ?? null,
    };
    current.deliverableTypes.add(deliverable.type);
    current.formats.add(deliverable.format);
    grouped.set(deliverable.audience, current);
  }

  return Array.from(grouped.entries()).map(([audience, value]) => ({
    audience,
    selected: false,
    deliverableTypes: Array.from(value.deliverableTypes),
    formats: Array.from(value.formats),
    artifact: value.artifact,
  }));
}

export function MissionBriefPanel() {
  const {
    sessionId,
    activeContract,
    loading,
    error,
    deliveryLog,
    deliveryLogLoading,
    deliveryLogError,
    refresh,
    refreshDeliveryLog,
    transition,
    createContract,
    savePatch,
    closeContract,
    verifyAssumption,
    buildDeliveryPack,
    renderArtifact,
    dispatchDelivery,
  } = useTaskContract();
  const latestUserGoalSeed = useChatStore((state) => {
    for (let index = state.messages.length - 1; index >= 0; index -= 1) {
      if (state.messages[index]?.role === 'user') {
        return state.messages[index]?.content ?? '';
      }
    }
    return '';
  });

  const [editorOpen, setEditorOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [closeDialogOpen, setCloseDialogOpen] = useState(false);
  const [closeNote, setCloseNote] = useState('Delivered to stakeholders');
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionErrorDetail, setActionErrorDetail] = useState<TaskContractErrorDetailView | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [selectedAudiences, setSelectedAudiences] = useState<string[]>([]);
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [sourceAnalysisId, setSourceAnalysisId] = useState('');
  const [tenant, setTenant] = useState('default');
  const [themeId, setThemeId] = useState('');
  const [analysisDraft, setAnalysisDraft] = useState('');
  const [providerBackedRender, setProviderBackedRender] = useState(false);
  const [renderModel, setRenderModel] = useState('');

  const openAssumptions = useMemo(
    () => activeContract?.assumption_log?.entries.filter((entry) => !entry.verified) ?? [],
    [activeContract],
  );
  const missionArtifactGate = useMemo(
    () => parseMissionArtifactGate(activeContract?.dod_summary ?? []),
    [activeContract?.dod_summary],
  );
  const actionMissionArtifactGate = useMemo(
    () => parseMissionArtifactGateError(actionErrorDetail),
    [actionErrorDetail],
  );
  const missionArtifactGateTone = useMemo(
    () => (missionArtifactGate ? getMissionArtifactGateTone(missionArtifactGate) : null),
    [missionArtifactGate],
  );
  const actionMissionArtifactGateTone = useMemo(
    () => (actionMissionArtifactGate ? getMissionArtifactGateTone(actionMissionArtifactGate) : null),
    [actionMissionArtifactGate],
  );

  // Check gate from DoD summary
  const missionCheckGate = useMemo(
    () => parseMissionCheckGate(activeContract?.dod_summary ?? []),
    [activeContract?.dod_summary],
  );
  // Check gate from action error detail
  const actionMissionCheckGate = useMemo(
    () => parseMissionCheckGateError(actionErrorDetail),
    [actionErrorDetail],
  );

  // Channel gate from DoD summary
  const missionChannelGate = useMemo(
    () => parseMissionChannelGate(activeContract?.dod_summary ?? []),
    [activeContract?.dod_summary],
  );
  // Channel gate from action error detail
  const actionMissionChannelGate = useMemo(
    () => parseMissionChannelGateError(actionErrorDetail),
    [actionErrorDetail],
  );

  const audienceOptions = useMemo(() => {
    if (!activeContract) {
      return [];
    }

    const selected = new Set(selectedAudiences);
    return buildAudienceOptions(activeContract).map((option) => ({
      ...option,
      selected: selected.has(option.audience),
    }));
  }, [activeContract, selectedAudiences]);

  const selectedArtifact = useMemo(
    () =>
      activeContract?.delivery_pack?.artifacts.find(
        (artifact) => artifact.artifact_id === selectedArtifactId,
      )
      ?? activeContract?.delivery_pack?.artifacts[0]
      ?? null,
    [activeContract, selectedArtifactId],
  );

  const hasDeliveryPack = Boolean(activeContract?.delivery_pack);
  const deliveryRecordCount = deliveryLog?.returned ?? 0;

  useEffect(() => {
    if (!activeContract) {
      setSelectedAudiences([]);
      setSelectedArtifactId(null);
      setSourceAnalysisId('');
      setTenant('default');
      setThemeId('');
      setAnalysisDraft('');
      setProviderBackedRender(false);
      setRenderModel('');
      return;
    }

    setSelectedAudiences(
      Array.from(new Set(activeContract.contract.required_deliverables.map((item) => item.audience))),
    );
    setSelectedArtifactId(activeContract.delivery_pack?.artifacts[0]?.artifact_id ?? null);
    setSourceAnalysisId(activeContract.delivery_pack?.source_analysis_id ?? '');
    setTenant(normalizeDeliveryTenant(activeContract.delivery_pack?.tenant));
    setThemeId(resolveThemeId(activeContract.delivery_pack?.global_context));
    setAnalysisDraft(defaultAnalysisDraft(activeContract));
    setProviderBackedRender(false);
    setRenderModel('');
  }, [activeContract?.contract.task_id]);

  useEffect(() => {
    if (!activeContract?.delivery_pack?.artifacts.length) {
      setSelectedArtifactId(null);
      return;
    }

    if (
      selectedArtifactId
      && activeContract.delivery_pack.artifacts.some(
        (artifact) => artifact.artifact_id === selectedArtifactId,
      )
    ) {
      return;
    }

    setSelectedArtifactId(activeContract.delivery_pack.artifacts[0].artifact_id);
  }, [activeContract?.delivery_pack?.artifacts, selectedArtifactId]);

  useEffect(() => {
    if (activeContract?.contract.task_id) {
      setCreateDialogOpen(false);
    }
  }, [activeContract?.contract.task_id]);

  const runAction = async (fn: () => Promise<void>) => {
    setBusy(true);
    setActionError(null);
    setActionErrorDetail(null);
    setActionNotice(null);
    try {
      await fn();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
      setActionErrorDetail(readTaskContractErrorDetail(err));
    } finally {
      setBusy(false);
    }
  };

  const handleTransition = async (nextStatus: TaskContractStatus) => {
    const label = {
      agreed: 'operator agreed contract',
      in_progress: 'operator moved contract to in progress',
      review: 'operator moved contract to review',
      abandoned: 'operator abandoned contract',
      closed: 'operator closed contract',
      draft: 'operator reset contract to draft',
    }[nextStatus];

    if (nextStatus === 'closed') {
      setCloseNote('Delivered to stakeholders');
      setCloseDialogOpen(true);
      return;
    }

    await runAction(async () => transition(nextStatus, label));
  };

  const toggleAudience = (audience: string) => {
    setSelectedAudiences((current) =>
      current.includes(audience)
        ? current.filter((item) => item !== audience)
        : [...current, audience],
    );
  };

  const handleBuildDeliveryPack = async () => {
    if (selectedAudiences.length === 0) {
      setActionError('Select at least one audience before building a delivery pack.');
      return;
    }

    await runAction(async () => {
      const result = await buildDeliveryPack({
        audiences: selectedAudiences,
        sourceAnalysisId: sourceAnalysisId.trim() || undefined,
        globalContext: buildDeliveryGlobalContext(
          activeContract?.delivery_pack?.global_context,
          themeId,
        ),
        tenant: normalizeDeliveryTenant(tenant),
      });
      setSelectedArtifactId(result.artifact_ids[0] ?? null);
      const normalizedThemeId = themeId.trim();
      setActionNotice(
        `Delivery pack ${result.pack_id} prepared for ${result.audiences.join(', ')}`
          + ` (tenant: ${normalizeDeliveryTenant(tenant)}`
          + `${normalizedThemeId ? `, theme: ${normalizedThemeId}` : ''}).`,
      );
    });
  };

  const handleConfirmClose = async () => {
    const note = closeNote.trim();
    if (!note) {
      setActionError('Closing note is required.');
      return;
    }

    await runAction(async () => {
      await closeContract(note);
      setCloseDialogOpen(false);
      setActionNotice('Task contract closed.');
    });
  };

  const handleVerifyAssumption = async (entryId: string, verificationNote?: string) => {
    await runAction(async () => {
      await verifyAssumption({ entryId, verificationNote });
      setActionNotice(`Assumption ${entryId} marked as verified.`);
    });
  };

  const handleRenderSelectedArtifact = async () => {
    if (!selectedArtifact) {
      setActionError('Select one artifact before rendering.');
      return;
    }

    await runAction(async () => {
      const renderOptions = resolveProviderBackedRenderOptions(
        providerBackedRender,
        renderModel,
      );
      const result = await renderArtifact({
        artifactId: selectedArtifact.artifact_id,
        analysis: parseAnalysisDraft(analysisDraft),
        providerBacked: renderOptions.providerBacked,
        model: renderOptions.model,
      });
      setSelectedArtifactId(result.artifact_id);
      setActionNotice(formatRenderResultNotice(result));
      await refreshDeliveryLog({ artifactIds: [result.artifact_id], limit: 20 });
    });
  };

  const handleDispatchSelected = async (dryRun: boolean) => {
    if (!selectedArtifact) {
      setActionError('Select one artifact before dispatching.');
      return;
    }

    await runAction(async () => {
      const result = await dispatchDelivery({
        artifactIds: [selectedArtifact.artifact_id],
        dryRun,
        approveManualReview: !dryRun,
      });
      setActionNotice(
        `${dryRun ? 'Dry run' : 'Dispatch'} ${result.dispatch_status} `
          + `(sent=${result.sent}, blocked=${result.blocked}).`,
      );
      await refreshDeliveryLog({ artifactIds: [selectedArtifact.artifact_id], limit: 20 });
    });
  };

  const handleDispatchPack = async (dryRun: boolean) => {
    await runAction(async () => {
      const result = await dispatchDelivery({
        dryRun,
        approveManualReview: !dryRun,
      });
      setActionNotice(
        `${dryRun ? 'Dry run' : 'Pack dispatch'} ${result.dispatch_status} `
          + `(sent=${result.sent}, blocked=${result.blocked}).`,
      );
      await refreshDeliveryLog({ limit: 20 });
    });
  };

  const handleRevealPath = async (targetPath: string) => {
    if (!window.electronAPI?.revealPath) {
      setActionError('Path reveal is unavailable.');
      return;
    }

    const result = await window.electronAPI.revealPath(targetPath);
    if (!result.ok) {
      setActionError(result.error ?? `Unable to reveal ${targetPath}`);
    }
  };

  const handleCreateContract = async (payload: TaskContractCreatePayload) => {
    await runAction(async () => {
      const result = await createContract(payload);
      setCreateDialogOpen(false);
      setActionNotice(`Task contract ${result.task_id} drafted for this session.`);
    });
  };

  if (!sessionId) {
    return (
      <section className="mx-3 rounded-2xl border border-ds-border bg-ds-bg px-4 py-3">
        <h3 className="text-sm font-semibold text-ds-text">Mission Brief</h3>
        <p className="mt-2 text-xs leading-5 text-ds-muted">
          Start a chat turn first. The active session will attach the current task contract here.
        </p>
      </section>
    );
  }

  return (
    <>
      <section
        className="mx-3 rounded-2xl border border-ds-border bg-ds-bg px-4 py-4"
        data-testid="mission-brief-panel"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-ds-text">Mission Brief</h3>
            <p className="mt-1 text-[11px] text-ds-muted">Session: {sessionId}</p>
          </div>
          <button
            onClick={() => void refresh()}
            className="rounded-lg border border-ds-border px-3 py-1.5 text-[11px] text-ds-muted hover:border-ds-accent hover:text-ds-text"
          >
            Refresh
          </button>
        </div>

        {loading && <p className="mt-3 text-xs text-ds-muted">Loading task contract...</p>}

        {!loading && !activeContract && (
          <div className="mt-3 rounded-2xl border border-dashed border-ds-border bg-ds-surface px-4 py-4">
            <p className="text-sm font-medium text-ds-text">
              No active task contract for this session yet.
            </p>
            <p className="mt-2 text-xs leading-5 text-ds-muted">
              Draft a manual recovery contract for the current session, then edit the details from the mission panel.
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={() => setCreateDialogOpen(true)}
              data-testid="mission-brief-create-contract-cta"
              className="mt-3 rounded-xl bg-ds-accent px-3 py-2 text-xs font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              Draft Contract
            </button>
          </div>
        )}

        {error && (
          <div className="mt-3 rounded-xl border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
            {error}
          </div>
        )}

        {actionError && (
          <div
            className="mt-3 rounded-xl border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200"
            data-testid="mission-brief-action-error"
          >
            {actionError}
          </div>
        )}

        {actionMissionArtifactGate && actionMissionArtifactGateTone && (
          <div
            className={`mt-3 rounded-2xl border px-4 py-3 ${MISSION_ARTIFACT_GATE_STYLES[actionMissionArtifactGateTone]}`}
            data-testid="mission-brief-action-gate-detail"
          >
            <p className="text-xs uppercase tracking-wide text-ds-muted">
              Blocked Transition
            </p>
            <p className="mt-1 text-sm font-semibold text-ds-text">
              {formatMissionArtifactGateHeading(actionMissionArtifactGate.transitionTarget)}
            </p>
            {actionMissionArtifactGate.requiredArtifacts.length > 0 && (
              <p className="mt-2 text-xs leading-5 text-ds-text/90">
                Required: {actionMissionArtifactGate.requiredArtifacts.join(', ')}
              </p>
            )}
            <div className="mt-3 space-y-2">
              {actionMissionArtifactGate.issues.map((issue) => (
                <div
                  key={`${issue.kind}-${issue.artifacts.join('-') || 'none'}`}
                  className="rounded-xl border border-current/15 bg-black/10 px-3 py-2 text-xs leading-5 text-current"
                >
                  <span className="font-medium">{issue.label}</span>
                  {issue.artifacts.length > 0 ? `: ${issue.artifacts.join(', ')}` : null}
                </div>
              ))}
            </div>
          </div>
        )}

        {actionMissionCheckGate
          && (actionMissionCheckGate.failed.length > 0 || actionMissionCheckGate.unmapped.length > 0) && (
          <MissionCheckGatePanel
            gate={actionMissionCheckGate}
            label="Blocked — Required Checks Failed"
            testId="mission-brief-action-check-gate-detail"
          />
        )}

        {actionMissionChannelGate && actionMissionChannelGate.missing.length > 0 && (
          <MissionChannelGatePanel
            gate={actionMissionChannelGate}
            label="Blocked — Required Channels Not Delivered"
            testId="mission-brief-action-channel-gate-detail"
          />
        )}

        {actionNotice && (
          <div
            className="mt-3 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200"
            data-testid="mission-brief-action-notice"
          >
            {actionNotice}
          </div>
        )}

        {activeContract && (
          <>
            <div className="mt-4 flex items-center gap-2">
              <span className="text-xs font-medium text-ds-muted">{activeContract.contract.task_id}</span>
              <span
                data-testid="mission-brief-status-badge"
                className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${
                  STATUS_STYLES[activeContract.contract.status]
                }`}
              >
                {activeContract.contract.status}
              </span>
              <span className="text-[11px] text-ds-muted">v{activeContract.contract.version}</span>
            </div>

            {(activeContract.contract.authority || activeContract.contract.audience) && (
              <div className="mt-3 flex flex-wrap gap-2">
                {activeContract.contract.authority && (
                  <span
                    className="rounded-full border border-ds-border bg-ds-surface px-2 py-1 text-[11px] text-ds-text"
                    data-testid="mission-brief-authority"
                  >
                    Authority: {activeContract.contract.authority}
                  </span>
                )}
                {activeContract.contract.audience && (
                  <span
                    className="rounded-full border border-ds-border bg-ds-surface px-2 py-1 text-[11px] text-ds-text"
                    data-testid="mission-brief-audience"
                  >
                    Audience: {activeContract.contract.audience}
                  </span>
                )}
              </div>
            )}

            <p className="mt-3 text-sm font-medium leading-6 text-ds-text">
              <span data-testid="mission-brief-business-goal">
              {activeContract.contract.business_goal}
              </span>
            </p>

            {activeContract.goal_brief && (
              <div className="mt-3 rounded-xl border border-ds-border bg-ds-surface px-3 py-3">
                <p className="text-[11px] uppercase tracking-wide text-ds-muted">Decision</p>
                <p className="mt-1 text-sm text-ds-text">
                  {activeContract.goal_brief.decision_to_make}
                </p>
              </div>
            )}

            {activeContract.contract.decision_owner && (
              <div className="mt-3 rounded-xl border border-ds-border bg-ds-surface px-3 py-3">
                <p className="text-[11px] uppercase tracking-wide text-ds-muted">Owner</p>
                <p
                  className="mt-1 text-sm text-ds-text"
                  data-testid="mission-brief-decision-owner"
                >
                  {activeContract.contract.decision_owner}
                </p>
              </div>
            )}

            <div className="mt-3 grid gap-2">
              {activeContract.contract.required_deliverables.map((item, index) => (
                <div
                  key={`${item.type}-${index}`}
                  className="rounded-xl border border-ds-border px-3 py-2 text-xs text-ds-muted"
                >
                  <span className="font-medium text-ds-text">{item.type}</span>
                  {` -> ${item.audience} (${item.format})`}
                </div>
              ))}
            </div>

            {missionArtifactGate && missionArtifactGateTone && (
              <div
                className={`mt-4 rounded-2xl border px-4 py-3 ${MISSION_ARTIFACT_GATE_STYLES[missionArtifactGateTone]}`}
                data-testid="mission-artifact-gate-panel"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-ds-muted">
                      Mission Artifact Gate
                    </p>
                    <p
                      className="mt-1 text-sm font-semibold text-ds-text"
                      data-testid="mission-artifact-gate-status"
                    >
                      {missionArtifactGate.ready ? 'Ready' : 'Unmet'}
                    </p>
                  </div>
                  {missionArtifactGate.missionName && (
                    <span className="rounded-full border border-current/20 px-2 py-1 text-[11px] font-medium text-inherit">
                      {missionArtifactGate.missionName}
                    </span>
                  )}
                </div>

                {missionArtifactGate.requiredArtifacts.length > 0 && (
                  <p className="mt-2 text-xs leading-5 text-ds-text/90">
                    Required: {missionArtifactGate.requiredArtifacts.join(', ')}
                  </p>
                )}

                {missionArtifactGate.issues.length > 0 ? (
                  <div className="mt-3 space-y-2">
                    {missionArtifactGate.issues.map((issue) => (
                      <div
                        key={`${issue.kind}-${issue.artifacts.join('-') || 'none'}`}
                        className="rounded-xl border border-current/15 bg-black/10 px-3 py-2 text-xs leading-5 text-current"
                      >
                        <span className="font-medium">{issue.label}</span>
                        {issue.artifacts.length > 0 ? `: ${issue.artifacts.join(', ')}` : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 text-xs leading-5 text-ds-text/90">
                    All mapped mission artifacts are declared and delivered.
                  </p>
                )}
              </div>
            )}

            {missionCheckGate
              && (missionCheckGate.failed.length > 0 || missionCheckGate.unmapped.length > 0) && (
              <MissionCheckGatePanel
                gate={missionCheckGate}
                label="Mission Check Gate"
                testId="mission-check-gate-panel"
              />
            )}

            {missionChannelGate && missionChannelGate.missing.length > 0 && (
              <MissionChannelGatePanel
                gate={missionChannelGate}
                label="Mission Channel Gate"
                testId="mission-channel-gate-panel"
              />
            )}

            <div className="mt-3 flex flex-wrap gap-2">
              {activeContract.contract.status === 'draft' && (
                <button
                  disabled={busy}
                  onClick={() => void handleTransition('agreed')}
                  data-testid="mission-brief-action-agree"
                  className="rounded-xl bg-ds-accent px-3 py-2 text-xs font-medium text-white disabled:opacity-60"
                >
                  Agree
                </button>
              )}
              {activeContract.contract.status === 'agreed' && (
                <button
                  disabled={busy}
                  onClick={() => void handleTransition('in_progress')}
                  data-testid="mission-brief-action-start-work"
                  className="rounded-xl bg-ds-accent px-3 py-2 text-xs font-medium text-white disabled:opacity-60"
                >
                  Start Work
                </button>
              )}
              {activeContract.contract.status === 'in_progress' && (
                <button
                  disabled={busy}
                  onClick={() => void handleTransition('review')}
                  data-testid="mission-brief-action-send-review"
                  className="rounded-xl bg-ds-accent px-3 py-2 text-xs font-medium text-white disabled:opacity-60"
                >
                  Send To Review
                </button>
              )}
              {activeContract.contract.status === 'review' && (
                <>
                  <button
                    disabled={busy}
                    onClick={() => void handleTransition('in_progress')}
                    data-testid="mission-brief-action-reopen"
                    className="rounded-xl bg-ds-accent px-3 py-2 text-xs font-medium text-white disabled:opacity-60"
                  >
                    Reopen
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => void handleTransition('closed')}
                    data-testid="mission-brief-action-close"
                    className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs font-medium text-emerald-200 disabled:opacity-60"
                  >
                    Close
                  </button>
                </>
              )}
              {!['closed', 'abandoned'].includes(activeContract.contract.status) && (
                <>
                  <button
                    disabled={busy}
                    onClick={() => setEditorOpen(true)}
                    data-testid="mission-brief-action-edit"
                    className="rounded-xl border border-ds-border px-3 py-2 text-xs text-ds-text hover:border-ds-accent disabled:opacity-60"
                  >
                    Edit
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => void handleTransition('abandoned')}
                    data-testid="mission-brief-action-abandon"
                    className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200 disabled:opacity-60"
                  >
                    Abandon
                  </button>
                </>
              )}
            </div>

            <div className="mt-4 rounded-2xl border border-ds-border bg-ds-surface px-4 py-4">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold text-ds-text">Stakeholder Delivery</p>
                  <p className="mt-1 text-[11px] text-ds-muted">
                    Build, preview, render, and dispatch audience-specific artifacts.
                  </p>
                </div>
                <div className="text-right">
                  {deliveryLogLoading && (
                    <span className="block text-[10px] text-ds-muted">Syncing log...</span>
                  )}
                  {!deliveryLogLoading && hasDeliveryPack && (
                    <span className="block text-[10px] text-ds-muted">
                      {deliveryRecordCount} log record{deliveryRecordCount === 1 ? '' : 's'}
                    </span>
                  )}
                </div>
              </div>

              <div className="mt-4 space-y-4">
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-ds-muted">Audience Selector</p>
                  <div className="mt-2">
                    <AudienceSelector
                      options={audienceOptions}
                      disabled={busy}
                      onToggle={toggleAudience}
                    />
                  </div>
                    <div className="mt-3 flex items-center gap-2">
                      <div className="grid min-w-0 flex-1 gap-2 md:grid-cols-3">
                        <input
                          value={sourceAnalysisId}
                          onChange={(event) => setSourceAnalysisId(event.target.value)}
                          placeholder="source analysis id (optional)"
                          className="min-w-0 rounded-xl border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text"
                        />
                        <input
                          value={tenant}
                          onChange={(event) => setTenant(event.target.value)}
                          placeholder="tenant"
                          className="min-w-0 rounded-xl border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text"
                        />
                        <input
                          value={themeId}
                          onChange={(event) => setThemeId(event.target.value)}
                          placeholder="theme_id (optional)"
                          className="min-w-0 rounded-xl border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text"
                        />
                      </div>
                    <button
                      disabled={busy}
                      onClick={() => void handleBuildDeliveryPack()}
                      className="rounded-xl bg-ds-accent px-3 py-2 text-xs font-medium text-white disabled:opacity-60"
                    >
                      {hasDeliveryPack ? 'Rebuild Pack' : 'Build Pack'}
                    </button>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] uppercase tracking-wide text-ds-muted">Render Input</p>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => setAnalysisDraft(defaultAnalysisDraft(activeContract))}
                      className="text-[10px] text-ds-muted hover:text-ds-text disabled:opacity-60"
                    >
                      Reset draft
                    </button>
                  </div>
                  <textarea
                    value={analysisDraft}
                    onChange={(event) => setAnalysisDraft(event.target.value)}
                    className="mt-2 h-32 w-full rounded-xl border border-ds-border bg-ds-bg px-3 py-2 font-mono text-[11px] text-ds-text"
                    spellCheck={false}
                  />
                  <div className="mt-3 grid gap-2 md:grid-cols-[auto_minmax(0,1fr)]">
                      <label className="flex items-center gap-2 rounded-xl border border-ds-border bg-ds-bg px-3 py-2 text-[11px] text-ds-muted">
                        <input
                          type="checkbox"
                          checked={providerBackedRender}
                          onChange={(event) => setProviderBackedRender(event.target.checked)}
                          className="h-3.5 w-3.5 rounded border-ds-border bg-ds-surface text-ds-accent"
                        />
                        Provider-backed narrative
                      </label>
                    <input
                      value={renderModel}
                      onChange={(event) => setRenderModel(event.target.value)}
                      disabled={!providerBackedRender}
                      placeholder="model override (optional)"
                      className="min-w-0 rounded-xl border border-ds-border bg-ds-bg px-3 py-2 text-xs text-ds-text disabled:cursor-not-allowed disabled:opacity-50"
                    />
                    </div>
                    <p className="mt-2 text-[10px] text-ds-muted">
                      Deterministic rendering stays default. Enable provider-backed mode only when you
                      want live model narration.
                    </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button
                      disabled={busy || !selectedArtifact}
                      onClick={() => void handleRenderSelectedArtifact()}
                      className="rounded-xl border border-ds-border px-3 py-2 text-xs text-ds-text hover:border-ds-accent disabled:opacity-60"
                    >
                      Render Selected
                    </button>
                    <button
                      disabled={busy || !hasDeliveryPack}
                      onClick={() => void handleDispatchSelected(true)}
                      className="rounded-xl border border-ds-border px-3 py-2 text-xs text-ds-text hover:border-ds-accent disabled:opacity-60"
                    >
                      Dry Run Selected
                    </button>
                    <button
                      disabled={busy || !hasDeliveryPack}
                      onClick={() => void handleDispatchPack(true)}
                      className="rounded-xl border border-ds-border px-3 py-2 text-xs text-ds-text hover:border-ds-accent disabled:opacity-60"
                    >
                      Dry Run Pack
                    </button>
                    <button
                      disabled={busy || !selectedArtifact}
                      onClick={() => void handleDispatchSelected(false)}
                      className="rounded-xl border border-ds-border px-3 py-2 text-xs text-ds-text hover:border-ds-accent disabled:opacity-60"
                    >
                      Send Selected
                    </button>
                    <button
                      disabled={busy || !hasDeliveryPack}
                      onClick={() => void handleDispatchPack(false)}
                      className="rounded-xl bg-ds-accent px-3 py-2 text-xs font-medium text-white disabled:opacity-60"
                    >
                      Send All
                    </button>
                  </div>
                </div>

                <DeliveryPackPreview
                  pack={activeContract.delivery_pack ?? null}
                  selectedArtifactId={selectedArtifactId}
                  logRecords={deliveryLog?.records ?? []}
                  onSelectArtifact={setSelectedArtifactId}
                  onRevealPath={(targetPath) => void handleRevealPath(targetPath)}
                />

                <ChannelInspector
                  artifact={selectedArtifact}
                  records={deliveryLog?.records ?? []}
                />

                {deliveryLog?.summary && (
                  <div className="rounded-xl border border-ds-border bg-ds-bg/60 px-3 py-3 text-[11px] text-ds-muted">
                    <p className="text-[11px] uppercase tracking-wide text-ds-muted">
                      Delivery Summary
                    </p>
                    <div className="mt-2 grid grid-cols-2 gap-2">
                      <div>Pack: {deliveryLog.summary.pack_status}</div>
                      <div>Artifacts: {deliveryLog.summary.artifact_count}</div>
                      <div>Rendered: {deliveryLog.summary.rendered_count}</div>
                      <div>Sent: {deliveryLog.summary.sent}</div>
                      <div>Blocked: {deliveryLog.summary.blocked}</div>
                      <div>Duplicates: {deliveryLog.summary.duplicate}</div>
                      <div>Failed: {deliveryLog.summary.failed}</div>
                      <div>Dry runs: {deliveryLog.summary.dry_run}</div>
                      <div className="col-span-2">
                        Last attempt: {deliveryLog.summary.last_attempt ?? '-'}
                      </div>
                    </div>
                  </div>
                )}

                {deliveryLog?.log_path && (
                  <div className="rounded-xl border border-ds-border bg-ds-bg/60 px-3 py-2 text-[11px] text-ds-muted">
                    Delivery log: {deliveryLog.log_path}
                  </div>
                )}

                {deliveryLogError && (
                  <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
                    {deliveryLogError}
                  </div>
                )}
              </div>
            </div>

            <button
              onClick={() => setDrawerOpen(true)}
              data-testid="mission-brief-open-assumptions"
              className={`mt-4 w-full rounded-2xl border px-4 py-3 text-left ${
                openAssumptions.some((entry) => entry.risk_level === 'high')
                  ? 'border-amber-500/50 bg-amber-500/10'
                  : 'border-ds-border bg-ds-surface'
              }`}
            >
              <p className="text-xs uppercase tracking-wide text-ds-muted">Assumptions</p>
              <p
                className="mt-1 text-sm font-medium text-ds-text"
                data-testid="mission-brief-open-assumptions-count"
              >
                {openAssumptions.length} open assumptions
              </p>
            </button>

            {activeContract.dod_summary.length > 0 && (
              <div className="mt-4 rounded-2xl border border-ds-border bg-ds-surface px-4 py-3">
                <p className="text-xs uppercase tracking-wide text-ds-muted">DoD Summary</p>
                <div className="mt-2 space-y-2">
                  {activeContract.dod_summary.map((item, index) => (
                    <p key={`${index}-${item}`} className="text-xs leading-5 text-ds-muted">
                      {item}
                    </p>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </section>

      {activeContract && (
        <>
          <ContractEditor
            contract={activeContract}
            open={editorOpen}
            saving={busy}
            onClose={() => setEditorOpen(false)}
            onSave={async (patch) => {
              await runAction(async () => savePatch(patch, 'renderer contract edit'));
              setEditorOpen(false);
            }}
          />
          <AssumptionDrawer
            open={drawerOpen}
            entries={openAssumptions}
            verifying={busy}
            onVerify={handleVerifyAssumption}
            onClose={() => setDrawerOpen(false)}
          />
          {closeDialogOpen && (
            <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 px-4">
              <div
                role="dialog"
                aria-modal="true"
                aria-labelledby="mission-brief-close-title"
                className="w-full max-w-lg rounded-2xl border border-ds-border bg-ds-surface shadow-2xl"
                data-testid="mission-brief-close-dialog"
              >
                <div className="flex items-center justify-between border-b border-ds-border px-5 py-4">
                  <div>
                    <h2
                      id="mission-brief-close-title"
                      className="text-base font-semibold text-ds-text"
                    >
                      Close Task Contract
                    </h2>
                    <p className="mt-1 text-xs text-ds-muted">
                      Record the operator note before the contract moves to closed.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setCloseDialogOpen(false)}
                    className="rounded-lg border border-ds-border px-3 py-1.5 text-xs text-ds-muted hover:border-ds-accent hover:text-ds-text"
                  >
                    Cancel
                  </button>
                </div>

                <div className="grid gap-4 p-5">
                  <label className="grid gap-2 text-xs text-ds-muted">
                    Closing Note
                    <textarea
                      value={closeNote}
                      onChange={(event) => setCloseNote(event.target.value)}
                      rows={4}
                      data-testid="mission-brief-close-note"
                      className="rounded-xl border border-ds-border bg-ds-bg px-3 py-2 text-sm text-ds-text outline-none focus:border-ds-accent"
                    />
                  </label>
                </div>

                <div className="flex items-center justify-end border-t border-ds-border px-5 py-4">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void handleConfirmClose()}
                    data-testid="mission-brief-close-confirm"
                    className="rounded-xl bg-ds-accent px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {busy ? 'Closing...' : 'Confirm Close'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      <CreateContractModal
        open={createDialogOpen}
        sessionId={sessionId}
        initialBusinessGoal={latestUserGoalSeed}
        saving={busy}
        onClose={() => setCreateDialogOpen(false)}
        onSubmit={handleCreateContract}
      />
    </>
  );
}

const MISSION_ARTIFACT_GATE_STYLES = {
  ready: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200',
  warning: 'border-amber-500/40 bg-amber-500/10 text-amber-200',
  danger: 'border-rose-500/40 bg-rose-500/10 text-rose-200',
} as const;

function getMissionArtifactGateTone(
  gate: MissionArtifactGateStatus,
): keyof typeof MISSION_ARTIFACT_GATE_STYLES {
  if (gate.issues.some((issue) => issue.kind === 'unavailable' || issue.kind === 'unmapped')) {
    return 'danger';
  }
  if (gate.issues.length > 0) {
    return 'warning';
  }
  return 'ready';
}

function formatMissionArtifactGateHeading(transitionTarget: string | null): string {
  if (transitionTarget === 'close') {
    return 'Close blocked by mission artifact gate.';
  }
  if (transitionTarget === 'review') {
    return 'Review blocked by mission artifact gate.';
  }
  return 'Mission artifact gate blocked this action.';
}

function readTaskContractErrorDetail(
  error: unknown,
): TaskContractErrorDetailView | null {
  if (!error || typeof error !== 'object' || !('detail' in error)) {
    return null;
  }
  const detail = (error as { detail?: unknown }).detail;
  if (!detail || typeof detail !== 'object') {
    return null;
  }
  const message = (detail as { message?: unknown }).message;
  return typeof message === 'string'
    ? (detail as TaskContractErrorDetailView)
    : null;
}

// ---------------------------------------------------------------------------
// Gate panel sub-components
// ---------------------------------------------------------------------------

const MISSION_GATE_DANGER_STYLES = 'border-rose-500/40 bg-rose-500/10 text-rose-200';
const MISSION_GATE_WARNING_STYLES = 'border-amber-500/40 bg-amber-500/10 text-amber-200';

function MissionCheckGatePanel({
  gate,
  label,
  testId,
}: {
  gate: MissionCheckGateStatus;
  label: string;
  testId?: string;
}) {
  const hasFailed = gate.failed.length > 0;
  const hasUnmapped = gate.unmapped.length > 0;
  const tone = hasFailed ? MISSION_GATE_DANGER_STYLES : MISSION_GATE_WARNING_STYLES;

  return (
    <div
      className={`mt-3 rounded-2xl border px-4 py-3 ${tone}`}
      data-testid={testId}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-ds-muted">
            {label}
          </p>
          <p className="mt-1 text-sm font-semibold text-ds-text">
            {hasFailed ? 'Checks Failed' : 'Checks Unmapped'}
          </p>
        </div>
        {gate.missionName && (
          <span className="rounded-full border border-current/20 px-2 py-1 text-[11px] font-medium text-inherit">
            {gate.missionName}
          </span>
        )}
      </div>

      {gate.requiredChecks.length > 0 && (
        <p className="mt-2 text-xs leading-5 text-ds-text/90">
          Required: {gate.requiredChecks.join(', ')}
        </p>
      )}

      <div className="mt-3 space-y-2">
        {hasFailed && (
          <div className="rounded-xl border border-current/15 bg-black/10 px-3 py-2 text-xs leading-5 text-current">
            <span className="font-medium">Failed checks</span>: {gate.failed.join(', ')}
          </div>
        )}
        {hasUnmapped && (
          <div className="rounded-xl border border-current/15 bg-black/10 px-3 py-2 text-xs leading-5 text-current">
            <span className="font-medium">Unmapped checks</span>: {gate.unmapped.join(', ')}
          </div>
        )}
      </div>

      {gate.transitionTarget && (
        <p className="mt-2 text-xs text-ds-muted">
          Transition blocked: {gate.transitionTarget}
        </p>
      )}
    </div>
  );
}

function MissionChannelGatePanel({
  gate,
  label,
  testId,
}: {
  gate: MissionChannelGateStatus;
  label: string;
  testId?: string;
}) {
  const hasMissing = gate.missing.length > 0;
  const hasUnmapped = gate.unmapped.length > 0;
  const tone = hasMissing ? MISSION_GATE_DANGER_STYLES : MISSION_GATE_WARNING_STYLES;

  return (
    <div
      className={`mt-3 rounded-2xl border px-4 py-3 ${tone}`}
      data-testid={testId}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-ds-muted">
            {label}
          </p>
          <p className="mt-1 text-sm font-semibold text-ds-text">
            {hasMissing ? 'Channels Not Delivered' : 'Channels Unmapped'}
          </p>
        </div>
        {gate.missionName && (
          <span className="rounded-full border border-current/20 px-2 py-1 text-[11px] font-medium text-inherit">
            {gate.missionName}
          </span>
        )}
      </div>

      {gate.requiredChannels.length > 0 && (
        <p className="mt-2 text-xs leading-5 text-ds-text/90">
          Required: {gate.requiredChannels.join(', ')}
        </p>
      )}

      <div className="mt-3 space-y-2">
        {hasMissing && (
          <div className="rounded-xl border border-current/15 bg-black/10 px-3 py-2 text-xs leading-5 text-current">
            <span className="font-medium">Missing delivery</span>: {gate.missing.join(', ')}
          </div>
        )}
        {gate.satisfied.length > 0 && (
          <div className="rounded-xl border border-current/15 bg-black/10 px-3 py-2 text-xs leading-5 text-current">
            <span className="font-medium">Satisfied</span>: {gate.satisfied.join(', ')}
          </div>
        )}
        {hasUnmapped && (
          <div className="rounded-xl border border-current/15 bg-black/10 px-3 py-2 text-xs leading-5 text-current">
            <span className="font-medium">Unmapped channels</span>: {gate.unmapped.join(', ')}
          </div>
        )}
        {!gate.dispatchLogAvailable && (
          <div className="rounded-xl border border-current/15 bg-black/10 px-3 py-2 text-xs leading-5 text-current">
            <span className="font-medium">Dispatch log unavailable</span> — cannot verify channel delivery.
          </div>
        )}
      </div>

      {gate.transitionTarget && (
        <p className="mt-2 text-xs text-ds-muted">
          Transition blocked: {gate.transitionTarget}
        </p>
      )}
    </div>
  );
}
