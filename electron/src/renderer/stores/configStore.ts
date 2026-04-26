/**
 * Config + UI state — Zustand store for settings, theme, and onboarding.
 */

import { create } from 'zustand';
import {
  applyThemeToDocument,
  getNextTheme,
  loadStoredTheme,
  normalizeTheme,
  THEME_STORAGE_KEY,
  type Theme,
} from '../design-system/themes';
import {
  DEFAULT_DENSITY_MODE,
  isDensityMode,
  type DensityMode,
} from '../domain/layout/density';
import {
  applyDensityToDocument,
  DENSITY_STORAGE_KEY,
  loadStoredDensity,
} from '../infrastructure/layout/densityPersistence';
import { announce } from '../application/a11y/ariaLive';
import type { DeepLinkReauthPolicy } from '../application/deepLink/handleDeepLink';
import {
  LOCALE_STORAGE_KEY,
  normalizeLocale,
  setLocale as setAppLocale,
  translateKey,
} from './i18nStore';

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

function persistDeepLinkReauth(policy: DeepLinkReauthPolicy): boolean {
  return persistStorageValue(DEEP_LINK_REAUTH_STORAGE_KEY, policy);
}

const ONBOARDING_STORAGE_KEY = 'ds-agent-onboarded-v2';
const LEGACY_ONBOARDING_STORAGE_KEY = 'ds-agent-onboarded';
export const MISSION_HEADER_FLAG_STORAGE_KEY = 'ds-agent-feature-mission-header';
export const NEW_EXECUTION_TIMELINE_FLAG_STORAGE_KEY = 'ds-agent-feature-new-execution-timeline';

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
  if (!trimmed) {
    return fallback;
  }
  try {
    new Intl.DateTimeFormat(undefined, { timeZone: trimmed }).format(new Date(0));
    return trimmed;
  } catch {
    return fallback;
  }
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
): boolean {
  try {
    const payload: StoredTelegramNotificationSettingsPayload = {
      source,
      settings,
    };
    localStorage.setItem(
      TELEGRAM_NOTIFICATION_SETTINGS_STORAGE_KEY,
      JSON.stringify(payload),
    );
    return true;
  } catch {
    return false;
  }
}

