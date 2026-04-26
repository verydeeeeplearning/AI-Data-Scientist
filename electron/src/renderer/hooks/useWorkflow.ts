/**
 * Workflow hook — subscribes to DS workflow events and updates workflowStore.
 *
 * Event payload shapes are defined in ``types/events.ts`` (canonical contract).
 */

import { useCallback, useEffect, useRef } from 'react';
import type {
  ApprovalEvent,
  BudgetDetailEvent,
  BudgetWarningEvent,
  ContextStatusEvent,
  ExperimentLogEvent,
  HarnessWarningEvent,
  ProfileResultsEvent,
  QualityUpdateEvent,
  SandboxViolationEvent,
  WorkflowStepEvent,
} from '../types/events';
import { useWorkflowStore } from '../stores/workflowStore';
import { useVisiblePolling } from './useVisiblePolling';

type OnFn = (event: string, handler: (payload: Record<string, unknown>) => void) => () => void;
type RpcFn = (method: string, params?: Record<string, unknown>) => Promise<Record<string, unknown>>;

function cast<T>(payload: Record<string, unknown>): T {
  return payload as unknown as T;
}

export function useWorkflow(on: OnFn, rpc: RpcFn, connected: boolean) {
  const updateStage = useWorkflowStore((s) => s.updateStage);
  const addWarning = useWorkflowStore((s) => s.addWarning);
  const addExperiment = useWorkflowStore((s) => s.addExperiment);
  const setApprovals = useWorkflowStore((s) => s.setApprovals);
  const upsertApproval = useWorkflowStore((s) => s.upsertApproval);
  const setProfileResults = useWorkflowStore((s) => s.setProfileResults);
  const updateBudget = useWorkflowStore((s) => s.updateBudget);
  const updateContext = useWorkflowStore((s) => s.updateContext);
  const setOverallQuality = useWorkflowStore((s) => s.setOverallQuality);
  const recordSandboxViolation = useWorkflowStore((s) => s.recordSandboxViolation);
  const approvalRefreshGenerationRef = useRef(0);

  const loadApprovals = useCallback(async () => {
    const generation = approvalRefreshGenerationRef.current;
    try {
      const result = await rpc('approval.list', { limit: 20 });
      if (approvalRefreshGenerationRef.current === generation) {
        setApprovals((result.approvals as unknown as ApprovalEvent[]) ?? []);
      }
    } catch (err) {
      if (approvalRefreshGenerationRef.current === generation) {
        console.warn('[useWorkflow] approval.list failed:', err);
      }
    }
  }, [rpc, setApprovals]);

  useEffect(() => {
    const unsubs = [
      on('workflow.step', (payload) => {
        const e = cast<WorkflowStepEvent>(payload);
        updateStage(e.stage, e.status, e.score);
      }),

      on('quality.update', (payload) => {
        const e = cast<QualityUpdateEvent>(payload);
        updateStage(e.stage, 'done', e.score);
        if (typeof e.overall === 'number' && typeof e.grade === 'string') {
          setOverallQuality(e.overall, e.grade);
        }
      }),

      on('harness.warning', (payload) => {
        const e = cast<HarnessWarningEvent>(payload);
        addWarning({
          id: e.id ?? '',
          type: e.type ?? 'unknown',
          severity: e.severity ?? 'medium',
          message: e.message ?? '',
          suggestion: e.suggestion,
        });
      }),

      on('experiment.log', (payload) => {
        const e = cast<ExperimentLogEvent>(payload);
        addExperiment({
          id: e.id ?? `exp-${Date.now()}`,
          model: e.model ?? 'unknown',
          isBaseline: e.isBaseline ?? false,
          metrics: e.metrics ?? {},
          trainingTime: e.trainingTime,
          timestamp: e.timestamp ?? Date.now(),
        });
      }),

      on('profile.results', (payload) => {
        const e = cast<ProfileResultsEvent>(payload);
        setProfileResults({
          summary: e.summary ?? '',
          grade: e.grade ?? 'C',
          rows: e.rows ?? 0,
          columns: e.columns ?? 0,
          missingPct: e.missingPct ?? 0,
          issues: e.issues ?? [],
        });
      }),

      on('budget.detail', (payload) => {
        const e = cast<BudgetDetailEvent>(payload);
        updateBudget({
          tokensUsed: e.tokensUsed ?? 0,
          tokensMax: e.tokensMax ?? 200000,
          costUsd: e.costUsd ?? 0,
          costMax: e.costMax ?? 10,
        });
      }),

      on('budget.warning', (payload) => {
        const e = cast<BudgetWarningEvent>(payload);
        addWarning({
          id: `budget-${e.level ?? 'warning'}-${Math.round(e.pct ?? 0)}`,
          type: 'budget',
          severity: e.level === 'exhausted' ? 'high' : 'medium',
          message: e.message ?? 'Budget warning',
          suggestion: e.level === 'exhausted'
            ? 'Increase the monthly budget in Settings to start another analysis.'
            : 'Review the monthly budget before launching another expensive run.',
        });
      }),

      on('context.status', (payload) => {
        const e = cast<ContextStatusEvent>(payload);
        updateContext({
          usedPct: e.usedPct ?? 0,
          compressed: e.compressed ?? false,
        });
      }),

      on('approval.requested', (payload) => {
        const e = cast<ApprovalEvent>(payload);
        upsertApproval(e);
      }),

      on('approval.resolved', (payload) => {
        const e = cast<ApprovalEvent>(payload);
        upsertApproval(e);
      }),

      on('sandbox.violation', (payload) => {
        const e = cast<SandboxViolationEvent>(payload);
        recordSandboxViolation({
          kind: e.kind,
          detail: e.detail,
          blocked: e.blocked,
          tool: e.tool,
          sessionId: e.sessionId ?? null,
          runId: e.runId ?? null,
          // backend emits seconds; store uses ms
          timestamp: Math.round((e.timestamp ?? Date.now() / 1000) * 1000),
        });
      }),
    ];

    return () => {
      unsubs.forEach((fn) => fn());
    };
  }, [
    on,
    updateStage,
    addWarning,
    addExperiment,
    upsertApproval,
    recordSandboxViolation,
    setProfileResults,
    updateBudget,
    updateContext,
    setOverallQuality,
  ]);

  useEffect(() => {
    approvalRefreshGenerationRef.current += 1;
    if (!connected) {
      setApprovals([]);
    }

    return () => {
      approvalRefreshGenerationRef.current += 1;
    };
  }, [connected, loadApprovals, setApprovals]);

  useVisiblePolling(() => {
    void loadApprovals();
  }, { intervalMs: 3000, enabled: connected });
}
