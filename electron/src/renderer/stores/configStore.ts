/**
 * Config + UI state — Zustand store for settings, theme, and onboarding.
 */

import { create } from 'zustand';

export type Theme = 'dark' | 'light';

const ONBOARDING_STORAGE_KEY = 'ds-agent-onboarded-v2';
const LEGACY_ONBOARDING_STORAGE_KEY = 'ds-agent-onboarded';

interface ConfigState {
  // Onboarding
  isFirstRun: boolean;
  showOnboarding: boolean;

  // Settings panel
  showSettings: boolean;

  // Theme
  theme: Theme;

  // Budget
  maxBudgetUsd: number;
  budgetWarningThresholdPct: number;

  // Cross-component handoff: chat input pre-fill from onboarding starter prompt.
  // Pending until the next ChatInput mount consumes it via consumePendingStarterPrompt().
  pendingStarterPrompt: string | null;

  // Actions
  setFirstRun: (v: boolean) => void;
  setShowOnboarding: (v: boolean) => void;
  setShowSettings: (v: boolean) => void;
  setTheme: (t: Theme) => void;
  toggleTheme: () => void;
  setMaxBudget: (v: number) => void;
  setBudgetWarningThresholdPct: (v: number) => void;
  setPendingStarterPrompt: (v: string | null) => void;
  consumePendingStarterPrompt: () => string | null;
  resetOnboarding: () => void;
}

function loadTheme(): Theme {
  try {
    return (localStorage.getItem('ds-agent-theme') as Theme) || 'dark';
  } catch {
    return 'dark';
  }
}

function persistTheme(theme: Theme): void {
  try {
    localStorage.setItem('ds-agent-theme', theme);
  } catch {}
}

function checkFirstRun(): boolean {
  try {
    return !localStorage.getItem(ONBOARDING_STORAGE_KEY);
  } catch {
    return true;
  }
}

function shouldSkipOnboardingForE2E(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }
  try {
    const params = new URLSearchParams(window.location.search);
    return params.get('e2e_skip_onboarding') === '1';
  } catch {
    return false;
  }
}

const SKIP_ONBOARDING_FOR_E2E = shouldSkipOnboardingForE2E();

export const useConfigStore = create<ConfigState>((set, get) => ({
  isFirstRun: SKIP_ONBOARDING_FOR_E2E ? false : checkFirstRun(),
  showOnboarding: SKIP_ONBOARDING_FOR_E2E ? false : checkFirstRun(),
  showSettings: false,
  theme: loadTheme(),
  maxBudgetUsd: 10.0,
  budgetWarningThresholdPct: 80,
  pendingStarterPrompt: null,

  setFirstRun: (v) => set({ isFirstRun: v }),

  setShowOnboarding: (v) => set({ showOnboarding: v }),

  setShowSettings: (v) => set({ showSettings: v }),

  setTheme: (t) => {
    persistTheme(t);
    applyThemeClass(t);
    set({ theme: t });
  },

  toggleTheme: () =>
    set((s) => {
      const next: Theme = s.theme === 'dark' ? 'light' : 'dark';
      persistTheme(next);
      applyThemeClass(next);
      return { theme: next };
    }),

  setMaxBudget: (v) => set({ maxBudgetUsd: v }),
  setBudgetWarningThresholdPct: (v) => set({ budgetWarningThresholdPct: v }),

  setPendingStarterPrompt: (v) => set({ pendingStarterPrompt: v }),

  consumePendingStarterPrompt: () => {
    const value = get().pendingStarterPrompt;
    if (value !== null) {
      set({ pendingStarterPrompt: null });
    }
    return value;
  },

  resetOnboarding: () => {
    try {
      localStorage.removeItem(ONBOARDING_STORAGE_KEY);
      localStorage.removeItem(LEGACY_ONBOARDING_STORAGE_KEY);
    } catch {
      // localStorage may be unavailable (private mode); UI state below
      // still re-opens the wizard for this session.
    }
    set({ isFirstRun: true, showOnboarding: true });
  },
}));

/** Apply or remove the `dark` class on <html>. */
function applyThemeClass(theme: Theme): void {
  if (typeof document !== 'undefined') {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    document.documentElement.classList.toggle('light', theme === 'light');
  }
}

// Apply on load
applyThemeClass(loadTheme());
