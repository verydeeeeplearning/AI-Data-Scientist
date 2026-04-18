import {
  AlertTriangle,
  BriefcaseBusiness,
  CheckCircle2,
  Layers3,
  Loader2,
  ShieldAlert,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useWs } from '../../hooks/WsProvider';
import { fetchPolicySnapshot } from '../../hooks/usePolicy';
import { useCertificationBoard } from '../../hooks/useCertificationBoard';
import { useTaskContract } from '../../hooks/useTaskContract';
import {
  usePolicyStore,
  type ActionMatrixOverrideMap,
  type MatrixAuthority,
  type MatrixVerdict,
} from '../../stores/policyStore';
import { useRuntimeStore } from '../../stores/runtimeStore';
import {
  AUDIENCE_OPTIONS,
  AUDIENCE_PREVIEWS,
  buildLegacyModeMigrationPreview,
  CONTRACT_AUTHORITY_OPTIONS,
  EFFECTIVE_AUTHORITY_CARDS,
  MATRIX_AUTHORITY_COLUMNS,
  MATRIX_VERDICT_OPTIONS,
  POLICY_STUDIO_PRESETS,
  formatAudienceLabel,
  formatAuthorityLabel,
  formatMatrixVerdictLabel,
  isAudienceDraft,
  isContractAuthorityDraft,
  isEffectiveAuthorityMode,
  type AudienceDraft,
  type ContractAuthorityDraft,
} from './policyStudioCatalog';

const NO_MISSION_VALUE = '__none__';
const INHERIT_MATRIX_VALUE = '__inherit__';

function countMatrixOverrides(overrides: ActionMatrixOverrideMap): number {
  return Object.values(overrides).reduce(
    (count, row) => count + Object.keys(row).length,
    0,
  );
}

function normalizeMatrixOverrides(overrides: ActionMatrixOverrideMap): ActionMatrixOverrideMap {
  const normalized: ActionMatrixOverrideMap = {};
  for (const [actionClass, row] of Object.entries(overrides)) {
    const filtered = Object.fromEntries(
      Object.entries(row).filter(([, verdict]) => Boolean(verdict)),
    );
    if (Object.keys(filtered).length > 0) {
      normalized[actionClass] = filtered as Partial<Record<MatrixAuthority, MatrixVerdict>>;
    }
  }
  return normalized;
}

function countMatrixDiffCells(
  current: ActionMatrixOverrideMap,
  draft: ActionMatrixOverrideMap,
): number {
  const actionClasses = new Set([...Object.keys(current), ...Object.keys(draft)]);
  let changed = 0;

  for (const actionClass of actionClasses) {
    for (const authority of MATRIX_AUTHORITY_COLUMNS.map((column) => column.value)) {
      const currentVerdict = current[actionClass]?.[authority] ?? null;
      const draftVerdict = draft[actionClass]?.[authority] ?? null;
      if (currentVerdict !== draftVerdict) {
        changed += 1;
      }
    }
  }

  return changed;
}

function countMatrixDiffRows(
  current: ActionMatrixOverrideMap,
  draft: ActionMatrixOverrideMap,
): number {
  return Object.keys({
    ...current,
    ...draft,
  }).filter((actionClass) => {
    return MATRIX_AUTHORITY_COLUMNS.some(
      (column) => (current[actionClass]?.[column.value] ?? null)
        !== (draft[actionClass]?.[column.value] ?? null),
    );
  }).length;
}

