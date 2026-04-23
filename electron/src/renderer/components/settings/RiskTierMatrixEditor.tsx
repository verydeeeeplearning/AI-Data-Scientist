import {
  AlertTriangle,
  CheckCircle2,
  Layers3,
  Loader2,
  RotateCcw,
  ShieldAlert,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useWs } from '../../hooks/WsProvider';
import { usePolicyMatrix } from '../../hooks/usePolicyMatrix';
import { useI18n } from '../../stores/i18nStore';
import type {
  ActionMatrixRowEntry,
  MatrixAuthority,
} from '../../stores/policyStore';
import {
  MATRIX_AUTHORITY_COLUMNS,
  POLICY_RISK_TIER_DEFINITIONS,
} from './policyStudioCatalog';
import {
  countRiskTierCellDiff,
  countRiskTierRowDiff,
  coerceRiskTierValue,
  formatRiskTierLabel,
  formatRiskTierSnapshotLabel,
  normalizeRiskTierMatrix,
  resolveRiskTierSavedBy,
  type RiskTier,
  RISK_TIER_OPTIONS,
} from '../../application/policy/riskTierMatrix';
import {
  mergeImpactPreview,
  type MergedImpactPreview,
} from '../../application/policy/previewMatrixImpact';
import type {
  RiskTierMatrix,
  RiskTierMatrixSnapshot,
} from '../../application/policy/matrixPort';

interface RiskTierMatrixEditorProps {
  actionMatrixRows: ActionMatrixRowEntry[];
}

function getTierBadgeClass(value: string): string {
  switch (value) {
    case 'T0':
      return 'border-emerald-400/40 bg-emerald-400/10 text-emerald-200';
    case 'T1':
      return 'border-sky-400/40 bg-sky-400/10 text-sky-200';
    case 'T2':
      return 'border-amber-400/40 bg-amber-400/10 text-amber-200';
    case 'T3':
      return 'border-rose-400/40 bg-rose-400/10 text-rose-200';
    default:
      return 'border-ds-border/70 bg-ds-bg/80 text-ds-muted';
  }
}

function buildTierSummary(rows: ActionMatrixRowEntry[]): string {
  if (rows.length === 0) {
    return 'No rows are available to derive a risk tier preview.';
  }

  const signals: string[] = [];
  if (rows.some((row) => row.dataSensitivity === 'pii')) {
    signals.push('PII');
  } else if (rows.some((row) => row.dataSensitivity === 'restricted')) {
    signals.push('restricted');
  } else {
    signals.push('public/internal');
  }

  if (rows.some((row) => row.writeSideEffect === 'irreversible')) {
    signals.push('irreversible writes');
  } else if (rows.some((row) => row.writeSideEffect === 'external')) {
    signals.push('external writes');
  } else if (rows.some((row) => row.writeSideEffect === 'local')) {
    signals.push('local writes');
  }

  if (rows.some((row) => row.costImpact === 'high')) {
    signals.push('high spend');
  }

  if (rows.some((row) => row.auditRequired)) {
    signals.push('audit-bound');
  }

  return signals.join(' | ');
}

