import {
  AlertTriangle,
  BriefcaseBusiness,
  CheckCircle2,
  Layers3,
  Loader2,
  ShieldAlert,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useCanMutate } from '../../hooks/useCanMutate';
import { useI18n } from '../../stores/i18nStore';
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
import { RiskTierMatrixEditor } from './RiskTierMatrixEditor';
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

interface ImpactPreviewCounts {
  autonomous: number;
  guided: number;
  blocked: number;
}

interface ImpactPreviewRow {
  authority: MatrixAuthority;
  label: string;
  current: ImpactPreviewCounts;
  preview: ImpactPreviewCounts;
  changedRows: number;
  isHighlighted: boolean;
}

function createImpactPreviewCounts(): ImpactPreviewCounts {
  return {
    autonomous: 0,
    guided: 0,
    blocked: 0,
  };
}

function addImpactPreviewVerdict(
  counts: ImpactPreviewCounts,
  verdict: MatrixVerdict,
): void {
  if (verdict === 'auto') {
    counts.autonomous += 1;
    return;
  }
  if (verdict === 'skip') {
    counts.blocked += 1;
    return;
  }
  counts.guided += 1;
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

export function PolicyStudio() {
  const { t } = useI18n();
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
  const { canMutate, reason: mutateBlockedReason } = useCanMutate();
  const mutateBlockedTitle = mutateBlockedReason ?? undefined;
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
  const impactPreview = useMemo<ImpactPreviewRow[]>(() => {
    return MATRIX_AUTHORITY_COLUMNS.map((column) => {
      const current = createImpactPreviewCounts();
      const preview = createImpactPreviewCounts();
      let changedRows = 0;

      for (const row of actionMatrixRows) {
        const currentVerdict = row.effectiveVerdicts[column.value];
        const previewVerdict = matrixDraftNormalized[row.actionClass]?.[column.value]
          ?? row.defaultVerdicts[column.value];

        addImpactPreviewVerdict(current, currentVerdict);
        addImpactPreviewVerdict(preview, previewVerdict);

        if (currentVerdict !== previewVerdict) {
          changedRows += 1;
        }
      }

      return {
        authority: column.value,
        label: column.label,
        current,
        preview,
        changedRows,
        isHighlighted: effectiveAuthorityCard === column.value,
      };
    });
  }, [actionMatrixRows, effectiveAuthorityCard, matrixDraftNormalized]);
  const hasPendingMatrixChanges = matrixChangedCells > 0;
  const legacyDraftApplied = authorityDraft === legacyMigration.authority
    && audienceDraft === legacyMigration.audience;
  const quickPresetDisabledReason = !activeContract
    ? t('settings.policyStudio.quickPresetsDisabledNoContract')
    : undefined;
  const legacyMappingDisabledReason = !activeContract
    ? t('settings.policyStudio.legacyMappingDisabledNoContract')
    : undefined;
  const matrixSaveDisabledReason = !hasPendingMatrixChanges
    ? t('settings.policyStudio.matrixSaveDisabledNoChanges')
    : undefined;
  const matrixResetDisabledReason = !hasPendingMatrixChanges
    ? t('settings.policyStudio.matrixResetDisabledNoChanges')
    : undefined;
  const matrixClearDisabledReason = draftMatrixOverrideCount === 0
    ? t('settings.policyStudio.matrixClearDisabledNoOverrides')
    : undefined;

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
      setNotice(t('settings.policyStudio.notice.contractUpdated'));
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
      setMatrixNotice(t('settings.policyStudio.notice.matrixSaved'));
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
            {t('settings.policyStudio.title')}
          </div>
          <p className="mt-1 text-[11px] text-ds-muted">
            {t('settings.policyStudio.headerDescription')}
          </p>
        </div>
        {loading && <Loader2 size={14} className="mt-0.5 animate-spin text-ds-accent" />}
      </div>

      {overlayMode && (
        <div
          data-testid="policy-overlay-banner"
          className="rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-[11px] text-amber-200"
        >
          {t('settings.policyStudio.overlayBannerPrefix')} <span className="font-medium">{t(formatAuthorityLabel(overlayMode))}</span>{' '}
          {t('settings.policyStudio.overlayBannerSuffix')}
        </div>
      )}

      <div className="grid gap-2 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-2 rounded-lg border border-ds-border/60 bg-ds-surface/70 p-3">
          <div
            data-testid="policy-quick-presets-card"
            className="rounded border border-ds-border/60 bg-ds-bg/70 px-3 py-2"
          >
            <div className="text-[11px] font-medium text-ds-text">
              {t('settings.policyStudio.quickPresets')}
            </div>
            <p className="mt-1 text-[11px] text-ds-muted">
              {t('settings.policyStudio.quickPresetsDescription')}
            </p>
            {!activeContract && (
              <p className="mt-2 rounded border border-amber-400/30 bg-amber-400/10 px-2 py-1.5 text-[11px] text-amber-200">
                {t('settings.policyStudio.quickPresetsDisabledNoContract')}
              </p>
            )}
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {POLICY_STUDIO_PRESETS.map((preset) => {
                const active = authorityDraft === preset.authority
                  && audienceDraft === preset.audience;
                const presetDisabledReason = quickPresetDisabledReason
                  ?? (active ? t('settings.policyStudio.quickPresetAlreadySelected') : undefined);
                return (
                  <button
                    key={preset.id}
                    type="button"
                    data-testid={`policy-quick-preset-${preset.id}`}
                    disabled={!activeContract || saving || active}
                    title={presetDisabledReason}
                    aria-label={presetDisabledReason
                      ? `${t(preset.label)}. ${presetDisabledReason}`
                      : t(preset.label)}
                    onClick={() => {
                      setAuthorityDraft(preset.authority);
                      setAudienceDraft(preset.audience);
                      setActionError(null);
                      setNotice(null);
                    }}
                    className={`rounded border px-3 py-2 text-left transition disabled:opacity-50 ${
                      active
                        ? 'border-ds-accent/70 bg-ds-accent/10 ring-1 ring-ds-accent/40'
                        : 'border-ds-border bg-ds-surface hover:border-ds-accent/40 hover:bg-ds-bg'
                    }`}
                  >
                    <div className="flex items-center gap-2 text-xs font-medium text-ds-text">
                      <span>{t(preset.label)}</span>
                      {active && (
                        <span className="ml-auto rounded border border-ds-accent/50 px-1.5 py-0.5 text-[10px] text-ds-accent">
                          {t('settings.policyStudio.tag.selected')}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-[11px] text-ds-muted">
                      {t(formatAuthorityLabel(preset.authority))} + {t(formatAudienceLabel(preset.audience))}
                    </div>
                    <div className="mt-1 text-[11px] text-ds-muted">{t(preset.summary)}</div>
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
                  {t('settings.policyStudio.legacyMigrationHelper')}
                </div>
                <div
                  data-testid="policy-legacy-migration-mode"
                  className="mt-1 text-[11px] text-ds-muted"
                >
                  {t('settings.policyStudio.runtimeModeLabel')} <span className="font-medium text-ds-text">{legacyMigration.legacyMode}</span>
                  {' '}{t('settings.policyStudio.mapsTo')} <span className="font-medium text-ds-text">{t(formatAuthorityLabel(legacyMigration.authority))}</span>
                  {' '}+ <span className="font-medium text-ds-text">{t(formatAudienceLabel(legacyMigration.audience))}</span>.
                </div>
              </div>
              <span
                className={`rounded border px-2 py-0.5 text-[10px] ${
                  legacyMigration.exactMatch
                    ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-200'
                    : 'border-amber-400/40 bg-amber-400/10 text-amber-200'
                }`}
              >
                {legacyMigration.exactMatch ? t('settings.policyStudio.exact') : t('settings.policyStudio.approximate')}
              </span>
            </div>
            <p className="mt-2 text-[11px] text-ds-muted">{t(legacyMigration.summary)}</p>
            {!activeContract && (
              <p className="mt-2 rounded border border-amber-400/30 bg-amber-400/10 px-2 py-1.5 text-[11px] text-amber-200">
                {t('settings.policyStudio.legacyMappingGuidanceNoContract')}
              </p>
            )}
            <div className="mt-2 space-y-1 text-[11px] text-ds-muted">
              {legacyMigration.notes.map((note) => (
                <div key={note}>- {t(note)}</div>
              ))}
            </div>
            <button
              type="button"
              data-testid="policy-apply-legacy-mapping"
              disabled={!activeContract || saving || legacyDraftApplied}
              title={legacyMappingDisabledReason}
              aria-label={legacyMappingDisabledReason
                ? `${t('settings.policyStudio.applyLegacyMapping')}. ${legacyMappingDisabledReason}`
                : t('settings.policyStudio.applyLegacyMapping')}
              onClick={() => {
                setAuthorityDraft(legacyMigration.authority);
                setAudienceDraft(legacyMigration.audience);
                setActionError(null);
                setNotice(null);
              }}
              className="mt-3 rounded border border-ds-border px-3 py-1.5 text-xs text-ds-text disabled:opacity-50"
            >
              {t('settings.policyStudio.applyLegacyMapping')}
            </button>
          </div>

          <div className="flex items-center gap-2 text-[11px] font-medium text-ds-text">
            <BriefcaseBusiness size={13} className="text-ds-muted" />
            {t('settings.policyStudio.currentSessionContract')}
          </div>

          {!sessionId && (
            <p className="text-[11px] text-ds-muted">
              {t('settings.policyStudio.openSessionFirst')}
            </p>
          )}

          {sessionId && !activeContract && !contractLoading && (
            <p className="text-[11px] text-ds-muted">
              {t('settings.policyStudio.noActiveContract', { sessionId })}
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
                  <span>{t('settings.policyStudio.contractAuthorityLabel')}</span>
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
                        {t(option.label)}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="space-y-1 text-[11px] text-ds-muted">
                  <span>{t('settings.policyStudio.audiencePersona')}</span>
                  <select
                    value={audienceDraft}
                    onChange={(event) => setAudienceDraft(event.target.value as AudienceDraft)}
                    data-testid="policy-audience-select"
                    disabled={saving}
                    className="w-full rounded border border-ds-border bg-ds-bg px-2 py-1.5 text-xs text-ds-text"
                  >
                    {AUDIENCE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {t(option.label)}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="space-y-1 text-[11px] text-ds-muted">
                  <span>{t('settings.policyStudio.missionPack')}</span>
                  <select
                    value={missionDraft}
                    onChange={(event) => setMissionDraft(event.target.value)}
                    data-testid="policy-mission-select"
                    disabled={saving}
                    className="w-full rounded border border-ds-border bg-ds-bg px-2 py-1.5 text-xs text-ds-text"
                  >
                    <option value={NO_MISSION_VALUE}>{t('settings.policyStudio.none')}</option>
                    {missionOptions.map((mission) => (
                      <option key={mission.name} value={mission.name}>
                        {mission.name}
                        {mission.fromCatalog ? '' : ` ${t('settings.policyStudio.current')}`}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="flex flex-wrap items-center gap-2 text-[11px] text-ds-muted">
                <span>
                  {t('settings.policyStudio.currentAuthority')}: <span className="text-ds-text">{t(formatAuthorityLabel(activeContract.contract.authority))}</span>
                </span>
                <span>
                  {t('settings.policyStudio.currentAudience')}: <span className="text-ds-text">{t(formatAudienceLabel(activeContract.contract.audience))}</span>
                </span>
                <span>
                  {t('settings.policyStudio.currentMission')}: <span className="text-ds-text">{activeContract.contract.mission ?? t('settings.policyStudio.none')}</span>
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => void handleApply()}
                  data-testid="policy-apply-task-contract"
                  disabled={!canMutate || !hasPendingChanges || saving}
                  aria-disabled={!canMutate || undefined}
                  title={canMutate ? undefined : mutateBlockedTitle}
                  className="rounded bg-ds-accent px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
                >
                  {saving ? t('settings.policyStudio.applying') : t('settings.policyStudio.applyToTaskContract')}
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
                  {t('settings.policyStudio.resetDraft')}
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
            {t('settings.policyStudio.runtimeGuardrails')}
          </div>
          <p className="text-[11px] text-ds-muted">
            {t('settings.policyStudio.runtimeGuardrailsDescription')}
          </p>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {EFFECTIVE_AUTHORITY_CARDS.map((card) => {
              const active = card.value === effectiveAuthorityCard;
              const outlined = overlayMode === card.value;
              return (
                <div
                  key={card.value}
                  aria-current={active ? 'true' : undefined}
                  className={`rounded border px-2 py-2 transition ${
                    active
                      ? 'border-ds-accent/70 bg-ds-accent/10 ring-1 ring-ds-accent/35'
                      : 'border-ds-border/70 bg-ds-bg/70'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-[11px] font-medium text-ds-text">{t(card.label)}</div>
                    {active && (
                      <span className="rounded border border-ds-accent/50 px-1.5 py-0.5 text-[10px] text-ds-accent">
                        {t('settings.policyStudio.tag.live')}
                      </span>
                    )}
                    {outlined && (
                      <span className="rounded bg-amber-400/15 px-1.5 py-0.5 text-[10px] text-amber-300">
                        {t('settings.policyStudio.tag.overlay')}
                      </span>
                    )}
                  </div>
                  <div className="mt-1 text-[10px] leading-5 text-ds-muted">{t(card.summary)}</div>
                </div>
              );
            })}
          </div>
          <p className="text-[10px] text-ds-muted">
            {t('settings.policyStudio.runtimeGuardrailsInformational')}
          </p>
          <div className="grid gap-2 text-[11px] text-ds-muted sm:grid-cols-2">
            <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-2 py-2">
              <div>{t('settings.policyStudio.legacyRuntimeMode')}</div>
              <div className="mt-1 font-medium text-ds-text">{runtimeStatus?.mode ?? 'auto'}</div>
            </div>
            <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-2 py-2">
              <div>{t('settings.policyStudio.runtimeEffectiveAuthority')}</div>
              <div className="mt-1 font-medium text-ds-text">
                {t(formatAuthorityLabel(runtimeEffectiveAuthority))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-3 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="space-y-2 rounded-lg border border-ds-border/60 bg-ds-surface/70 p-3">
          <div className="flex items-center gap-2 text-[11px] font-medium text-ds-text">
            <ShieldAlert size={13} className="text-ds-muted" />
            {t('settings.policyStudio.missionCatalog')}
          </div>
          <p className="text-[11px] text-ds-muted">
            {t('settings.policyStudio.missionCatalogDescription')}
          </p>

          {missionError && (
            <p className="text-[11px] text-ds-error">{missionError}</p>
          )}

          {missions.length === 0 && !missionLoading ? (
            <p className="text-[11px] text-ds-muted">
              {t('settings.policyStudio.noMissionPacks')}
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
                    aria-pressed={selected}
                    className={`w-full rounded border px-3 py-2 text-left transition ${
                      selected
                        ? 'border-ds-accent/70 bg-ds-accent/10 ring-1 ring-ds-accent/40'
                        : 'border-ds-border/70 bg-ds-bg/70 hover:border-ds-accent/40 hover:bg-ds-bg'
                    }`}
                  >
                    <div className="flex flex-wrap items-center gap-2 text-xs text-ds-text">
                      <span className="font-medium">{mission.name}</span>
                      {selected && (
                        <span className="rounded border border-ds-accent/50 px-1.5 py-0.5 text-[10px] text-ds-accent">
                          {t('settings.policyStudio.tag.selected')}
                        </span>
                      )}
                      {active && (
                        <span className="rounded bg-ds-success/15 px-1.5 py-0.5 text-[10px] text-ds-success">
                          {t('settings.policyStudio.tag.active')}
                        </span>
                      )}
                      {status?.effective_level && (
                        <span className="rounded bg-ds-surface px-1.5 py-0.5 text-[10px] text-ds-muted">
                          {status.effective_level}
                        </span>
                      )}
                      {status?.next_target && (
                        <span className="rounded bg-ds-surface px-1.5 py-0.5 text-[10px] text-ds-muted">
                          {t('settings.policyStudio.tag.next', { target: status.next_target })}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-[10px] text-ds-muted">
                      {status
                        ? status.certified_for_next_target
                          ? t('settings.policyStudio.certReady')
                          : t('settings.policyStudio.certGaps', { count: status.gaps.length })
                        : t('settings.policyStudio.certNoCatalog')}
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
                    {t('settings.policyStudio.effectiveLevel')}:{' '}
                    <span className="font-medium text-ds-text">
                      {selectedMissionStatus.effective_level ?? t('settings.policyStudio.none')}
                    </span>
                  </span>
                  <span>
                    {t('settings.policyStudio.requiredApprovers')}:{' '}
                    <span className="font-medium text-ds-text">
                      {selectedMissionStatus.required_approvers}
                    </span>
                  </span>
                </div>
                <div>
                  {t('settings.policyStudio.gaps')}:{' '}
                  <span className="text-ds-text">
                    {selectedMissionStatus.gaps.length > 0
                      ? selectedMissionStatus.gaps.slice(0, 3).join(' | ')
                      : t('settings.policyStudio.none')}
                  </span>
                </div>
              </div>
            ) : (
              <span>
                {t('settings.policyStudio.selectMissionPrompt')}
              </span>
            )}
          </div>
        </div>

        <div className="space-y-2 rounded-lg border border-ds-border/60 bg-ds-surface/70 p-3">
          <div className="flex items-center gap-2 text-[11px] font-medium text-ds-text">
            <ShieldAlert size={13} className="text-ds-muted" />
            {t('settings.policyStudio.audiencePreviewTitle')}
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
                  {t(option.label)}
                </button>
              );
            })}
          </div>

          <div className="rounded border border-ds-border/70 bg-ds-bg/70 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-ds-text">{t(preview.label)}</span>
              <span className="rounded bg-ds-surface px-1.5 py-0.5 text-[10px] text-ds-muted">
                {t('settings.policyStudio.toneLabel')} {t(preview.tone)}
              </span>
              <span className="rounded bg-ds-surface px-1.5 py-0.5 text-[10px] text-ds-muted">
                {t('settings.policyStudio.depthLabel')} {t(preview.depth)}
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
              {t('settings.policyStudio.uncertaintyHandling')} <span className="text-ds-text">{t(preview.uncertaintyStyle)}</span>
            </p>
            <div className="mt-3 rounded border border-ds-border/70 bg-ds-surface/70 px-3 py-2">
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-ds-muted">
                <ShieldAlert size={11} />
                {t('settings.policyStudio.sampleResponse')}
              </div>
              <div className="mt-2 space-y-1.5 text-[11px] leading-5 text-ds-text">
                {preview.sample.map((line) => (
                  <p key={line}>{t(line)}</p>
                ))}
              </div>
            </div>
          </div>

          <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-3 py-2 text-[11px] text-ds-muted">
            <div className="flex items-center gap-2">
              <Layers3 size={12} />
              {t('settings.policyStudio.previewReflects')}{' '}
              <span className="font-medium text-ds-text">{t(formatAudienceLabel(audienceDraft))}</span>.
            </div>
            <div className="mt-1">
              {t('settings.policyStudio.previewFallback', { fallback: t(formatAudienceLabel(fallbackAudience)) })}
            </div>
          </div>
        </div>
      </div>

      <div className="space-y-2 rounded-lg border border-ds-border/60 bg-ds-surface/70 p-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-medium text-ds-text">
              <AlertTriangle size={13} className="text-amber-300" />
              {t('settings.policyStudio.actionMatrix')}
            </div>
            <p className="mt-1 text-[11px] text-ds-muted">
              {t('settings.policyStudio.actionMatrixDescription')}
            </p>
          </div>
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => void handleSaveMatrix()}
                data-testid="policy-matrix-save"
                disabled={!hasPendingMatrixChanges || matrixSaving}
                title={matrixSaving ? t('settings.policyStudio.savingMatrix') : matrixSaveDisabledReason}
                aria-label={matrixSaveDisabledReason
                  ? `${t('settings.policyStudio.saveMatrixDraft')}. ${matrixSaveDisabledReason}`
                  : t('settings.policyStudio.saveMatrixDraft')}
                className="rounded bg-ds-accent px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
              >
                {t(matrixSaving ? 'settings.policyStudio.savingMatrix' : 'settings.policyStudio.saveMatrixDraft')}
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
                title={matrixSaving ? t('settings.policyStudio.savingMatrix') : matrixResetDisabledReason}
                aria-label={matrixResetDisabledReason
                  ? `${t('settings.policyStudio.resetDraft')}. ${matrixResetDisabledReason}`
                  : t('settings.policyStudio.resetDraft')}
                className="rounded border border-ds-border px-3 py-1.5 text-xs text-ds-text disabled:opacity-50"
              >
                {t('settings.policyStudio.resetDraft')}
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
                title={matrixSaving ? t('settings.policyStudio.savingMatrix') : matrixClearDisabledReason}
                aria-label={matrixClearDisabledReason
                  ? `${t('settings.policyStudio.clearOverrides')}. ${matrixClearDisabledReason}`
                  : t('settings.policyStudio.clearOverrides')}
                className="rounded border border-ds-border px-3 py-1.5 text-xs text-ds-text disabled:opacity-50"
              >
                {t('settings.policyStudio.clearOverrides')}
              </button>
            </div>
            {!hasPendingMatrixChanges && draftMatrixOverrideCount === 0 && (
              <p className="text-right text-[10px] text-ds-muted">
                {t('settings.policyStudio.matrixButtonGroupIdleHint')}
              </p>
            )}
          </div>
        </div>

        <div className="grid gap-2 sm:grid-cols-4">
          <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-3 py-2">
            <div className="text-[10px] text-ds-muted">{t('settings.policyStudio.storedOverrides')}</div>
            <div
              data-testid="policy-matrix-stored-count"
              className="mt-1 text-sm font-mono text-ds-text"
            >
              {currentMatrixOverrideCount}
            </div>
          </div>
          <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-3 py-2">
            <div className="text-[10px] text-ds-muted">{t('settings.policyStudio.draftOverrides')}</div>
            <div className="mt-1 text-sm font-mono text-ds-text">{draftMatrixOverrideCount}</div>
          </div>
          <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-3 py-2">
            <div className="text-[10px] text-ds-muted">{t('settings.policyStudio.changedCells')}</div>
            <div className="mt-1 text-sm font-mono text-ds-text">{matrixChangedCells}</div>
          </div>
          <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-3 py-2">
            <div className="text-[10px] text-ds-muted">{t('settings.policyStudio.changedRows')}</div>
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
            {t('settings.policyStudio.matrixEmpty')}
          </div>
        ) : (
          <>
            <div
              data-testid="policy-impact-preview"
              className="rounded border border-ds-border/70 bg-ds-bg/70 p-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 text-[11px] font-medium text-ds-text">
                    <BriefcaseBusiness size={12} className="text-ds-muted" />
                    {t('settings.policyStudio.draftImpactPreview')}
                  </div>
                  <p className="mt-1 max-w-3xl text-[11px] text-ds-muted">
                    {t('settings.policyStudio.draftImpactDescription')}
                  </p>
                </div>
                <div className="rounded border border-ds-border/70 bg-ds-surface/70 px-2 py-1 text-[10px] text-ds-muted">
                  {t('settings.policyStudio.currentRuntimeAuthority', { authority: t(formatAuthorityLabel(effectiveAuthorityCard)) })}
                </div>
              </div>

              <div className="mt-3 grid gap-2 xl:grid-cols-3">
                {impactPreview.map((item) => (
                  <div
                    key={item.authority}
                    className={`rounded border px-3 py-3 ${
                      item.isHighlighted
                        ? 'border-ds-accent/50 bg-ds-accent/10'
                        : 'border-ds-border/70 bg-ds-surface/70'
                    }`}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-medium text-ds-text">{t(item.label)}</span>
                      {item.isHighlighted && (
                        <span className="rounded border border-ds-accent/50 px-1.5 py-0.5 text-[10px] text-ds-accent">
                          {t('settings.policyStudio.tag.live')}
                        </span>
                      )}
                      <span className="ml-auto rounded border border-ds-border/70 px-1.5 py-0.5 text-[10px] text-ds-muted">
                        {t('settings.policyStudio.changedRowsCount', { count: item.changedRows })}
                      </span>
                    </div>

                    <div className="mt-3 grid grid-cols-3 gap-2">
                      <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-2 py-2">
                        <div className="text-[10px] text-ds-muted">{t('settings.policyStudio.autonomous')}</div>
                        <div className="mt-1 text-xs text-ds-text">
                          {item.current.autonomous} → {item.preview.autonomous}
                        </div>
                      </div>
                      <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-2 py-2">
                        <div className="text-[10px] text-ds-muted">{t('settings.policyStudio.guided')}</div>
                        <div className="mt-1 text-xs text-ds-text">
                          {item.current.guided} → {item.preview.guided}
                        </div>
                      </div>
                      <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-2 py-2">
                        <div className="text-[10px] text-ds-muted">{t('settings.policyStudio.blocked')}</div>
                        <div className="mt-1 text-xs text-ds-text">
                          {item.current.blocked} → {item.preview.blocked}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="overflow-x-auto rounded border border-ds-border/70">
              <table className="min-w-[1120px] w-full border-collapse text-left">
                <thead className="bg-ds-bg/80 text-[10px] uppercase tracking-wider text-ds-muted">
                  <tr>
                    <th className="border-b border-ds-border px-3 py-2 font-medium">{t('settings.policyStudio.actionClass')}</th>
                    {MATRIX_AUTHORITY_COLUMNS.map((column) => (
                      <th
                        key={column.value}
                        className="border-b border-ds-border px-2 py-2 font-medium"
                      >
                        {t(column.label)}
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
                            {t('settings.policyStudio.tag.data', { value: row.dataSensitivity })}
                          </span>
                          <span className="rounded border border-ds-border/70 px-1.5 py-0.5 text-[10px] text-ds-muted">
                            {t('settings.policyStudio.tag.write', { value: row.writeSideEffect })}
                          </span>
                          <span className="rounded border border-ds-border/70 px-1.5 py-0.5 text-[10px] text-ds-muted">
                            {t('settings.policyStudio.tag.cost', { value: row.costImpact })}
                          </span>
                          <span className="rounded border border-ds-border/70 px-1.5 py-0.5 text-[10px] text-ds-muted">
                            {row.reversibility}
                          </span>
                          {row.auditRequired && (
                            <span className="rounded border border-amber-400/40 px-1.5 py-0.5 text-[10px] text-amber-200">
                              {t('settings.policyStudio.tag.audit')}
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
                              aria-label={`${row.actionClass} verdict for ${t(column.label)}`}
                              disabled={matrixSaving}
                              className={`w-full rounded border px-2 py-1.5 text-xs ${
                                changed
                                  ? 'border-amber-400/40 bg-amber-400/5 text-ds-text'
                                  : 'border-ds-border bg-ds-bg text-ds-text'
                              }`}
                            >
                              <option value={INHERIT_MATRIX_VALUE}>
                                {t('settings.policyStudio.matrix.inheritOption', { verdict: t(formatMatrixVerdictLabel(defaultVerdict)) })}
                              </option>
                              {MATRIX_VERDICT_OPTIONS.map((option) => (
                                <option key={option.value} value={option.value}>
                                  {t(option.label)}
                                </option>
                              ))}
                            </select>
                            <div className="mt-1.5 space-y-1 text-[10px] leading-4 text-ds-muted">
                              <div>
                                {t('settings.policyStudio.matrix.currentVerdict', { verdict: t(formatMatrixVerdictLabel(currentEffectiveVerdict)) })}
                              </div>
                              <div>
                                {t('settings.policyStudio.matrix.previewLabel')}{' '}
                                <span className={changed ? 'text-amber-200' : 'text-ds-text'}>
                                  {t(formatMatrixVerdictLabel(previewVerdict))}
                                </span>
                              </div>
                              <div>
                                {t('settings.policyStudio.matrix.overrideLabel', { verdict: currentOverride ? t(formatMatrixVerdictLabel(currentOverride)) : t('settings.policyStudio.none') })}
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
          </>
        )}
      </div>

      <RiskTierMatrixEditor actionMatrixRows={actionMatrixRows} />
    </div>
  );
}
