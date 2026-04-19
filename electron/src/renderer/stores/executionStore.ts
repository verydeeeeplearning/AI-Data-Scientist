/**
 * Execution state — Zustand store for status bar, model + mode + budget config.
 *
 * Replaces legacy `agentStore.ts`. Splits chat (chatStore) and runtime sessions
 * (runtimeStore) responsibility per cross_cutting/PLAN_02 Sub-Phase 1.2.
 *
 * Business logic lives in `domain/execution/executionState.ts` — the store is a
 * thin Zustand wrapper around pure reducers.
 */

import { create } from 'zustand';
import {
  createExecutionState,
  reduceSetActiveSessions,
  reduceSetConnected,
  reduceSetCost,
  reduceSetMode,
  reduceSetModel,
  reduceSetQualityPreset,
  reduceSetStep,
  reduceUpdateFromStatus,
  type ExecutionMode,
  type ExecutionState,
  type QualityPreset,
} from '../domain/execution/executionState';

interface ExecutionStore extends ExecutionState {
  setModel: (model: string) => void;
  setQualityPreset: (preset: QualityPreset) => void;
  setMode: (mode: ExecutionMode) => void;
  setCost: (cost: number) => void;
  setStep: (step: number) => void;
  setActiveSessions: (n: number) => void;
  setConnected: (v: boolean) => void;
  updateFromStatus: (data: Record<string, unknown>) => void;
}

export const useExecutionStore = create<ExecutionStore>((set) => ({
  ...createExecutionState(),

  setModel: (model) => set((s) => reduceSetModel(s, model)),
  setQualityPreset: (qualityPreset) => set((s) => reduceSetQualityPreset(s, qualityPreset)),
  setMode: (mode) => set((s) => reduceSetMode(s, mode)),
  setCost: (cost) => set((s) => reduceSetCost(s, cost)),
  setStep: (step) => set((s) => reduceSetStep(s, step)),
  setActiveSessions: (n) => set((s) => reduceSetActiveSessions(s, n)),
  setConnected: (v) => set((s) => reduceSetConnected(s, v)),
  updateFromStatus: (data) => set((s) => reduceUpdateFromStatus(s, data)),
}));

export type { ExecutionMode, QualityPreset };