export function PolicyStudio() {
  const { rpc } = useWs();
  const runtimeStatus = useRuntimeStore((s) => s.status);
  const policySnapshot = usePolicyStore((s) => s.snapshot);
  const setPolicySnapshot = usePolicyStore((s) => s.setSnapshot);
  const markPolicyUpdated = usePolicyStore((s) => s.markUpdated);
  const {
    sessionId,
    activeContract,
    loading: contractLoading,
    error: contractError,
    savePatch,
  } = useTaskContract();
  const {
    missions,
    loading: missionLoading,
    error: missionError,
  } = useCertificationBoard();

  const [authorityDraft, setAuthorityDraft] = useState<ContractAuthorityDraft>('inherit');
  const [audienceDraft, setAudienceDraft] = useState<AudienceDraft>('inherit');
  const [missionDraft, setMissionDraft] = useState<string>(NO_MISSION_VALUE);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [matrixDraft, setMatrixDraft] = useState<ActionMatrixOverrideMap>({});
  const [matrixDirty, setMatrixDirty] = useState(false);
  const [matrixSaving, setMatrixSaving] = useState(false);
  const [matrixNotice, setMatrixNotice] = useState<string | null>(null);
  const [matrixError, setMatrixError] = useState<string | null>(null);

  const currentAuthority = useMemo<ContractAuthorityDraft>(() => {
    const raw = activeContract?.contract.authority;
    return isContractAuthorityDraft(raw) ? raw : 'inherit';
  }, [activeContract?.contract.authority]);

  const currentAudience = useMemo<AudienceDraft>(() => {
    const raw = activeContract?.contract.audience;
    return isAudienceDraft(raw) ? raw : 'inherit';
  }, [activeContract?.contract.audience]);

  const currentMission = activeContract?.contract.mission ?? NO_MISSION_VALUE;

  useEffect(() => {
    setAuthorityDraft(currentAuthority);
    setAudienceDraft(currentAudience);
    setMissionDraft(currentMission);
    setNotice(null);
    setActionError(null);
  }, [currentAuthority, currentAudience, currentMission, activeContract?.contract.version]);

  const currentMatrixOverrides = useMemo(
    () => normalizeMatrixOverrides(policySnapshot?.actionMatrixOverrides ?? {}),
    [policySnapshot?.actionMatrixOverrides],
  );
  const actionMatrixRows = policySnapshot?.actionMatrixRows ?? [];

  useEffect(() => {
    if (!matrixDirty) {
      setMatrixDraft(currentMatrixOverrides);
      setMatrixNotice(null);
      setMatrixError(null);
    }
  }, [currentMatrixOverrides, matrixDirty]);

  const missionOptions = useMemo(() => {
    const seen = new Set<string>();
    const options: { name: string; fromCatalog: boolean }[] = [];

    const activeMission = activeContract?.contract.mission;
    if (activeMission && !seen.has(activeMission)) {
      seen.add(activeMission);
      options.push({ name: activeMission, fromCatalog: false });
    }

    for (const mission of missions) {
      if (seen.has(mission.mission_name)) {
        continue;
      }
      seen.add(mission.mission_name);
      options.push({ name: mission.mission_name, fromCatalog: true });
    }

    return options;
  }, [activeContract?.contract.mission, missions]);

  const selectedMissionStatus = useMemo(() => {
    if (missionDraft === NO_MISSION_VALUE) {
      return null;
    }
    return missions.find((mission) => mission.mission_name === missionDraft) ?? null;
  }, [missionDraft, missions]);

  const overlayMode = runtimeStatus?.authorityOverlay ?? null;
  const runtimeEffectiveAuthority = runtimeStatus?.effectiveAuthorityMode ?? null;
  const legacyMigration = useMemo(
    () => buildLegacyModeMigrationPreview(runtimeStatus?.mode),
    [runtimeStatus?.mode],
  );
  const fallbackAudience = runtimeStatus?.mode === 'step-by-step' ? 'junior_mentor' : 'peer_ds';
  const previewAudienceKey = useMemo<Exclude<AudienceDraft, 'inherit'>>(() => {
    if (audienceDraft !== 'inherit') {
      return audienceDraft;
    }
    if (isAudienceDraft(activeContract?.contract.audience)) {
      return activeContract.contract.audience;
    }
    return fallbackAudience;
  }, [activeContract?.contract.audience, audienceDraft, fallbackAudience]);
  const preview = AUDIENCE_PREVIEWS[previewAudienceKey];

  const hasPendingChanges = authorityDraft !== currentAuthority
    || audienceDraft !== currentAudience
    || missionDraft !== currentMission;

  const loading = contractLoading || missionLoading;
  const effectiveAuthorityCard = useMemo(() => {
    if (isEffectiveAuthorityMode(overlayMode)) {
      return overlayMode;
    }
    if (isEffectiveAuthorityMode(runtimeEffectiveAuthority)) {
      return runtimeEffectiveAuthority;
    }
    return currentAuthority === 'inherit' ? 'delegate' : currentAuthority;
  }, [currentAuthority, overlayMode, runtimeEffectiveAuthority]);

  const matrixDraftNormalized = useMemo(
    () => normalizeMatrixOverrides(matrixDraft),
    [matrixDraft],
  );
  const currentMatrixOverrideCount = policySnapshot?.actionMatrixOverrideCount
    ?? countMatrixOverrides(currentMatrixOverrides);
  const draftMatrixOverrideCount = countMatrixOverrides(matrixDraftNormalized);
  const matrixChangedCells = useMemo(
    () => countMatrixDiffCells(currentMatrixOverrides, matrixDraftNormalized),
    [currentMatrixOverrides, matrixDraftNormalized],
  );
  const matrixChangedRows = useMemo(
    () => countMatrixDiffRows(currentMatrixOverrides, matrixDraftNormalized),
    [currentMatrixOverrides, matrixDraftNormalized],
  );
  const hasPendingMatrixChanges = matrixChangedCells > 0;
  const legacyDraftApplied = authorityDraft === legacyMigration.authority
    && audienceDraft === legacyMigration.audience;

  const refreshPolicy = async () => {
    const nextSnapshot = await fetchPolicySnapshot(rpc);
    setPolicySnapshot(nextSnapshot);
    markPolicyUpdated();
    return nextSnapshot;
  };

  const setMatrixCellDraft = (
    actionClass: string,
    authority: MatrixAuthority,
    verdict: MatrixVerdict | typeof INHERIT_MATRIX_VALUE,
  ) => {
    setMatrixDraft((current) => {
      const next: ActionMatrixOverrideMap = {
        ...current,
      };
      const existingRow = {
        ...(next[actionClass] ?? {}),
      };
      if (verdict === INHERIT_MATRIX_VALUE) {
        delete existingRow[authority];
      } else {
        existingRow[authority] = verdict;
      }

      if (Object.keys(existingRow).length === 0) {
        delete next[actionClass];
      } else {
        next[actionClass] = existingRow;
      }
      return next;
    });
    setMatrixDirty(true);
    setMatrixSaving(false);
    setMatrixNotice(null);
    setMatrixError(null);
  };

  const handleApply = async () => {
    if (!activeContract) {
      return;
    }

    setSaving(true);
    setActionError(null);
    setNotice(null);
    try {
      await savePatch(
        {
          authority: authorityDraft === 'inherit' ? null : authorityDraft,
          audience: audienceDraft === 'inherit' ? null : audienceDraft,
          mission: missionDraft === NO_MISSION_VALUE ? null : missionDraft,
        },
        'operator updated policy studio autonomy axes',
      );
      setNotice('Task contract autonomy axes updated.');
    } catch (error) {
      setActionError(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveMatrix = async () => {
    setMatrixSaving(true);
    setMatrixError(null);
    setMatrixNotice(null);
    try {
      await rpc('policy.setActionMatrixOverrides', {
        overrides: matrixDraftNormalized,
      });
      await refreshPolicy();
      setMatrixDirty(false);
      setMatrixNotice('Action Matrix overrides saved.');
    } catch (error) {
      setMatrixError(error instanceof Error ? error.message : String(error));
    } finally {
      setMatrixSaving(false);
    }
  };

  return (
    <div
      data-testid="policy-studio"
      className="space-y-3 rounded-lg border border-ds-border bg-ds-bg p-3"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-ds-text">
            <ShieldAlert size={14} className="text-ds-accent" />
            Policy Studio
          </div>
          <p className="mt-1 text-[11px] text-ds-muted">
            Overlay {'>'} contract authority {'>'} mission defaults {'>'} legacy runtime mode.
            Audience follows the same inheritance rule.
          </p>
        </div>
        {loading && <Loader2 size={14} className="mt-0.5 animate-spin text-ds-accent" />}
      </div>

      {overlayMode && (
        <div
          data-testid="policy-overlay-banner"
          className="rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-[11px] text-amber-200"
        >
          Runtime overlay <span className="font-medium">{formatAuthorityLabel(overlayMode)}</span>{' '}
          is active. It overrides the task-contract authority until cleared in Runtime Console.
        </div>
      )}

      <div className="grid gap-2 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-2 rounded-lg border border-ds-border/60 bg-ds-surface/70 p-3">
          <div
            data-testid="policy-quick-presets-card"
            className="rounded border border-ds-border/60 bg-ds-bg/70 px-3 py-2"
          >
            <div className="text-[11px] font-medium text-ds-text">
              Quick presets
            </div>
            <p className="mt-1 text-[11px] text-ds-muted">
              Apply one common authority + audience pair to the draft. Mission stays unchanged.
            </p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {POLICY_STUDIO_PRESETS.map((preset) => {
                const active = authorityDraft === preset.authority
                  && audienceDraft === preset.audience;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    data-testid={`policy-quick-preset-${preset.id}`}
                    disabled={!activeContract || saving || active}
                    onClick={() => {
                      setAuthorityDraft(preset.authority);
                      setAudienceDraft(preset.audience);
                      setActionError(null);
                      setNotice(null);
                    }}
                    className={`rounded border px-3 py-2 text-left disabled:opacity-50 ${
                      active
                        ? 'border-ds-accent/60 bg-ds-accent/10'
                        : 'border-ds-border bg-ds-surface hover:border-ds-accent/40'
                    }`}
                  >
                    <div className="text-xs font-medium text-ds-text">{preset.label}</div>
                    <div className="mt-1 text-[11px] text-ds-muted">
                      {formatAuthorityLabel(preset.authority)} + {formatAudienceLabel(preset.audience)}
                    </div>
                    <div className="mt-1 text-[11px] text-ds-muted">{preset.summary}</div>
                  </button>
                );
              })}
            </div>
          </div>

          <div
            data-testid="policy-legacy-migration-card"
            className="rounded border border-ds-border/60 bg-ds-bg/70 px-3 py-2"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="text-[11px] font-medium text-ds-text">
                  Legacy mode migration helper
                </div>
                <div
                  data-testid="policy-legacy-migration-mode"
                  className="mt-1 text-[11px] text-ds-muted"
                >
                  Runtime mode <span className="font-medium text-ds-text">{legacyMigration.legacyMode}</span>
                  {' '}maps to <span className="font-medium text-ds-text">{formatAuthorityLabel(legacyMigration.authority)}</span>
                  {' '}+ <span className="font-medium text-ds-text">{formatAudienceLabel(legacyMigration.audience)}</span>.
                </div>
              </div>
              <span
                className={`rounded border px-2 py-0.5 text-[10px] ${
                  legacyMigration.exactMatch
                    ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-200'
                    : 'border-amber-400/40 bg-amber-400/10 text-amber-200'
                }`}
              >
                {legacyMigration.exactMatch ? 'Exact' : 'Approximate'}
              </span>
            </div>
            <p className="mt-2 text-[11px] text-ds-muted">{legacyMigration.summary}</p>
            <div className="mt-2 space-y-1 text-[11px] text-ds-muted">
              {legacyMigration.notes.map((note) => (
                <div key={note}>- {note}</div>
              ))}
            </div>
            <button
              type="button"
              data-testid="policy-apply-legacy-mapping"
              disabled={!activeContract || saving || legacyDraftApplied}
              onClick={() => {
                setAuthorityDraft(legacyMigration.authority);
                setAudienceDraft(legacyMigration.audience);
                setActionError(null);
                setNotice(null);
              }}
              className="mt-3 rounded border border-ds-border px-3 py-1.5 text-xs text-ds-text disabled:opacity-50"
            >
              Apply legacy mapping to draft
            </button>
          </div>

          <div className="flex items-center gap-2 text-[11px] font-medium text-ds-text">
            <BriefcaseBusiness size={13} className="text-ds-muted" />
            Current Session Contract
          </div>

          {!sessionId && (
            <p className="text-[11px] text-ds-muted">
              Open or start a session first. Policy Studio edits the active TaskContract for the
              current chat session.
            </p>
          )}

          {sessionId && !activeContract && !contractLoading && (
            <p className="text-[11px] text-ds-muted">
              No active TaskContract was found for <span className="font-mono">{sessionId}</span>.
            </p>
          )}

          {contractError && (
            <p className="text-[11px] text-ds-error">{contractError}</p>
          )}

          {activeContract && (
            <>
              <div
                data-testid="policy-contract-card"
                className="rounded border border-ds-border/60 bg-ds-bg/70 px-3 py-2"
              >
                <div className="flex flex-wrap items-center gap-2 text-[11px]">
                  <span className="rounded border border-ds-border/70 px-2 py-0.5 font-mono text-ds-text">
                    {activeContract.contract.task_id}
                  </span>
                  <span className="rounded border border-ds-border/70 px-2 py-0.5 text-ds-muted">
                    {activeContract.contract.status}
                  </span>
                  <span className="text-ds-muted">session {sessionId}</span>
                </div>
                <div className="mt-2 text-xs text-ds-text">
                  {activeContract.contract.business_goal}
                </div>
              </div>

              <div className="grid gap-2 md:grid-cols-3">
                <label className="space-y-1 text-[11px] text-ds-muted">
                  <span>Contract authority</span>
                  <select
                    value={authorityDraft}
                    onChange={(event) =>
                      setAuthorityDraft(event.target.value as ContractAuthorityDraft)
                    }
                    data-testid="policy-authority-select"
                    disabled={saving}
                    className="w-full rounded border border-ds-border bg-ds-bg px-2 py-1.5 text-xs text-ds-text"
                  >
                    {CONTRACT_AUTHORITY_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="space-y-1 text-[11px] text-ds-muted">
                  <span>Audience persona</span>
                  <select
                    value={audienceDraft}
                    onChange={(event) => setAudienceDraft(event.target.value as AudienceDraft)}
                    data-testid="policy-audience-select"
                    disabled={saving}
                    className="w-full rounded border border-ds-border bg-ds-bg px-2 py-1.5 text-xs text-ds-text"
                  >
                    {AUDIENCE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="space-y-1 text-[11px] text-ds-muted">
                  <span>Mission pack</span>
                  <select
                    value={missionDraft}
                    onChange={(event) => setMissionDraft(event.target.value)}
                    data-testid="policy-mission-select"
                    disabled={saving}
                    className="w-full rounded border border-ds-border bg-ds-bg px-2 py-1.5 text-xs text-ds-text"
                  >
                    <option value={NO_MISSION_VALUE}>None</option>
                    {missionOptions.map((mission) => (
                      <option key={mission.name} value={mission.name}>
                        {mission.name}
                        {mission.fromCatalog ? '' : ' (current)'}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="flex flex-wrap items-center gap-2 text-[11px] text-ds-muted">
                <span>
                  Current authority: <span className="text-ds-text">{formatAuthorityLabel(activeContract.contract.authority)}</span>
                </span>
                <span>
                  Current audience: <span className="text-ds-text">{formatAudienceLabel(activeContract.contract.audience)}</span>
                </span>
                <span>
                  Current mission: <span className="text-ds-text">{activeContract.contract.mission ?? 'None'}</span>
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => void handleApply()}
                  data-testid="policy-apply-task-contract"
                  disabled={!hasPendingChanges || saving}
                  className="rounded bg-ds-accent px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
                >
                  {saving ? 'Applying...' : 'Apply to TaskContract'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setAuthorityDraft(currentAuthority);
                    setAudienceDraft(currentAudience);
                    setMissionDraft(currentMission);
                    setActionError(null);
                    setNotice(null);
                  }}
                  disabled={!hasPendingChanges || saving}
                  className="rounded border border-ds-border px-3 py-1.5 text-xs text-ds-text disabled:opacity-50"
                >
                  Reset Draft
                </button>
              </div>

              {notice && (
                <div className="flex items-center gap-2 text-[11px] text-ds-success">
                  <CheckCircle2 size={12} />
                  {notice}
                </div>
              )}
              {actionError && (
                <div className="flex items-center gap-2 text-[11px] text-ds-error">
                  <AlertTriangle size={12} />
                  {actionError}
                </div>
              )}
            </>
          )}
        </div>

        <div className="space-y-2 rounded-lg border border-ds-border/60 bg-ds-surface/70 p-3">
          <div className="flex items-center gap-2 text-[11px] font-medium text-ds-text">
            <Layers3 size={13} className="text-ds-muted" />
            Runtime Guardrails
          </div>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {EFFECTIVE_AUTHORITY_CARDS.map((card) => {
              const active = card.value === effectiveAuthorityCard;
              const outlined = overlayMode === card.value;
              return (
                <div
                  key={card.value}
                  className={`rounded border px-2 py-2 ${
                    active
                      ? 'border-ds-accent/70 bg-ds-accent/10'
                      : 'border-ds-border/70 bg-ds-bg/70'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-[11px] font-medium text-ds-text">{card.label}</div>
                    {outlined && (
                      <span className="rounded bg-amber-400/15 px-1.5 py-0.5 text-[10px] text-amber-300">
                        overlay
                      </span>
                    )}
                  </div>
                  <div className="mt-1 text-[10px] leading-5 text-ds-muted">{card.summary}</div>
                </div>
              );
            })}
          </div>
          <div className="grid gap-2 text-[11px] text-ds-muted sm:grid-cols-2">
            <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-2 py-2">
              <div>Legacy runtime mode</div>
              <div className="mt-1 font-medium text-ds-text">{runtimeStatus?.mode ?? 'auto'}</div>
            </div>
            <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-2 py-2">
              <div>Runtime effective authority</div>
              <div className="mt-1 font-medium text-ds-text">
                {formatAuthorityLabel(runtimeEffectiveAuthority)}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-3 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="space-y-2 rounded-lg border border-ds-border/60 bg-ds-surface/70 p-3">
          <div className="flex items-center gap-2 text-[11px] font-medium text-ds-text">
            <ShieldAlert size={13} className="text-ds-muted" />
            Mission Catalog
          </div>

          {missionError && (
            <p className="text-[11px] text-ds-error">{missionError}</p>
          )}

          {missions.length === 0 && !missionLoading ? (
            <p className="text-[11px] text-ds-muted">
              No mission packs with certification metadata were found.
            </p>
          ) : (
            <div className="space-y-1.5">
              {missionOptions.map((mission) => {
                const status = missions.find((item) => item.mission_name === mission.name) ?? null;
                const selected = missionDraft === mission.name;
                const active = activeContract?.contract.mission === mission.name;
                return (
                  <button
                    key={mission.name}
                    type="button"
                    onClick={() => setMissionDraft(mission.name)}
                    className={`w-full rounded border px-3 py-2 text-left ${
                      selected
                        ? 'border-ds-accent/70 bg-ds-accent/10'
                        : 'border-ds-border/70 bg-ds-bg/70 hover:border-ds-accent/40'
                    }`}
                  >
                    <div className="flex flex-wrap items-center gap-2 text-xs text-ds-text">
                      <span className="font-medium">{mission.name}</span>
                      {active && (
                        <span className="rounded bg-ds-success/15 px-1.5 py-0.5 text-[10px] text-ds-success">
                          active
                        </span>
                      )}
                      {status?.effective_level && (
                        <span className="rounded bg-ds-surface px-1.5 py-0.5 text-[10px] text-ds-muted">
                          {status.effective_level}
                        </span>
                      )}
                      {status?.next_target && (
                        <span className="rounded bg-ds-surface px-1.5 py-0.5 text-[10px] text-ds-muted">
                          next {status.next_target}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-[10px] text-ds-muted">
                      {status
                        ? status.certified_for_next_target
                          ? 'Ready for the next certification target.'
                          : `${status.gaps.length} open certification gap(s).`
                        : 'Mission is present on the contract but has no catalog metadata yet.'}
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-3 py-2 text-[11px] text-ds-muted">
            {selectedMissionStatus ? (
              <div className="space-y-1.5">
                <div className="flex flex-wrap items-center gap-3">
                  <span>
                    Effective level:{' '}
                    <span className="font-medium text-ds-text">
                      {selectedMissionStatus.effective_level ?? 'none'}
                    </span>
                  </span>
                  <span>
                    Required approvers:{' '}
                    <span className="font-medium text-ds-text">
                      {selectedMissionStatus.required_approvers}
                    </span>
                  </span>
                </div>
                <div>
                  Gaps:{' '}
                  <span className="text-ds-text">
                    {selectedMissionStatus.gaps.length > 0
                      ? selectedMissionStatus.gaps.slice(0, 3).join(' | ')
                      : 'none'}
                  </span>
                </div>
              </div>
            ) : (
              <span>
                Select a mission pack to inspect its certification readiness and use it in the
                current contract.
              </span>
            )}
          </div>
        </div>

        <div className="space-y-2 rounded-lg border border-ds-border/60 bg-ds-surface/70 p-3">
          <div className="flex items-center gap-2 text-[11px] font-medium text-ds-text">
            <ShieldAlert size={13} className="text-ds-muted" />
            Audience Preview
          </div>

          <div className="flex flex-wrap gap-1.5">
            {AUDIENCE_OPTIONS.filter((option) => option.value !== 'inherit').map((option) => {
              const active = previewAudienceKey === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setAudienceDraft(option.value as AudienceDraft)}
                  className={`rounded border px-2 py-1 text-[11px] ${
                    active
                      ? 'border-ds-accent/70 bg-ds-accent/10 text-ds-text'
                      : 'border-ds-border bg-ds-bg text-ds-muted hover:text-ds-text'
                  }`}
                >
                  {option.label}
                </button>
              );
            })}
          </div>

          <div className="rounded border border-ds-border/70 bg-ds-bg/70 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-ds-text">{preview.label}</span>
              <span className="rounded bg-ds-surface px-1.5 py-0.5 text-[10px] text-ds-muted">
                tone {preview.tone}
              </span>
              <span className="rounded bg-ds-surface px-1.5 py-0.5 text-[10px] text-ds-muted">
                depth {preview.depth}
              </span>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {preview.defaultArtifacts.map((artifact) => (
                <span
                  key={artifact}
                  className="rounded border border-ds-border/70 px-1.5 py-0.5 text-[10px] text-ds-muted"
                >
                  {artifact}
                </span>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-ds-muted">
              Uncertainty handling: <span className="text-ds-text">{preview.uncertaintyStyle}</span>
            </p>
            <div className="mt-3 rounded border border-ds-border/70 bg-ds-surface/70 px-3 py-2">
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-ds-muted">
                <ShieldAlert size={11} />
                Sample response
              </div>
              <div className="mt-2 space-y-1.5 text-[11px] leading-5 text-ds-text">
                {preview.sample.map((line) => (
                  <p key={line}>{line}</p>
                ))}
              </div>
            </div>
          </div>

          <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-3 py-2 text-[11px] text-ds-muted">
            <div className="flex items-center gap-2">
              <Layers3 size={12} />
              Preview currently reflects{' '}
              <span className="font-medium text-ds-text">{formatAudienceLabel(audienceDraft)}</span>.
            </div>
            <div className="mt-1">
              If the contract stays on inherit, the runtime will fall back to the mission default
              first and then the legacy audience mapping ({formatAudienceLabel(fallbackAudience)}).
            </div>
          </div>
        </div>
      </div>

      <div className="space-y-2 rounded-lg border border-ds-border/60 bg-ds-surface/70 p-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-medium text-ds-text">
              <AlertTriangle size={13} className="text-amber-300" />
              Action Matrix
            </div>
            <p className="mt-1 text-[11px] text-ds-muted">
              Operator overrides persist the base authority matrix. Mission-pack overrides still
              take precedence at runtime when a mission explicitly pins a verdict.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void handleSaveMatrix()}
              data-testid="policy-matrix-save"
              disabled={!hasPendingMatrixChanges || matrixSaving}
              className="rounded bg-ds-accent px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
            >
              {matrixSaving ? 'Saving...' : 'Save Matrix Draft'}
            </button>
            <button
              type="button"
              onClick={() => {
                setMatrixDraft(currentMatrixOverrides);
                setMatrixDirty(false);
                setMatrixNotice(null);
                setMatrixError(null);
              }}
              disabled={!hasPendingMatrixChanges || matrixSaving}
              className="rounded border border-ds-border px-3 py-1.5 text-xs text-ds-text disabled:opacity-50"
            >
              Reset Draft
            </button>
            <button
              type="button"
              onClick={() => {
                setMatrixDraft({});
                setMatrixDirty(true);
                setMatrixNotice(null);
                setMatrixError(null);
              }}
              disabled={draftMatrixOverrideCount === 0 || matrixSaving}
              className="rounded border border-ds-border px-3 py-1.5 text-xs text-ds-text disabled:opacity-50"
            >
              Clear Overrides
            </button>
          </div>
        </div>

        <div className="grid gap-2 sm:grid-cols-4">
          <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-3 py-2">
            <div className="text-[10px] text-ds-muted">Stored overrides</div>
            <div
              data-testid="policy-matrix-stored-count"
              className="mt-1 text-sm font-mono text-ds-text"
            >
              {currentMatrixOverrideCount}
            </div>
          </div>
          <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-3 py-2">
            <div className="text-[10px] text-ds-muted">Draft overrides</div>
            <div className="mt-1 text-sm font-mono text-ds-text">{draftMatrixOverrideCount}</div>
          </div>
          <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-3 py-2">
            <div className="text-[10px] text-ds-muted">Changed cells</div>
            <div className="mt-1 text-sm font-mono text-ds-text">{matrixChangedCells}</div>
          </div>
          <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-3 py-2">
            <div className="text-[10px] text-ds-muted">Changed rows</div>
            <div className="mt-1 text-sm font-mono text-ds-text">{matrixChangedRows}</div>
          </div>
        </div>

        {matrixNotice && (
          <div className="flex items-center gap-2 text-[11px] text-ds-success">
            <CheckCircle2 size={12} />
            {matrixNotice}
          </div>
        )}
        {matrixError && (
          <div className="flex items-center gap-2 text-[11px] text-ds-error">
            <AlertTriangle size={12} />
            {matrixError}
          </div>
        )}

        {actionMatrixRows.length === 0 ? (
          <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-3 py-2 text-[11px] text-ds-muted">
            Policy snapshot is not available yet. Keep the runtime connected to load the current
            matrix state.
          </div>
        ) : (
          <div className="overflow-x-auto rounded border border-ds-border/70">
            <table className="min-w-[1120px] w-full border-collapse text-left">
              <thead className="bg-ds-bg/80 text-[10px] uppercase tracking-wider text-ds-muted">
                <tr>
                  <th className="border-b border-ds-border px-3 py-2 font-medium">Action class</th>
                  {MATRIX_AUTHORITY_COLUMNS.map((column) => (
                    <th
                      key={column.value}
                      className="border-b border-ds-border px-2 py-2 font-medium"
                    >
                      {column.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {actionMatrixRows.map((row) => (
                  <tr key={row.actionClass} className="align-top">
                    <td className="border-b border-ds-border/70 px-3 py-3">
                      <div className="text-xs font-medium text-ds-text">{row.actionClass}</div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        <span className="rounded border border-ds-border/70 px-1.5 py-0.5 text-[10px] text-ds-muted">
                          data {row.dataSensitivity}
                        </span>
                        <span className="rounded border border-ds-border/70 px-1.5 py-0.5 text-[10px] text-ds-muted">
                          write {row.writeSideEffect}
                        </span>
                        <span className="rounded border border-ds-border/70 px-1.5 py-0.5 text-[10px] text-ds-muted">
                          cost {row.costImpact}
                        </span>
                        <span className="rounded border border-ds-border/70 px-1.5 py-0.5 text-[10px] text-ds-muted">
                          {row.reversibility}
                        </span>
                        {row.auditRequired && (
                          <span className="rounded border border-amber-400/40 px-1.5 py-0.5 text-[10px] text-amber-200">
                            audit
                          </span>
                        )}
                      </div>
                    </td>
                    {MATRIX_AUTHORITY_COLUMNS.map((column) => {
                      const currentOverride = currentMatrixOverrides[row.actionClass]?.[column.value] ?? null;
                      const draftOverride = matrixDraftNormalized[row.actionClass]?.[column.value] ?? null;
                      const draftValue = draftOverride ?? INHERIT_MATRIX_VALUE;
                      const defaultVerdict = row.defaultVerdicts[column.value];
                      const currentEffectiveVerdict = row.effectiveVerdicts[column.value];
                      const previewVerdict = draftOverride ?? defaultVerdict;
                      const changed = currentOverride !== draftOverride;

                      return (
                        <td
                          key={`${row.actionClass}-${column.value}`}
                          className={`border-b border-ds-border/70 px-2 py-3 ${
                            changed ? 'bg-amber-400/5' : ''
                          }`}
                        >
                          <select
                            value={draftValue}
                            onChange={(event) =>
                              setMatrixCellDraft(
                                row.actionClass,
                                column.value,
                                event.target.value as MatrixVerdict | typeof INHERIT_MATRIX_VALUE,
                              )
                            }
                            data-testid={`policy-matrix-${row.actionClass}-${column.value}`}
                            disabled={matrixSaving}
                            className={`w-full rounded border px-2 py-1.5 text-xs ${
                              changed
                                ? 'border-amber-400/40 bg-amber-400/5 text-ds-text'
                                : 'border-ds-border bg-ds-bg text-ds-text'
                            }`}
                          >
                            <option value={INHERIT_MATRIX_VALUE}>
                              Inherit ({formatMatrixVerdictLabel(defaultVerdict)})
                            </option>
                            {MATRIX_VERDICT_OPTIONS.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                          <div className="mt-1.5 space-y-1 text-[10px] leading-4 text-ds-muted">
                            <div>
                              Current {formatMatrixVerdictLabel(currentEffectiveVerdict)}
                            </div>
                            <div>
                              Preview{' '}
                              <span className={changed ? 'text-amber-200' : 'text-ds-text'}>
                                {formatMatrixVerdictLabel(previewVerdict)}
                              </span>
                            </div>
                            <div>
                              Override {currentOverride ? formatMatrixVerdictLabel(currentOverride) : 'none'}
                            </div>
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