export function RiskTierMatrixEditor({ actionMatrixRows }: RiskTierMatrixEditorProps) {
  const { rpc } = useWs();
  const { t } = useI18n();
  const policyMatrix = usePolicyMatrix();
  const [currentMatrix, setCurrentMatrix] = useState<RiskTierMatrix>({});
  const [draftMatrix, setDraftMatrix] = useState<RiskTierMatrix>({});
  const [lastSaved, setLastSaved] = useState<RiskTierMatrixSnapshot | null>(null);
  const [savedBy, setSavedBy] = useState<string | null>(null);
  const [matrixSaving, setMatrixSaving] = useState(false);
  const [matrixNotice, setMatrixNotice] = useState<string | null>(null);
  const [matrixError, setMatrixError] = useState<string | null>(null);
  const [matrixImpact, setMatrixImpact] = useState<MergedImpactPreview | null>(null);
  const previewSeqRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const result = await policyMatrix.load();
        if (cancelled) {
          return;
        }
        const matrix = normalizeRiskTierMatrix(result.matrix);
        setCurrentMatrix(matrix);
        setDraftMatrix(matrix);
        setLastSaved(result.history[0] ?? null);
      } catch (error) {
        if (!cancelled) {
          console.warn('[RiskTierMatrixEditor] policy.matrix.get failed:', error);
          setMatrixError(
            error instanceof Error ? error.message : String(error),
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [policyMatrix]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const result = await rpc('org.get');
        if (cancelled) {
          return;
        }
        const organization = (result as { organization?: { members?: Array<{ userId?: string | null; role?: string | null }> } }).organization;
        const resolved = resolveRiskTierSavedBy(organization ?? null);
        setSavedBy(resolved ?? 'local-user');
      } catch {
        if (!cancelled) {
          setSavedBy('local-user');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [rpc]);

  useEffect(() => {
    if (countRiskTierCellDiff(currentMatrix, draftMatrix) === 0) {
      setMatrixImpact(null);
      return;
    }

    const seq = previewSeqRef.current + 1;
    previewSeqRef.current = seq;
    const heuristicChangedCells = countRiskTierCellDiff(currentMatrix, draftMatrix);

    void (async () => {
      try {
        const result = await policyMatrix.preview({ candidateMatrix: draftMatrix });
        if (previewSeqRef.current !== seq) {
          return;
        }
        setMatrixImpact(mergeImpactPreview(result, heuristicChangedCells));
      } catch (error) {
        if (previewSeqRef.current !== seq) {
          return;
        }
        console.warn('[RiskTierMatrixEditor] policy.matrix.preview failed:', error);
      }
    })();
  }, [currentMatrix, draftMatrix, policyMatrix]);

  const dirtyCells = useMemo(
    () => countRiskTierCellDiff(currentMatrix, draftMatrix),
    [currentMatrix, draftMatrix],
  );
  const dirtyRows = useMemo(
    () => countRiskTierRowDiff(currentMatrix, draftMatrix),
    [currentMatrix, draftMatrix],
  );
  const tierSummary = useMemo(
    () => buildTierSummary(actionMatrixRows),
    [actionMatrixRows],
  );
  const lastSavedLabel = useMemo(
    () => formatRiskTierSnapshotLabel(lastSaved),
    [lastSaved],
  );
  const hasDirtyDraft = dirtyCells > 0;

  const setCellDraft = (
    actionClass: string,
    authority: MatrixAuthority,
    nextTier: RiskTier,
  ) => {
    setDraftMatrix((current) => {
      const next: Record<string, Record<string, string>> = {
        ...normalizeRiskTierMatrix(current),
      };
      const row = { ...(next[actionClass] ?? {}) };
      row[authority] = nextTier;
      next[actionClass] = row;
      return next;
    });
    setMatrixNotice(null);
    setMatrixError(null);
  };

  const handleReset = () => {
    setDraftMatrix(currentMatrix);
    setMatrixNotice(null);
    setMatrixError(null);
  };

  const handleSaveDraft = async () => {
    setMatrixSaving(true);
    setMatrixError(null);
    setMatrixNotice(null);
    try {
      const snapshot = await policyMatrix.save({
        matrix: draftMatrix,
        savedBy: savedBy ?? undefined,
      });
      const nextMatrix = normalizeRiskTierMatrix(snapshot.matrix);
      setCurrentMatrix(nextMatrix);
      setDraftMatrix(nextMatrix);
      setLastSaved(snapshot);
      setMatrixNotice('Risk-tier matrix draft saved.');
    } catch (error) {
      setMatrixError(error instanceof Error ? error.message : String(error));
    } finally {
      setMatrixSaving(false);
    }
  };

  return (
    <div
      data-testid="risk-tier-matrix-editor"
      className="space-y-3 rounded-lg border border-ds-border/60 bg-ds-surface/70 p-3"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[11px] font-medium text-ds-text">
            <ShieldAlert size={13} className="text-ds-muted" />
            {t('settings.policyStudio.riskTier.title')}
          </div>
          <p className="mt-1 max-w-3xl text-[11px] text-ds-muted">
            {t('settings.policyStudio.riskTier.description')}
            {tierSummary ? ` ${tierSummary}.` : ''}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleSaveDraft}
            data-testid="risk-tier-matrix-save-draft"
            disabled={!hasDirtyDraft || matrixSaving}
            className="rounded bg-ds-accent px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
          >
            {matrixSaving
              ? t('settings.policyStudio.riskTier.saving')
              : t('settings.policyStudio.riskTier.saveDraft')}
          </button>
          <button
            type="button"
            onClick={handleReset}
            data-testid="risk-tier-matrix-reset-current"
            disabled={!hasDirtyDraft || matrixSaving}
            className="rounded border border-ds-border px-3 py-1.5 text-xs text-ds-text disabled:opacity-50"
          >
            <span className="inline-flex items-center gap-1.5">
              <RotateCcw size={12} />
              {t('settings.policyStudio.riskTier.resetCurrent')}
            </span>
          </button>
          {matrixSaving && <Loader2 size={14} className="animate-spin text-ds-accent" />}
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-3 py-2">
          <div className="text-[10px] text-ds-muted">
            {t('settings.policyStudio.riskTier.dirtyCells')}
          </div>
          <div
            data-testid="risk-tier-matrix-dirty-count"
            className="mt-1 text-sm font-mono text-ds-text"
          >
            {dirtyCells}
          </div>
        </div>
        <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-3 py-2">
          <div className="text-[10px] text-ds-muted">
            {t('settings.policyStudio.riskTier.dirtyRows')}
          </div>
          <div className="mt-1 text-sm font-mono text-ds-text">{dirtyRows}</div>
        </div>
        <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-3 py-2">
          <div className="text-[10px] text-ds-muted">
            {t('settings.policyStudio.riskTier.lastSaved')}
          </div>
          <div className="mt-1 text-[10px] text-ds-text">
            {lastSavedLabel ?? t('settings.policyStudio.riskTier.noSavedDraft')}
          </div>
        </div>
        <div className="rounded border border-ds-border/70 bg-ds-bg/70 px-3 py-2">
          <div className="text-[10px] text-ds-muted">
            {t('settings.policyStudio.riskTier.savedBy')}
          </div>
          <div className="mt-1 text-xs text-ds-text">{savedBy ?? 'local-user'}</div>
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
          {t('settings.policyStudio.riskTier.emptyState')}
        </div>
      ) : (
        <>
          <div
            data-testid="risk-tier-matrix-diff"
            className="rounded border border-ds-border/70 bg-ds-bg/70 p-3"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 text-[11px] font-medium text-ds-text">
                  <ShieldAlert size={12} className="text-ds-muted" />
                  {t('settings.policyStudio.riskTier.diffTitle')}
                </div>
                <p className="mt-1 max-w-3xl text-[11px] text-ds-muted">
                  {t('settings.policyStudio.riskTier.diffDescription')}
                </p>
              </div>
              <div className="rounded border border-ds-border/70 bg-ds-surface/70 px-2 py-1 text-[10px] text-ds-muted">
                {dirtyCells} changed cell{dirtyCells === 1 ? '' : 's'}
              </div>
            </div>

            {matrixImpact && (
              <div className="mt-2 flex flex-wrap items-center gap-2 text-[10px] text-ds-muted">
                <span className="rounded border border-ds-border/70 bg-ds-surface/70 px-2 py-1">
                  +{matrixImpact.addedRows.length} added
                </span>
                <span className="rounded border border-ds-border/70 bg-ds-surface/70 px-2 py-1">
                  -{matrixImpact.removedRows.length} removed
                </span>
                <span className="rounded border border-ds-border/70 bg-ds-surface/70 px-2 py-1">
                  ~{matrixImpact.modifiedRows.length} modified
                </span>
                <span className="rounded border border-ds-border/70 bg-ds-surface/70 px-2 py-1">
                  {Object.keys(matrixImpact.historicalCounts).length} historical cells
                </span>
                <span className="rounded border border-ds-border/70 bg-ds-surface/70 px-2 py-1">
                  heuristic {matrixImpact.heuristicChangedCells}
                </span>
              </div>
            )}
          </div>

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
                      const persistedValue = currentMatrix[row.actionClass]?.[column.value] ?? null;
                      const draftValue = draftMatrix[row.actionClass]?.[column.value] ?? persistedValue;
                      const changed = persistedValue !== draftValue;
                      const currentLabel = formatRiskTierLabel(persistedValue);
                      const draftLabel = formatRiskTierLabel(draftValue);
                      const selectValue = coerceRiskTierValue(draftValue, 'T0');

                      return (
                        <td
                          key={`${row.actionClass}-${column.value}`}
                          className={`border-b border-ds-border/70 px-2 py-3 ${
                            changed ? 'bg-amber-400/5' : ''
                          }`}
                        >
                          <select
                            value={selectValue}
                            onChange={(event) =>
                              setCellDraft(
                                row.actionClass,
                                column.value,
                                event.target.value as RiskTier,
                              )
                            }
                            data-testid={`risk-tier-matrix-cell-${row.actionClass}-${column.value}`}
                            aria-label={`${row.actionClass} risk tier for ${column.label}`}
                            disabled={matrixSaving}
                            className={`w-full rounded border px-2 py-1.5 text-xs ${
                              changed
                                ? 'border-amber-400/40 bg-amber-400/5 text-ds-text'
                                : 'border-ds-border bg-ds-bg text-ds-text'
                            }`}
                          >
                            {RISK_TIER_OPTIONS.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>

                          <div className="mt-1.5 space-y-1 text-[10px] leading-4 text-ds-muted">
                            <div className="flex flex-wrap gap-1.5">
                              <span className={`rounded border px-1.5 py-0.5 ${getTierBadgeClass(currentLabel)}`}>
                                Current {currentLabel}
                              </span>
                              <span className={`rounded border px-1.5 py-0.5 ${getTierBadgeClass(draftLabel)}`}>
                                Draft {draftLabel}
                              </span>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                              <span className="rounded border border-ds-border/70 bg-ds-surface/70 px-1.5 py-0.5 text-ds-muted">
                                effective {currentLabel}
                              </span>
                              <span className="rounded border border-ds-border/70 bg-ds-surface/70 px-1.5 py-0.5 text-ds-muted">
                                draft {draftLabel}
                              </span>
                            </div>
                            <div>
                              {changed ? 'Draft differs from the persisted value.' : 'Draft matches the persisted value.'}
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

          <div className="rounded border border-ds-border/70 bg-ds-bg/70 p-3">
            <div className="flex flex-wrap items-center gap-2 text-[11px] font-medium text-ds-text">
              <Layers3 size={13} className="text-ds-muted" />
              {t('settings.policyStudio.riskTier.legend')}
            </div>
            <div className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
              {POLICY_RISK_TIER_DEFINITIONS.map((definition, index) => {
                const tier = `T${index}` as RiskTier;
                return (
                  <div
                    key={definition.value}
                    className={`rounded border px-3 py-2 ${getTierBadgeClass(tier)}`}
                  >
                    <div className="text-xs font-medium">{tier}</div>
                    <div className="mt-1 text-[10px] leading-4">{definition.summary}</div>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
