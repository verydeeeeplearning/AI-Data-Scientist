/**
 * Workflow state — DS pipeline stages, quality scores, warnings, experiments, budget.
 */

import { create } from 'zustand';

export interface WorkflowStage {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'done' | 'error';
  score?: number;
}

export interface HarnessWarning {
  id: string;
  type: string;
  severity: 'high' | 'medium' | 'low';
  message: string;
  suggestion?: string;
  dismissed: boolean;
  timestamp: number;
}

export interface Experiment {
  id: string;
  model: string;
  isBaseline: boolean;
  metrics: Record<string, number>;
  cvStd?: number;
  trainingTime?: number;
  timestamp: number;
}

export interface BudgetDetail {
  tokensUsed: number;
  tokensMax: number;
  costUsd: number;
  costMax: number;
}

export interface ContextStatus {
  usedPct: number;
  compressed: boolean;
}

export interface ProfileResults {
  summary: string;
  grade: string;
  rows: number;
  columns: number;
  missingPct: number;
  issues: Array<{ issue: string; detail: string }>;
}

export interface ApprovalRequest {
  approvalId: string;
  sessionId: string;
  runId?: string | null;
  surface: string;
  question: string;
  kind: string;
  metadata: Record<string, unknown>;
  options: string[];
  default?: string | null;
  status: 'pending' | 'approved' | 'rejected';
  response?: string | null;
  source?: string | null;
  actor?: string | null;
  createdAt: number;
  updatedAt: number;
  resolvedAt?: number | null;
}

export interface SandboxViolationRecord {
  id: string;  // composed locally: `${tool}-${timestamp}-${kind}`
  kind: 'filesystem' | 'network' | 'subprocess' | 'resource';
  detail: string;
  blocked: boolean;
  tool: string;
  sessionId?: string | null;
  runId?: string | null;
  timestamp: number;  // ms since epoch
  acknowledged: boolean;
}

const VIOLATION_HISTORY_CAP = 50;
let violationCounter = 0;

export type SidebarTab = 'files' | 'workflow' | 'review' | 'runtime' | 'experiments' | 'portfolio' | 'learning';

interface WorkflowState {
  stages: WorkflowStage[];
  warnings: HarnessWarning[];
  experiments: Experiment[];
  approvals: ApprovalRequest[];
  sandboxViolations: SandboxViolationRecord[];
  overallQuality: { score: number; grade: string } | null;
  profileResults: ProfileResults | null;
  budget: BudgetDetail | null;
  context: ContextStatus | null;
  activeTab: SidebarTab;

  // Actions
  updateStage: (stageId: string, status: string, score?: number) => void;
  addWarning: (warning: Omit<HarnessWarning, 'dismissed' | 'timestamp'>) => void;
  dismissWarning: (id: string) => void;
  addExperiment: (exp: Experiment) => void;
  setApprovals: (approvals: ApprovalRequest[]) => void;
  upsertApproval: (approval: ApprovalRequest) => void;
  recordSandboxViolation: (
    violation: Omit<SandboxViolationRecord, 'id' | 'acknowledged'>
  ) => void;
  acknowledgeSandboxViolation: (id: string) => void;
  clearSandboxViolations: () => void;
  setProfileResults: (results: ProfileResults) => void;
  updateBudget: (budget: BudgetDetail) => void;
  updateContext: (ctx: ContextStatus) => void;
  setOverallQuality: (score: number, grade: string) => void;
  setActiveTab: (tab: SidebarTab) => void;
  resetWorkflow: () => void;
}

const DEFAULT_STAGES: WorkflowStage[] = [
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

export const useWorkflowStore = create<WorkflowState>((set) => ({
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

  updateStage: (stageId, status, score) =>
    set((s) => ({
      stages: s.stages.map((st) =>
        st.id === stageId
          ? { ...st, status: status as WorkflowStage['status'], score: score ?? st.score }
          : st
      ),
    })),

  addWarning: (w) =>
    set((s) => ({
      warnings: [
        ...s.warnings,
        { ...w, id: w.id || `warn-${++warningCounter}`, dismissed: false, timestamp: Date.now() },
      ],
    })),

  dismissWarning: (id) =>
    set((s) => ({
      warnings: s.warnings.map((w) => (w.id === id ? { ...w, dismissed: true } : w)),
    })),

  addExperiment: (exp) =>
    set((s) => ({
      experiments: [...s.experiments, exp],
    })),

  setApprovals: (approvals) => set({ approvals }),

  upsertApproval: (approval) =>
    set((s) => ({
      approvals: [
        approval,
        ...s.approvals.filter((item) => item.approvalId !== approval.approvalId),
      ].sort((a, b) => b.updatedAt - a.updatedAt),
    })),

  recordSandboxViolation: (violation) =>
    set((s) => {
      const id = `sv-${++violationCounter}`;
      const record: SandboxViolationRecord = { ...violation, id, acknowledged: false };
      return {
        sandboxViolations: [record, ...s.sandboxViolations].slice(0, VIOLATION_HISTORY_CAP),
      };
    }),

  acknowledgeSandboxViolation: (id) =>
    set((s) => ({
      sandboxViolations: s.sandboxViolations.map((v) =>
        v.id === id ? { ...v, acknowledged: true } : v
      ),
    })),

  clearSandboxViolations: () => set({ sandboxViolations: [] }),

  setProfileResults: (results) => set({ profileResults: results }),
  updateBudget: (budget) => set({ budget }),
  updateContext: (ctx) => set({ context: ctx }),
  setOverallQuality: (score, grade) => set({ overallQuality: { score, grade } }),
  setActiveTab: (tab) => set({ activeTab: tab }),

  resetWorkflow: () =>
    set({
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
