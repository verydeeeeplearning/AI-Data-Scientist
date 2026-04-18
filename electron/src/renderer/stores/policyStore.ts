/**
 * Policy state for autonomous runtime configuration surfaced in Electron.
 */

import { create } from 'zustand';

export interface RecurringGoalEntry {
  goalId: string;
  sessionId: string;
  prompt: string;
  intervalSeconds: number;
  enabled: boolean;
  lastTriggeredAt?: number | null;
  createdAt: number;
  updatedAt: number;
}

export type MatrixAuthority =
  | 'shadow'
  | 'supervised'
  | 'delegate'
  | 'autopilot'
  | 'incident'
  | 'freeze';

export type MatrixVerdict = 'auto' | 'ask' | 'approve' | 'dual' | 'skip';

export type ActionMatrixOverrideRow = Partial<Record<MatrixAuthority, MatrixVerdict>>;
export type ActionMatrixOverrideMap = Record<string, ActionMatrixOverrideRow>;

export interface ActionMatrixRowEntry {
  actionClass: string;
  dataSensitivity: string;
  writeSideEffect: string;
  costImpact: string;
  reversibility: string;
  auditRequired: boolean;
  defaultVerdicts: Record<MatrixAuthority, MatrixVerdict>;
  effectiveVerdicts: Record<MatrixAuthority, MatrixVerdict>;
  overrideVerdicts: ActionMatrixOverrideRow;
}

export interface PolicySnapshot {
  automationProfile: 'manual' | 'balanced' | 'aggressive';
  recurringGoals: RecurringGoalEntry[];
  standingOrders: string[];
  actionMatrixRows: ActionMatrixRowEntry[];
  actionMatrixOverrides: ActionMatrixOverrideMap;
  actionMatrixOverrideCount: number;
}

interface PolicyState {
  snapshot: PolicySnapshot | null;
  lastUpdatedAt: number | null;

  setSnapshot: (snapshot: PolicySnapshot | null) => void;
  markUpdated: () => void;
  resetPolicy: () => void;
}

export const usePolicyStore = create<PolicyState>((set) => ({
  snapshot: null,
  lastUpdatedAt: null,

  setSnapshot: (snapshot) => set({ snapshot }),
  markUpdated: () => set({ lastUpdatedAt: Date.now() }),
  resetPolicy: () =>
    set({
      snapshot: null,
      lastUpdatedAt: null,
    }),
}));
