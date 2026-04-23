"use strict";
/**
 * Workflow state — DS pipeline stages, quality scores, warnings, experiments, budget.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.useWorkflowStore = void 0;
const zustand_1 = require("zustand");
const VIOLATION_HISTORY_CAP = 50;
let violationCounter = 0;
const DEFAULT_STAGES = [
    { id: 'scoping', label: 'Scoping', status: 'pending' },
    { id: 'data_loading', label: 'Data Loading', status: 'pending' },
    { id: 'profiling', label: 'Profiling', status: 'pending' },
    { id: 'eda', label: 'EDA', status: 'pending' },
    { id: 'feature_eng', label: 'Feature Eng', status: 'pending' },
    { id: 'modeling', label: 'Modeling', status: 'pending' },
    { id: 'evaluation', label: 'Evaluation', status: 'pending' },
    { id: 'reporting', label: 'Reporting', status: 'pending' },
];
let warningCounter = 0;
exports.useWorkflowStore = (0, zustand_1.create)((set) => ({
    stages: DEFAULT_STAGES.map((s) => ({ ...s })),
    warnings: [],
    experiments: [],
    approvals: [],
    sandboxViolations: [],
    overallQuality: null,
    profileResults: null,
    budget: null,
    context: null,
    activeTab: 'files',
    updateStage: (stageId, status, score) => set((s) => ({
        stages: s.stages.map((st) => st.id === stageId
            ? { ...st, status: status, score: score ?? st.score }
            : st),
    })),
    addWarning: (w) => set((s) => ({
        warnings: [
            ...s.warnings,
            { ...w, id: w.id || `warn-${++warningCounter}`, dismissed: false, timestamp: Date.now() },
        ],
    })),
    dismissWarning: (id) => set((s) => ({
        warnings: s.warnings.map((w) => (w.id === id ? { ...w, dismissed: true } : w)),
    })),
    addExperiment: (exp) => set((s) => ({
        experiments: [...s.experiments, exp],
    })),
    setApprovals: (approvals) => set({ approvals }),
    upsertApproval: (approval) => set((s) => ({
        approvals: [
            approval,
            ...s.approvals.filter((item) => item.approvalId !== approval.approvalId),
        ].sort((a, b) => b.updatedAt - a.updatedAt),
    })),
    recordSandboxViolation: (violation) => set((s) => {
        const id = `sv-${++violationCounter}`;
        const record = { ...violation, id, acknowledged: false };
        return {
            sandboxViolations: [record, ...s.sandboxViolations].slice(0, VIOLATION_HISTORY_CAP),
        };
    }),
    acknowledgeSandboxViolation: (id) => set((s) => ({
        sandboxViolations: s.sandboxViolations.map((v) => v.id === id ? { ...v, acknowledged: true } : v),
    })),
    clearSandboxViolations: () => set({ sandboxViolations: [] }),
    setProfileResults: (results) => set({ profileResults: results }),
    updateBudget: (budget) => set({ budget }),
    updateContext: (ctx) => set({ context: ctx }),
    setOverallQuality: (score, grade) => set({ overallQuality: { score, grade } }),
    setActiveTab: (tab) => set({ activeTab: tab }),
    resetWorkflow: () => set({
        stages: DEFAULT_STAGES.map((s) => ({ ...s })),
        warnings: [],
        experiments: [],
        approvals: [],
        sandboxViolations: [],
        overallQuality: null,
        profileResults: null,
        budget: null,
        context: null,
    }),
}));