function clearTelegramNotificationSettings(): boolean {
  try {
    localStorage.removeItem(TELEGRAM_NOTIFICATION_SETTINGS_STORAGE_KEY);
    return true;
  } catch {
    return false;
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

  // Local rollout gates
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

function persistStorageValue(key: string, value: string): boolean {
  try {
    localStorage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

function notifySessionOnlyPersist(): void {
  announce(translateKey('common.storage.persistFailed'));
}

function notifyIfPersistFailed(persisted: boolean): void {
  if (!persisted) {
    notifySessionOnlyPersist();
  }
}

function serializeFlag(enabled: boolean): string {
  return enabled ? 'true' : 'false';
}

function persistTheme(theme: Theme): boolean {
  return persistStorageValue(THEME_STORAGE_KEY, theme);
}

function persistDensityMode(mode: DensityMode): boolean {
  return persistStorageValue(DENSITY_STORAGE_KEY, mode);
}

export function parseFlag(value: string | null, defaultValue: boolean): boolean {
  if (value === null) {
    return defaultValue;
  }
  const normalized = value.trim().toLowerCase();
  if (normalized === '1' || normalized === 'true' || normalized === 'on') {
    return true;
  }
  if (normalized === '0' || normalized === 'false' || normalized === 'off') {
    return false;
  }
  return defaultValue;
}

export function parseMissionHeaderEnabled(value: string | null): boolean {
  return parseFlag(value, true);
}

export function loadMissionHeaderEnabled(): boolean {
  try {
    return parseMissionHeaderEnabled(localStorage.getItem(MISSION_HEADER_FLAG_STORAGE_KEY));
  } catch {
    return true;
  }
}

function persistMissionHeaderEnabled(enabled: boolean): boolean {
  return persistStorageValue(MISSION_HEADER_FLAG_STORAGE_KEY, serializeFlag(enabled));
}

export function parseNewExecutionTimelineEnabled(value: string | null): boolean {
  return parseFlag(value, true);
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

function persistNewExecutionTimelineEnabled(enabled: boolean): boolean {
  return persistStorageValue(NEW_EXECUTION_TIMELINE_FLAG_STORAGE_KEY, serializeFlag(enabled));
}

function checkFirstRun(): boolean {
  try {
    return (
      !localStorage.getItem(ONBOARDING_STORAGE_KEY)
      && !localStorage.getItem(LEGACY_ONBOARDING_STORAGE_KEY)
    );
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

  setMissionHeaderEnabled: (v) => {
    const persisted = persistMissionHeaderEnabled(v);
    set({ missionHeaderEnabled: v });
    notifyIfPersistFailed(persisted);
  },

  setUseNewExecutionTimeline: (v) => {
    const persisted = persistNewExecutionTimelineEnabled(v);
    set({ useNewExecutionTimeline: v });
    notifyIfPersistFailed(persisted);
  },

  setTheme: (t) => {
    const persisted = persistTheme(t);
    applyThemeToDocument(t);
    set({ theme: t });
    notifyIfPersistFailed(persisted);
  },

  toggleTheme: () => {
    const next = getNextTheme(get().theme);
    const persisted = persistTheme(next);
    applyThemeToDocument(next);
    set({ theme: next });
    notifyIfPersistFailed(persisted);
  },

  setDensity: (mode) => {
    const persisted = persistDensityMode(mode);
    applyDensityToDocument(mode);
    set({ density: mode });
    notifyIfPersistFailed(persisted);
  },

  setDeepLinkReauth: (policy) => {
    const persisted = persistDeepLinkReauth(policy);
    set({ deepLinkReauth: policy });
    notifyIfPersistFailed(persisted);
  },

  updateTelegramNotificationSettings: (patch) => {
    const next = coerceTelegramNotificationSettings({
      ...get().telegramNotificationSettings,
      ...patch,
    });
    const persisted = persistTelegramNotificationSettings(next, 'local');
    set({
      telegramNotificationSettings: next,
      telegramNotificationSettingsSource: 'local',
    });
    notifyIfPersistFailed(persisted);
  },

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
      const persisted = clearTelegramNotificationSettings();
      set({
        telegramNotificationSettings: createDefaultTelegramNotificationSettings(),
        telegramNotificationSettingsSource: 'default',
      });
      notifyIfPersistFailed(persisted);
      return;
    }
    const next = coerceTelegramNotificationSettings(settings);
    const persisted = persistTelegramNotificationSettings(next, source);
    set({
      telegramNotificationSettings: next,
      telegramNotificationSettingsSource: source,
    });
    notifyIfPersistFailed(persisted);
  },

  resetTelegramNotificationSettings: () => {
    const persisted = clearTelegramNotificationSettings();
    set({
      telegramNotificationSettings: createDefaultTelegramNotificationSettings(),
      telegramNotificationSettingsSource: 'default',
    });
    notifyIfPersistFailed(persisted);
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
    let persisted = true;
    try {
      localStorage.removeItem(ONBOARDING_STORAGE_KEY);
      localStorage.removeItem(LEGACY_ONBOARDING_STORAGE_KEY);
    } catch {
      persisted = false;
      // localStorage may be unavailable (private mode); UI state below
      // still re-opens the wizard for this session.
    }
    set({ isFirstRun: true, showOnboarding: true });
    notifyIfPersistFailed(persisted);
  },
}));

function isConfigStorageEvent(event: StorageEvent): boolean {
  if (typeof window === 'undefined') {
    return false;
  }
  try {
    return event.storageArea === null || event.storageArea === window.localStorage;
  } catch {
    return event.storageArea === null;
  }
}

function readStoredValue(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function syncThemeFromStorage(value: string | null): void {
  const theme = normalizeTheme(value) ?? loadTheme();
  applyThemeToDocument(theme);
  useConfigStore.setState({ theme });
}

function syncDensityFromStorage(value: string | null): void {
  const density = isDensityMode(value) ? value : loadInitialDensity();
  applyDensityToDocument(density);
  useConfigStore.setState({ density });
}

function syncDeepLinkReauthFromStorage(value: string | null): void {
  useConfigStore.setState({
    deepLinkReauth: isDeepLinkReauthPolicy(value) ? value : loadDeepLinkReauth(),
  });
}

function syncTelegramNotificationSettingsFromStorage(): void {
  const next = loadTelegramNotificationSettings();
  useConfigStore.setState({
    telegramNotificationSettings: next.settings,
    telegramNotificationSettingsSource: next.source,
  });
}

function syncLocaleFromStorage(value: string | null): void {
  const locale = normalizeLocale(value);
  if (locale) {
    setAppLocale(locale);
  }
}

function syncAllConfigStorage(): void {
  syncThemeFromStorage(readStoredValue(THEME_STORAGE_KEY));
  syncDensityFromStorage(readStoredValue(DENSITY_STORAGE_KEY));
  useConfigStore.setState({
    missionHeaderEnabled: loadMissionHeaderEnabled(),
    useNewExecutionTimeline: loadNewExecutionTimelineEnabled(),
    deepLinkReauth: loadDeepLinkReauth(),
  });
  syncTelegramNotificationSettingsFromStorage();
  syncLocaleFromStorage(readStoredValue(LOCALE_STORAGE_KEY));
}

export function syncConfigStoreFromStorageEvent(event: StorageEvent): void {
  if (!isConfigStorageEvent(event)) {
    return;
  }
  if (event.key === null) {
    syncAllConfigStorage();
    return;
  }

  switch (event.key) {
    case THEME_STORAGE_KEY:
      syncThemeFromStorage(event.newValue);
      break;
    case DENSITY_STORAGE_KEY:
      syncDensityFromStorage(event.newValue);
      break;
    case MISSION_HEADER_FLAG_STORAGE_KEY:
      useConfigStore.setState({
        missionHeaderEnabled: parseMissionHeaderEnabled(event.newValue),
      });
      break;
    case NEW_EXECUTION_TIMELINE_FLAG_STORAGE_KEY:
      useConfigStore.setState({
        useNewExecutionTimeline: parseNewExecutionTimelineEnabled(event.newValue),
      });
      break;
    case DEEP_LINK_REAUTH_STORAGE_KEY:
      syncDeepLinkReauthFromStorage(event.newValue);
      break;
    case TELEGRAM_NOTIFICATION_SETTINGS_STORAGE_KEY:
      syncTelegramNotificationSettingsFromStorage();
      break;
    case LOCALE_STORAGE_KEY:
      syncLocaleFromStorage(event.newValue);
      break;
    default:
      break;
  }
}

// Apply on load
applyThemeToDocument(loadTheme());

export const __test = {
  coerceTelegramNotificationSettings,
  createDefaultTelegramNotificationSettings,
  loadTelegramNotificationSettings,
  normalizeTelegramDigestCadence,
};
