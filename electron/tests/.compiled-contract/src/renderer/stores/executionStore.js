"use strict";
/**
 * Execution state — Zustand store for status bar, model + mode + budget config.
 *
 * Replaces legacy `agentStore.ts`. Splits chat (chatStore) and runtime sessions
 * (runtimeStore) responsibility per cross_cutting/PLAN_02 Sub-Phase 1.2.
 *
 * Business logic lives in `domain/execution/executionState.ts` — the store is a
 * thin Zustand wrapper around pure reducers.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.useExecutionStore = void 0;
const zustand_1 = require("zustand");
const executionState_1 = require("../domain/execution/executionState");
exports.useExecutionStore = (0, zustand_1.create)((set) => ({
    ...(0, executionState_1.createExecutionState)(),
    setModel: (model) => set((s) => (0, executionState_1.reduceSetModel)(s, model)),
    setQualityPreset: (qualityPreset) => set((s) => (0, executionState_1.reduceSetQualityPreset)(s, qualityPreset)),
    setMode: (mode) => set((s) => (0, executionState_1.reduceSetMode)(s, mode)),
    setCost: (cost) => set((s) => (0, executionState_1.reduceSetCost)(s, cost)),
    setStep: (step) => set((s) => (0, executionState_1.reduceSetStep)(s, step)),
    setActiveSessions: (n) => set((s) => (0, executionState_1.reduceSetActiveSessions)(s, n)),
    setConnected: (v) => set((s) => (0, executionState_1.reduceSetConnected)(s, v)),
    updateFromStatus: (data) => set((s) => (0, executionState_1.reduceUpdateFromStatus)(s, data)),
}));
