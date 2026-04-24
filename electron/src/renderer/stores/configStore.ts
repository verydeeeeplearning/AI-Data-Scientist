/**
 * Config + UI state — Zustand store for settings, theme, and onboarding.
 */

import { create } from 'zustand';
import {
  applyThemeToDocument,
  getNextTheme,
  loadStoredTheme,
  THEME_STORAGE_KEY,
  type Theme,
} from '../design-system/themes';
import {
  DEFAULT_DENSITY_MODE,
  type DensityMode,
} from '../domain/layout/density';
import {
  applyDensityToDocument,
  loadStoredDensity,
  persistDensity,
} from '../infrastructure/layout/densityPersistence';
import type { DeepLinkReauthPolicy } from '../application/deepLink/handleDeepLink';

export const DEEP_LINK_REAUTH_STORAGE_KEY = 'ds-agent-deep-link-reauth:v1';
const DEEP_LINK_REAUTH_DEFAULT: DeepLinkReauthPolicy = 'once-per-session';
export const TELEGRAM_NOTIFICATION_SETTINGS_STORAGE_KEY =
  'ds-agent-telegram-notification-settings:v1';

export type TelegramDigestCadence =
  | 'interval'
  | 'hourly'
  | 'morning'
  | 'end_of_day';

export type TelegramNotificationSettingsSource = 'default' | 'workspace' | 'local';

export interface TelegramNotificationSettings {
  digestEnabled: boolean;
  digestCadence: TelegramDigestCadence;
  digestIntervalMinutes: number;
  timezone: string;
  quietHoursEnabled: boolean;
  quietHoursStart: string;
  quietHoursEnd: string;
  quietHoursTimezone: string;
}

interface StoredTelegramNotificationSettingsPayload {
  source?: TelegramNotificationSettingsSource;
  settings?: Partial<TelegramNotificationSettings>;
}

interface LoadedTelegramNotificationSettings {
  settings: TelegramNotificationSettings;
  source: TelegramNotificationSettingsSource;
}

function isDeepLinkReauthPolicy(value: unknown): value is DeepLinkReauthPolicy {
  return value === 'none' || value === 'once-per-session' || value === 'always';
}

function loadDeepLinkReauth(): DeepLinkReauthPolicy {
  try {
    const raw = localStorage.getItem(DEEP_LINK_REAUTH_STORAGE_KEY);
    if (isDeepLinkReauthPolicy(raw)) {
      return raw;
    }
  } catch {
    // storage unavailable — fall through
  }
  return DEEP_LINK_REAUTH_DEFAULT;
}

function persistDeepLinkReauth(policy: DeepLinkReauthPolicy): void {
  try {
    localStorage.setItem(DEEP_LINK_REAUTH_STORAGE_KEY, policy);
  } catch {
    // ignore
  }
}

const ONBOARDING_STORAGE_KEY = 'ds-agent-onboarded-v2';
const LEGACY_ONBOARDING_STORAGE_KEY = 'ds-agent-onboarded';
export const MISSION_HEADER_FLAG_STORAGE_KEY = 'ds-agent-feature-mission-header';
export const NEW_EXECUTION_TIMELINE_FLAG_STORAGE_KEY = 'ds-agent-feature-new-execution-timeline';
export const IA_V2_FLAG_STORAGE_KEY = 'ds-agent-feature-ia-v2';

const TELEGRAM_DIGEST_CADENCE_ALIASES: Readonly<Record<string, TelegramDigestCadence>> = {
  interval: 'interval',
  hourly: 'hourly',
  morning: 'morning',
  eod: 'end_of_day',
  end_of_day: 'end_of_day',
  'end-of-day': 'end_of_day',
};

function resolveLocalTimeZone(): string {
  try {
    const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone?.trim();
    if (timeZone) {
      return timeZone;
    }
  } catch {
    // ignore
  }
  return 'UTC';
}

function normalizeTelegramDigestCadence(value: unknown): TelegramDigestCadence {
  if (typeof value !== 'string') {
    return 'interval';
  }
  return TELEGRAM_DIGEST_CADENCE_ALIASES[value.trim().toLowerCase()] ?? 'interval';
}

