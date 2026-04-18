/**
 * Policy hook that keeps autonomous policy state in sync with backend RPCs.
 */

import { useCallback, useEffect } from 'react';
import {
  type ActionMatrixOverrideMap,
  type ActionMatrixOverrideRow,
  type ActionMatrixRowEntry,
  type MatrixAuthority,
  type MatrixVerdict,
  usePolicyStore,
  type PolicySnapshot,
  type RecurringGoalEntry,
} from '../stores/policyStore';

type OnFn = (event: string, handler: (payload: Record<string, unknown>) => void) => () => void;
export type PolicyRpcFn = (
  method: string,
  params?: Record<string, unknown>
) => Promise<Record<string, unknown>>;

const MATRIX_AUTHORITIES: MatrixAuthority[] = [
  'shadow',
  'supervised',
  'delegate',
  'autopilot',
  'incident',
  'freeze',
];

const MATRIX_VERDICTS = new Set<MatrixVerdict>(['auto', 'ask', 'approve', 'dual', 'skip']);

function isMatrixVerdict(value: unknown): value is MatrixVerdict {
  return typeof value === 'string' && MATRIX_VERDICTS.has(value as MatrixVerdict);
}

function normalizeActionMatrixOverrideRow(raw: unknown): ActionMatrixOverrideRow {
  if (!raw || typeof raw !== 'object') {
    return {};
  }

  const normalized: ActionMatrixOverrideRow = {};
  for (const authority of MATRIX_AUTHORITIES) {
    const value = (raw as Record<string, unknown>)[authority];
    if (isMatrixVerdict(value)) {
      normalized[authority] = value;
    }
  }
  return normalized;
}

function normalizeActionMatrixOverrides(raw: unknown): ActionMatrixOverrideMap {
  if (!raw || typeof raw !== 'object') {
    return {};
  }

  const normalized: ActionMatrixOverrideMap = {};
  for (const [actionClass, row] of Object.entries(raw as Record<string, unknown>)) {
    if (!actionClass.trim()) {
      continue;
    }
    const overrideRow = normalizeActionMatrixOverrideRow(row);
    if (Object.keys(overrideRow).length > 0) {
      normalized[actionClass] = overrideRow;
    }
  }
  return normalized;
}

function normalizeMatrixVerdictMap(raw: unknown): Record<MatrixAuthority, MatrixVerdict> {
  const normalized = {} as Record<MatrixAuthority, MatrixVerdict>;
  for (const authority of MATRIX_AUTHORITIES) {
    const value = raw && typeof raw === 'object'
      ? (raw as Record<string, unknown>)[authority]
      : null;
    normalized[authority] = isMatrixVerdict(value) ? value : 'approve';
  }
  return normalized;
}

function normalizeActionMatrixRows(raw: unknown): ActionMatrixRowEntry[] {
  if (!Array.isArray(raw)) {
    return [];
  }

  return raw
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
    .map((item) => ({
      actionClass: typeof item.actionClass === 'string' ? item.actionClass : 'unknown',
      dataSensitivity: typeof item.dataSensitivity === 'string' ? item.dataSensitivity : 'internal',
      writeSideEffect: typeof item.writeSideEffect === 'string' ? item.writeSideEffect : 'external',
      costImpact: typeof item.costImpact === 'string' ? item.costImpact : 'medium',
      reversibility: typeof item.reversibility === 'string' ? item.reversibility : 'soft_reversible',
      auditRequired: item.auditRequired === true,
      defaultVerdicts: normalizeMatrixVerdictMap(item.defaultVerdicts),
      effectiveVerdicts: normalizeMatrixVerdictMap(item.effectiveVerdicts),
      overrideVerdicts: normalizeActionMatrixOverrideRow(item.overrideVerdicts),
    }));
}

export function normalizePolicyPayload(payload: Record<string, unknown>): PolicySnapshot {
  const recurringGoals = Array.isArray(payload.recurringGoals)
    ? (payload.recurringGoals as RecurringGoalEntry[])
    : [];
  const standingOrders = Array.isArray(payload.standingOrders)
    ? payload.standingOrders.filter((item): item is string => typeof item === 'string')
    : [];
  const actionMatrixRows = normalizeActionMatrixRows(payload.actionMatrixRows);
  const actionMatrixOverrides = normalizeActionMatrixOverrides(payload.actionMatrixOverrides);
  const actionMatrixOverrideCount = typeof payload.actionMatrixOverrideCount === 'number'
    ? payload.actionMatrixOverrideCount
    : Object.values(actionMatrixOverrides).reduce(
      (count, row) => count + Object.keys(row).length,
      0,
    );

  return {
    automationProfile:
      (payload.automationProfile as 'manual' | 'balanced' | 'aggressive') ?? 'balanced',
    recurringGoals,
    standingOrders,
    actionMatrixRows,
    actionMatrixOverrides,
    actionMatrixOverrideCount,
  };
}

export async function fetchPolicySnapshot(rpc: PolicyRpcFn): Promise<PolicySnapshot> {
  const result = await rpc('policy.get');
  return normalizePolicyPayload(result);
}

export function usePolicy(on: OnFn, rpc: PolicyRpcFn, connected: boolean) {
  const setSnapshot = usePolicyStore((s) => s.setSnapshot);
  const markUpdated = usePolicyStore((s) => s.markUpdated);
  const resetPolicy = usePolicyStore((s) => s.resetPolicy);

  const refreshPolicy = useCallback(async () => {
    setSnapshot(await fetchPolicySnapshot(rpc));
    markUpdated();
  }, [markUpdated, rpc, setSnapshot]);

  useEffect(() => {
    if (!connected) {
      resetPolicy();
      return;
    }

    let cancelled = false;
    const guardedRefresh = async () => {
      try {
        await refreshPolicy();
      } catch (err) {
        if (!cancelled) {
          console.warn('[usePolicy] refresh failed:', err);
        }
      }
    };

    void guardedRefresh();
    const timer = window.setInterval(() => {
      void guardedRefresh();
    }, 5000);

    const unsubs = [
      on('stream.done', () => {
        void guardedRefresh();
      }),
      on('approval.requested', () => {
        void guardedRefresh();
      }),
      on('approval.resolved', () => {
        void guardedRefresh();
      }),
      on('workspace.changed', () => {
        void guardedRefresh();
      }),
    ];

    return () => {
      cancelled = true;
      window.clearInterval(timer);
      unsubs.forEach((unsub) => unsub());
    };
  }, [connected, on, refreshPolicy, resetPolicy]);
}
