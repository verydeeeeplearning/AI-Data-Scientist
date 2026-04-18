/**
 * Runtime operator state for sessions, runs, tasks, and gateway status.
 */

import { create } from 'zustand';

export interface RuntimeStatusSnapshot {
  model: string;
  mode: 'auto' | 'supervised' | 'step-by-step';
  activeSessions: number;
  activeRuns: number;
  activeTasks: number;
  pendingApprovals: number;
  autonomousRuntimeEnabled: boolean;
  autonomousRuntimeRunning: boolean;
  sensorBacklog: number;
  recoveredSessions: number;
  automationProfile: 'manual' | 'balanced' | 'aggressive';
  recurringGoalCount: number;
  standingOrderCount: number;
  resourcePressure: boolean;
  authorityOverlay: 'incident' | 'freeze' | null;
  authorityOverlayStartedAt?: string | null;
  authorityOverlayExpiresAt?: string | null;
  effectiveAuthorityMode?: string;
}

export interface RuntimeSessionEntry {
  sessionId: string;
  sessionLabel?: string | null;
  conversationId?: string | null;
  threadId?: string | null;
  threadLabel?: string | null;
  surface: string;
  createdAt: number;
  lastActive: number;
  lastRunId?: string | null;
}

export interface RuntimeRunEntry {
  runId: string;
  sessionId: string;
  sessionLabel?: string | null;
  conversationId?: string | null;
  threadId?: string | null;
  threadLabel?: string | null;
  surface: string;
  status: 'running' | 'succeeded' | 'failed' | 'cancelled';
  message: string;
  taskId?: string | null;
  error?: string | null;
  resultPreview?: string | null;
  costUsd: number;
  createdAt: number;
  startedAt: number;
  finishedAt?: number | null;
}

export interface RuntimeTaskEntry {
  taskId: string;
  runId: string;
  status: 'running' | 'succeeded' | 'failed' | 'cancelled';
  createdAt: number;
  startedAt: number;
  finishedAt?: number | null;
  error?: string | null;
}

interface RuntimeState {
  status: RuntimeStatusSnapshot | null;
  sessions: RuntimeSessionEntry[];
  runs: RuntimeRunEntry[];
  tasks: RuntimeTaskEntry[];
  lastUpdatedAt: number | null;
  selectedRunId: string | null;

  setStatus: (status: RuntimeStatusSnapshot | null) => void;
  setSessions: (sessions: RuntimeSessionEntry[]) => void;
  setRuns: (runs: RuntimeRunEntry[]) => void;
  setTasks: (tasks: RuntimeTaskEntry[]) => void;
  selectRun: (runId: string) => void;
  clearSelectedRun: () => void;
  markUpdated: () => void;
  resetRuntime: () => void;
}

export const useRuntimeStore = create<RuntimeState>((set) => ({
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
  resetRuntime: () =>
    set({
      status: null,
      sessions: [],
      runs: [],
      tasks: [],
      lastUpdatedAt: null,
      selectedRunId: null,
    }),
}));