function normalizeTelegramIntervalMinutes(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.max(1, Math.round(value));
  }
  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10);
    if (Number.isFinite(parsed)) {
      return Math.max(1, parsed);
    }
  }
  return 15;
}

function normalizeTelegramTime(value: unknown, fallback: string): string {
  if (typeof value !== 'string') {
    return fallback;
  }
  const trimmed = value.trim();
  return /^\d{2}:\d{2}$/.test(trimmed) ? trimmed : fallback;
}

function normalizeTelegramTimeZone(value: unknown, fallback: string): string {
  if (typeof value !== 'string') {
    return fallback;
  }
  const trimmed = value.trim();
  return trimmed || fallback;
}

export function createDefaultTelegramNotificationSettings(): TelegramNotificationSettings {
  const timeZone = resolveLocalTimeZone();
  return {
    digestEnabled: false,
    digestCadence: 'interval',
    digestIntervalMinutes: 15,
    timezone: timeZone,
    quietHoursEnabled: false,
    quietHoursStart: '22:00',
    quietHoursEnd: '07:00',
    quietHoursTimezone: timeZone,
  };
}

function coerceTelegramNotificationSettings(
  value: Partial<TelegramNotificationSettings> | null | undefined,
): TelegramNotificationSettings {
  const defaults = createDefaultTelegramNotificationSettings();
  return {
    digestEnabled:
      typeof value?.digestEnabled === 'boolean' ? value.digestEnabled : defaults.digestEnabled,
    digestCadence: normalizeTelegramDigestCadence(value?.digestCadence),
    digestIntervalMinutes: normalizeTelegramIntervalMinutes(value?.digestIntervalMinutes),
    timezone: normalizeTelegramTimeZone(value?.timezone, defaults.timezone),
    quietHoursEnabled:
      typeof value?.quietHoursEnabled === 'boolean'
        ? value.quietHoursEnabled
        : defaults.quietHoursEnabled,
    quietHoursStart: normalizeTelegramTime(value?.quietHoursStart, defaults.quietHoursStart),
    quietHoursEnd: normalizeTelegramTime(value?.quietHoursEnd, defaults.quietHoursEnd),
    quietHoursTimezone: normalizeTelegramTimeZone(
      value?.quietHoursTimezone,
      defaults.quietHoursTimezone,
    ),
  };
}

function persistTelegramNotificationSettings(
  settings: TelegramNotificationSettings,
  source: Exclude<TelegramNotificationSettingsSource, 'default'>,
): void {
  try {
    const payload: StoredTelegramNotificationSettingsPayload = {
      source,
      settings,
    };
    localStorage.setItem(
      TELEGRAM_NOTIFICATION_SETTINGS_STORAGE_KEY,
      JSON.stringify(payload),
    );
  } catch {
    // ignore
  }
}

function clearTelegramNotificationSettings(): void {
  try {
    localStorage.removeItem(TELEGRAM_NOTIFICATION_SETTINGS_STORAGE_KEY);
  } catch {
    // ignore
  }
}

function loadTelegramNotificationSettings(): LoadedTelegramNotificationSettings {
  const defaults = createDefaultTelegramNotificationSettings();
  try {
    const raw = localStorage.getItem(TELEGRAM_NOTIFICATION_SETTINGS_STORAGE_KEY);
    if (!raw) {
      return { settings: defaults, source: 'default' };
    }
    const parsed = JSON.parse(raw) as StoredTelegramNotificationSettingsPayload | null;
    if (!parsed || typeof parsed !== 'object') {
      return { settings: defaults, source: 'default' };
    }
    const source =
      parsed.source === 'workspace' || parsed.source === 'local'
        ? parsed.source
        : 'local';
    return {
      settings: coerceTelegramNotificationSettings(parsed.settings),
      source,
    };
  } catch {
    return { settings: defaults, source: 'default' };
  }
}

interface ConfigState {
  // Onboarding
  isFirstRun: boolean;
  showOnboarding: boolean;

  // Settings panel
  showSettings: boolean;

