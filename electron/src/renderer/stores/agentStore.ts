/**
 * Agent state — Zustand store for status bar and sidebar.
 */

import { create } from 'zustand';
import { normalizeQualityPreset, type QualityPreset } from '../utils/qualityPreset';

interface AgentState {
  model: string;
  qualityPreset: QualityPreset;
  mode: 'auto' | 'supervised' | 'step-by-step';
  cost: number;
  step: number;
  activeSessions: number;
  connected: boolean;

  setModel: (model: string) => void;
  setQualityPreset: (preset: QualityPreset) => void;
  setMode: (mode: 'auto' | 'supervised' | 'step-by-step') => void;
  setCost: (cost: number) => void;
  setStep: (step: number) => void;
  setActiveSessions: (n: number) => void;
  setConnected: (v: boolean) => void;
  updateFromStatus: (data: Record<string, unknown>) => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  model: 'anthropic/claude-sonnet-4-6',
  qualityPreset: 'balanced',
  mode: 'auto',
  cost: 0,
  step: 0,
  activeSessions: 0,
  connected: false,

  setModel: (model) => set({ model }),
  setQualityPreset: (qualityPreset) => set({ qualityPreset }),
  setMode: (mode) => set({ mode }),
  setCost: (cost) => set({ cost }),
  setStep: (step) => set({ step }),
  setActiveSessions: (n) => set({ activeSessions: n }),
  setConnected: (v) => set({ connected: v }),

  updateFromStatus: (data) => {
    set((s) => ({
      model: (data.model as string) ?? s.model,
      qualityPreset: normalizeQualityPreset(data.qualityPreset),
      mode: (data.mode as 'auto' | 'supervised' | 'step-by-step') ?? s.mode,
      activeSessions: (data.activeSessions as number) ?? s.activeSessions,
    }));
  },
}));
