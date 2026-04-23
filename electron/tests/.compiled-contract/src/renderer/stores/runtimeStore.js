"use strict";
/**
 * Runtime operator state for sessions, runs, tasks, and gateway status.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.useRuntimeStore = void 0;
const zustand_1 = require("zustand");
exports.useRuntimeStore = (0, zustand_1.create)((set) => ({
    status: null,
    sessions: [],
    runs: [],
    tasks: [],
    lastUpdatedAt: null,
    selectedRunId: null,
    setStatus: (status) => set({ status }),
    setSessions: (sessions) => set({ sessions }),
    setRuns: (runs) => set({ runs }),
    setTasks: (tasks) => set({ tasks }),
    selectRun: (runId) => set({ selectedRunId: runId }),
    clearSelectedRun: () => set({ selectedRunId: null }),
    markUpdated: () => set({ lastUpdatedAt: Date.now() }),
    resetRuntime: () => set({
        status: null,
        sessions: [],
        runs: [],
        tasks: [],
        lastUpdatedAt: null,
        selectedRunId: null,
    }),
}));