  // Local rollback gates
  useIaV2: boolean;
  missionHeaderEnabled: boolean;
  useNewExecutionTimeline: boolean;

  // Theme
  theme: Theme;

  // Layout density (W4-B / PLAN_02)
  density: DensityMode;

  // Cross-surface deep link re-auth policy (W4-C / PLAN_03)
  deepLinkReauth: DeepLinkReauthPolicy;

  // Telegram delivery settings (renderer-local draft)
  telegramNotificationSettings: TelegramNotificationSettings;
  telegramNotificationSettingsSource: TelegramNotificationSettingsSource;

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
  setUseIaV2: (v: boolean) => void;
  setMissionHeaderEnabled: (v: boolean) => void;
  setUseNewExecutionTimeline: (v: boolean) => void;
  setTheme: (t: Theme) => void;
  toggleTheme: () => void;
  setDensity: (mode: DensityMode) => void;
  setDeepLinkReauth: (policy: DeepLinkReauthPolicy) => void;
  updateTelegramNotificationSettings: (
    patch: Partial<TelegramNotificationSettings>,
  ) => void;
  hydrateTelegramNotificationSettingsFromWorkspace: (
    settings: TelegramNotificationSettings,
  ) => void;
  replaceTelegramNotificationSettings: (
    settings: TelegramNotificationSettings,
    source?: TelegramNotificationSettingsSource,
  ) => void;
  resetTelegramNotificationSettings: () => void;
  setMaxBudget: (v: number) => void;
  setBudgetWarningThresholdPct: (v: number) => void;
  setPendingStarterPrompt: (v: string | null) => void;
  consumePendingStarterPrompt: () => string | null;
  resetOnboarding: () => void;
}

function loadTheme(): Theme {
  try {
    return loadStoredTheme(localStorage);
  } catch {
    return 'dark';
  }
}

function loadInitialDensity(): DensityMode {
  try {
    return loadStoredDensity();
  } catch {
    return DEFAULT_DENSITY_MODE;
  }
}

function persistTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {}
}

export function parseMissionHeaderEnabled(value: string | null): boolean {
  if (value === null) {
    return true;
  }
  const normalized = value.trim().toLowerCase();
  return normalized !== '0' && normalized !== 'false' && normalized !== 'off';
}

export function loadMissionHeaderEnabled(): boolean {
  try {
    return parseMissionHeaderEnabled(localStorage.getItem(MISSION_HEADER_FLAG_STORAGE_KEY));
  } catch {
    return true;
  }
}

export function parseIaV2Enabled(value: string | null): boolean {
  if (value === null) {
    return true;
  }
  const normalized = value.trim().toLowerCase();
  return normalized !== '0' && normalized !== 'false' && normalized !== 'off';
}

export function loadIaV2Enabled(): boolean {
  try {
    const params = new URLSearchParams(window.location.search);
    if (params.get('e2e_force_legacy_ia') === '1') {
      return false;
    }
    return parseIaV2Enabled(localStorage.getItem(IA_V2_FLAG_STORAGE_KEY));
  } catch {
    return true;
  }
}

function persistIaV2Enabled(enabled: boolean): void {
  try {
    localStorage.setItem(IA_V2_FLAG_STORAGE_KEY, enabled ? 'true' : 'false');
  } catch {}
}

function persistMissionHeaderEnabled(enabled: boolean): void {
  try {
    localStorage.setItem(MISSION_HEADER_FLAG_STORAGE_KEY, enabled ? 'true' : 'false');
  } catch {}
}

export function parseNewExecutionTimelineEnabled(value: string | null): boolean {
  if (value === null) {
    return true;
  }
  const normalized = value.trim().toLowerCase();
  return normalized !== '0' && normalized !== 'false' && normalized !== 'off';
}

export function loadNewExecutionTimelineEnabled(): boolean {
  try {
    return parseNewExecutionTimelineEnabled(
      localStorage.getItem(NEW_EXECUTION_TIMELINE_FLAG_STORAGE_KEY),
    );
  } catch {
    return true;
  }
}

