import { Plus, RefreshCcw, ShieldCheck, Siren } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useWs } from '../../hooks/WsProvider';
import { InlineError, OverviewStat, StatusLine } from './DecisionOsReviewPrimitives';
import { PromotionGateModal } from './PromotionGateModal';
import { RunDiffPanel } from './RunDiffPanel';
import { SharedSkillReviewPanel } from './SharedSkillReviewPanel';
import {
  DecisionOsOverview,
  formatDate,
  modelOptionLabel,
  PostDeployStatusResult,
  severityClass,
} from './decisionOsReviewModel';

export function ReviewTab() {
  const { on, rpc, status } = useWs();
  const connected = status === 'connected';

  const [overview, setOverview] = useState<DecisionOsOverview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decisionActionError, setDecisionActionError] = useState<string | null>(null);
  const [applyingDecisionId, setApplyingDecisionId] = useState<string | null>(null);

  const [promotionModalOpen, setPromotionModalOpen] = useState(false);
  const [promotionSeedRunId, setPromotionSeedRunId] = useState<string | null>(null);

  const [modelId, setModelId] = useState('');
  const [windowValue, setWindowValue] = useState('7d');
  const [statusBusy, setStatusBusy] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [statusResult, setStatusResult] = useState<PostDeployStatusResult | null>(null);

  const refreshOverview = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await rpc('decisionOs.overview', {
        runLimit: 20,
        modelLimit: 20,
        decisionLimit: 20,
      });
      setOverview(payload as unknown as DecisionOsOverview);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!connected) {
      setOverview(null);
      setStatusResult(null);
      return;
    }

    let cancelled = false;
    const guardedRefresh = async () => {
      if (!cancelled) {
        await refreshOverview();
      }
    };

    void guardedRefresh();
    const timer = window.setInterval(() => {
      void guardedRefresh();
    }, 5000);

    const unsubs = [
      on('runtime.alert', () => {
        void guardedRefresh();
      }),
      on('workspace.changed', () => {
        void guardedRefresh();
      }),
      on('stream.done', () => {
        void guardedRefresh();
      }),
    ];

    return () => {
      cancelled = true;
      window.clearInterval(timer);
      unsubs.forEach((unsub) => unsub());
    };
  }, [connected, on, rpc]);

  useEffect(() => {
    if (!overview) {
      return;
    }
    const modelIds = new Set(overview.models.map((model) => model.model_id));
    if (!modelIds.has(modelId)) {
      setModelId(overview.models[0]?.model_id ?? '');
    }
  }, [modelId, overview]);

  const latestDecisions = overview?.promotionDecisions.slice(0, 3) ?? [];
  const latestMonitorStates = overview?.monitorStates.slice(0, 3) ?? [];
  const defaultRollbackPlanRef =
    overview?.promotionDecisions[0]?.rollback_plan_ref ?? 'registry/rollback/churn.yaml';

  const openPromotionModal = (candidateRunId?: string | null) => {
    setPromotionSeedRunId(candidateRunId ?? overview?.runs[0]?.run_id ?? null);
    setPromotionModalOpen(true);
  };

  const applyPromotion = async (decisionId: string, candidateModelId: string) => {
    setDecisionActionError(null);
    setApplyingDecisionId(decisionId);
    try {
      await rpc('decisionOs.applyPromotion', { decisionId });
      setModelId(candidateModelId);
      await refreshOverview();
    } catch (err) {
      setDecisionActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setApplyingDecisionId(null);
    }
  };

  const loadPostDeployStatus = async () => {
    if (!modelId) {
      setStatusError('Select a model.');
      return;
    }
    setStatusBusy(true);
    setStatusError(null);
    try {
      const payload = await rpc('decisionOs.getPostDeployStatus', {
        modelId,
        window: windowValue,
      });
      setStatusResult(payload as unknown as PostDeployStatusResult);
    } catch (err) {
      setStatusError(err instanceof Error ? err.message : String(err));
    } finally {
      setStatusBusy(false);
    }
  };

  const selectedModel = useMemo(
    () => overview?.models.find((model) => model.model_id === modelId) ?? null,
    [modelId, overview],
  );

  return (
    <>
      <div data-testid="decision-os-review-tab" className="space-y-3 px-3 py-2">
        <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
          <ShieldCheck size={12} />
          Review
          <button
            onClick={() => void refreshOverview()}
            disabled={!connected || loading}
            data-testid="decision-os-refresh"
            className="ml-auto inline-flex items-center gap-1 rounded border border-ds-border px-2 py-1 text-[10px] normal-case text-ds-muted hover:text-ds-text disabled:opacity-50"
          >
            <RefreshCcw size={10} />
            Refresh
          </button>
        </div>

        {error && <InlineError message={error} />}
        {decisionActionError && <InlineError message={decisionActionError} />}

        <section
          data-testid="decision-os-overview"
          className="space-y-2 rounded-md border border-ds-border bg-ds-bg/70 p-3"
        >
          <div className="flex items-center justify-between gap-2">
            <div className="text-xs font-semibold text-ds-text">Decision OS Overview</div>
            <button
              onClick={() => openPromotionModal()}
              disabled={!connected || (overview?.runs.length ?? 0) === 0}
              data-testid="decision-os-open-promotion"
              className="inline-flex items-center gap-1 rounded border border-ds-accent px-2 py-1 text-[10px] text-ds-accent hover:bg-ds-accent/10 disabled:opacity-50"
            >
              <Plus size={10} />
              Open promotion gate
            </button>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <OverviewStat
              label="Runs"
              value={overview?.summary.runCount ?? 0}
              testId="decision-os-overview-run-count"
            />
            <OverviewStat
              label="Models"
              value={overview?.summary.modelCount ?? 0}
              testId="decision-os-overview-model-count"
            />
            <OverviewStat
              label="Decisions"
              value={overview?.summary.decisionCount ?? 0}
              testId="decision-os-overview-decision-count"
            />
            <OverviewStat
              label="Monitors"
              value={overview?.summary.monitorStateCount ?? 0}
              testId="decision-os-overview-monitor-count"
            />
          </div>

          <div className="grid gap-2 lg:grid-cols-2">
            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wider text-ds-muted">
                Latest decisions
              </div>
              {latestDecisions.length === 0 ? (
                <div className="text-xs text-ds-muted">No promotion decisions yet.</div>
              ) : (
                <div className="space-y-2">
                  {latestDecisions.map((decision) => (
                    <div
                      key={decision.decision_id}
                      className="rounded border border-ds-border/70 bg-ds-surface/60 p-2"
                    >
                      <button
                        onClick={() => openPromotionModal(decision.candidate_run_id)}
                        className="w-full text-left"
                      >
                        <div className="flex items-center gap-2 text-xs text-ds-text">
                          <span className="font-mono">{decision.candidate_run_id}</span>
                          <span
                            className={`rounded border px-1.5 py-0.5 text-[10px] ${severityClass(decision.chain_state)}`}
                          >
                            {decision.chain_state}
                          </span>
                        </div>
                        <div className="mt-1 text-[10px] text-ds-muted">
                          {decision.target_stage} {'->'} {decision.candidate_model_id}
                        </div>
                      </button>
                      {decision.chain_state === 'approved' ? (
                        <button
                          onClick={() =>
                            void applyPromotion(
                              decision.decision_id,
                              decision.candidate_model_id,
                            )
                          }
                          disabled={!connected || applyingDecisionId === decision.decision_id}
                          data-testid={`decision-os-apply-${decision.decision_id}`}
                          className="mt-2 rounded border border-ds-success/40 px-2 py-1 text-[10px] text-ds-success hover:bg-ds-success/10 disabled:opacity-50"
                        >
                          {applyingDecisionId === decision.decision_id ? 'Applying...' : 'Apply'}
                        </button>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wider text-ds-muted">
                Latest monitor states
              </div>
              {latestMonitorStates.length === 0 ? (
                <div className="text-xs text-ds-muted">No post-deploy observations yet.</div>
              ) : (
                <div className="space-y-2">
                  {latestMonitorStates.map((monitorState) => (
                    <div
                      key={`${monitorState.model_id}:${monitorState.observed_at}`}
                      className="rounded border border-ds-border/70 bg-ds-surface/60 p-2"
                    >
                      <div className="flex items-center gap-2 text-xs text-ds-text">
                        <span className="font-mono">{monitorState.model_id}</span>
                        <span
                          className={`rounded border px-1.5 py-0.5 text-[10px] ${severityClass(monitorState.overall_status)}`}
                        >
                          {monitorState.overall_status}
                        </span>
                      </div>
                      <div className="mt-1 text-[10px] text-ds-muted">
                        {monitorState.remediation.decision} / {monitorState.trigger_mode} /{' '}
                        {formatDate(monitorState.observed_at)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>

        <SharedSkillReviewPanel runs={overview?.runs ?? []} />

        <RunDiffPanel
          runs={overview?.runs ?? []}
          connected={connected}
          onOpenPromotionModal={(candidateRunId) => openPromotionModal(candidateRunId)}
        />

        <section
          data-testid="decision-os-post-deploy"
          className="space-y-2 rounded-md border border-ds-border bg-ds-bg/70 p-3"
        >
          <div className="flex items-center gap-2 text-xs font-semibold text-ds-text">
            <Siren size={14} />
            Post-deploy Monitor
          </div>
          <div className="grid gap-2">
            <select
              value={modelId}
              onChange={(event) => setModelId(event.target.value)}
              aria-label="Model selected for post-deploy monitoring"
              data-testid="decision-os-post-deploy-model"
              className="rounded border border-ds-border bg-ds-surface px-2 py-1.5 text-xs text-ds-text"
            >
              <option value="">Select model</option>
              {(overview?.models ?? []).map((model) => (
                <option key={`${model.model_id}:${model.version}`} value={model.model_id}>
                  {modelOptionLabel(model)}
                </option>
              ))}
            </select>
            <input
              value={windowValue}
              onChange={(event) => setWindowValue(event.target.value)}
              placeholder="7d"
              data-testid="decision-os-post-deploy-window"
              className="rounded border border-ds-border bg-ds-surface px-2 py-1.5 text-xs text-ds-text"
            />
            <button
              onClick={() => void loadPostDeployStatus()}
              disabled={statusBusy || !connected}
              data-testid="decision-os-post-deploy-load"
              className="rounded bg-ds-accent px-2 py-1.5 text-xs text-white disabled:opacity-50"
            >
              {statusBusy ? 'Loading...' : 'Load status'}
            </button>
          </div>
          {statusError && <InlineError message={statusError} />}
          {statusResult && (
            <div data-testid="decision-os-post-deploy-result" className="space-y-2">
              <div className="rounded border border-ds-border/70 bg-ds-surface/60 p-2">
                <div className="flex items-center gap-2 text-xs text-ds-text">
                  <span className="font-mono">{statusResult.model_id}</span>
                  <span
                    className={`rounded border px-1.5 py-0.5 text-[10px] ${severityClass(statusResult.summary.overall_status)}`}
                  >
                    {statusResult.summary.overall_status}
                  </span>
                </div>
                <div className="mt-1 text-[10px] text-ds-muted">
                  {statusResult.observations} observations / {statusResult.window} /{' '}
                  {formatDate(statusResult.summary.observed_at)}
                </div>
              </div>
              <div className="grid gap-2 md:grid-cols-2">
                <StatusLine
                  label="Selected model"
                  value={selectedModel ? modelOptionLabel(selectedModel) : statusResult.model_id}
                />
                <StatusLine
                  label="Remediation"
                  value={`${statusResult.summary.remediation.decision} (${statusResult.summary.remediation.severity})`}
                />
                <StatusLine
                  label="Drift"
                  value={`PSI ${statusResult.summary.drift.max_psi ?? '-'} / KS ${statusResult.summary.drift.max_ks ?? '-'}`}
                />
                <StatusLine
                  label="Service level"
                  value={`${statusResult.summary.service_level.status} / p95 ${statusResult.summary.service_level.latency_p95_ms ?? '-'} ms`}
                />
              </div>
              {statusResult.alerts.length > 0 ? (
                <div data-testid="decision-os-post-deploy-alerts" className="space-y-1">
                  {statusResult.alerts.map((alert) => (
                    <div
                      key={alert}
                      className="rounded border border-ds-error/30 bg-ds-error/10 px-2 py-1 text-[10px] text-ds-error"
                    >
                      {alert}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          )}
        </section>
      </div>

      <PromotionGateModal
        open={promotionModalOpen}
        connected={connected}
        runs={overview?.runs ?? []}
        initialCandidateRunId={promotionSeedRunId}
        defaultRollbackPlanRef={defaultRollbackPlanRef}
        onClose={() => setPromotionModalOpen(false)}
        onSubmitted={refreshOverview}
      />
    </>
  );
}