function persistNewExecutionTimelineEnabled(enabled: boolean): void {
  try {
    localStorage.setItem(
      NEW_EXECUTION_TIMELINE_FLAG_STORAGE_KEY,
      enabled ? 'true' : 'false',
    );
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
const initialTelegramNotificationSettings = loadTelegramNotificationSettings();

export const useConfigStore = create<ConfigState>((set, get) => ({
  isFirstRun: SKIP_ONBOARDING_FOR_E2E ? false : checkFirstRun(),
  showOnboarding: SKIP_ONBOARDING_FOR_E2E ? false : checkFirstRun(),
  showSettings: false,
  useIaV2: loadIaV2Enabled(),
  missionHeaderEnabled: loadMissionHeaderEnabled(),
  useNewExecutionTimeline: loadNewExecutionTimelineEnabled(),
  theme: loadTheme(),
  density: loadInitialDensity(),
  deepLinkReauth: loadDeepLinkReauth(),
  telegramNotificationSettings: initialTelegramNotificationSettings.settings,
  telegramNotificationSettingsSource: initialTelegramNotificationSettings.source,
  maxBudgetUsd: 10.0,
  budgetWarningThresholdPct: 80,
  pendingStarterPrompt: null,

  setFirstRun: (v) => set({ isFirstRun: v }),

  setShowOnboarding: (v) => set({ showOnboarding: v }),

  setShowSettings: (v) => set({ showSettings: v }),

  setUseIaV2: (v) => {
    persistIaV2Enabled(v);
    set({ useIaV2: v });
  },

  setMissionHeaderEnabled: (v) => {
    persistMissionHeaderEnabled(v);
    set({ missionHeaderEnabled: v });
  },

  setUseNewExecutionTimeline: (v) => {
    persistNewExecutionTimelineEnabled(v);
    set({ useNewExecutionTimeline: v });
  },

  setTheme: (t) => {
    persistTheme(t);
    applyThemeToDocument(t);
    set({ theme: t });
  },

  toggleTheme: () =>
    set((s) => {
      const next = getNextTheme(s.theme);
      persistTheme(next);
      applyThemeToDocument(next);
      return { theme: next };
    }),

  setDensity: (mode) => {
    persistDensity(mode);
    applyDensityToDocument(mode);
    set({ density: mode });
  },

  setDeepLinkReauth: (policy) => {
    persistDeepLinkReauth(policy);
    set({ deepLinkReauth: policy });
  },

  updateTelegramNotificationSettings: (patch) =>
    set((state) => {
      const next = coerceTelegramNotificationSettings({
        ...state.telegramNotificationSettings,
        ...patch,
      });
      persistTelegramNotificationSettings(next, 'local');
      return {
        telegramNotificationSettings: next,
        telegramNotificationSettingsSource: 'local',
      };
    }),

  hydrateTelegramNotificationSettingsFromWorkspace: (settings) =>
    set((state) => {
      if (state.telegramNotificationSettingsSource === 'local') {
        return state;
      }
      const next = coerceTelegramNotificationSettings(settings);
      persistTelegramNotificationSettings(next, 'workspace');
      return {
        telegramNotificationSettings: next,
        telegramNotificationSettingsSource: 'workspace',
      };
    }),

  replaceTelegramNotificationSettings: (settings, source = 'local') => {
    if (source === 'default') {
      clearTelegramNotificationSettings();
      set({
        telegramNotificationSettings: createDefaultTelegramNotificationSettings(),
        telegramNotificationSettingsSource: 'default',
      });
      return;
    }
    const next = coerceTelegramNotificationSettings(settings);
    persistTelegramNotificationSettings(next, source);
    set({
      telegramNotificationSettings: next,
      telegramNotificationSettingsSource: source,
    });
  },

  resetTelegramNotificationSettings: () => {
    clearTelegramNotificationSettings();
    set({
      telegramNotificationSettings: createDefaultTelegramNotificationSettings(),
      telegramNotificationSettingsSource: 'default',
    });
  },

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

// Apply on load
applyThemeToDocument(loadTheme());

export const __test = {
  coerceTelegramNotificationSettings,
  createDefaultTelegramNotificationSettings,
  loadTelegramNotificationSettings,
  normalizeTelegramDigestCadence,
};
