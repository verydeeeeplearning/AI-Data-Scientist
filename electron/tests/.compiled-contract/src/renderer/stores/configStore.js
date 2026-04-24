"use strict";
/**
 * Config + UI state — Zustand store for settings, theme, and onboarding.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.__test = exports.useConfigStore = exports.IA_V2_FLAG_STORAGE_KEY = exports.NEW_EXECUTION_TIMELINE_FLAG_STORAGE_KEY = exports.MISSION_HEADER_FLAG_STORAGE_KEY = exports.TELEGRAM_NOTIFICATION_SETTINGS_STORAGE_KEY = exports.DEEP_LINK_REAUTH_STORAGE_KEY = void 0;
exports.createDefaultTelegramNotificationSettings = createDefaultTelegramNotificationSettings;
exports.parseMissionHeaderEnabled = parseMissionHeaderEnabled;
exports.loadMissionHeaderEnabled = loadMissionHeaderEnabled;
exports.parseIaV2Enabled = parseIaV2Enabled;
exports.loadIaV2Enabled = loadIaV2Enabled;
exports.parseNewExecutionTimelineEnabled = parseNewExecutionTimelineEnabled;
exports.loadNewExecutionTimelineEnabled = loadNewExecutionTimelineEnabled;
const zustand_1 = require("zustand");
const themes_1 = require("../design-system/themes");
const density_1 = require("../domain/layout/density");
const densityPersistence_1 = require("../infrastructure/layout/densityPersistence");
exports.DEEP_LINK_REAUTH_STORAGE_KEY = 'ds-agent-deep-link-reauth:v1';
const DEEP_LINK_REAUTH_DEFAULT = 'once-per-session';
exports.TELEGRAM_NOTIFICATION_SETTINGS_STORAGE_KEY = 'ds-agent-telegram-notification-settings:v1';
function isDeepLinkReauthPolicy(value) {
    return value === 'none' || value === 'once-per-session' || value === 'always';
}
function loadDeepLinkReauth() {
    try {
        const raw = localStorage.getItem(exports.DEEP_LINK_REAUTH_STORAGE_KEY);
        if (isDeepLinkReauthPolicy(raw)) {
            return raw;
        }
    }
    catch {
        // storage unavailable — fall through
    }
    return DEEP_LINK_REAUTH_DEFAULT;
}
function persistDeepLinkReauth(policy) {
    try {
        localStorage.setItem(exports.DEEP_LINK_REAUTH_STORAGE_KEY, policy);
    }
    catch {
        // ignore
    }
}
const ONBOARDING_STORAGE_KEY = 'ds-agent-onboarded-v2';
const LEGACY_ONBOARDING_STORAGE_KEY = 'ds-agent-onboarded';
exports.MISSION_HEADER_FLAG_STORAGE_KEY = 'ds-agent-feature-mission-header';
exports.NEW_EXECUTION_TIMELINE_FLAG_STORAGE_KEY = 'ds-agent-feature-new-execution-timeline';
exports.IA_V2_FLAG_STORAGE_KEY = 'ds-agent-feature-ia-v2';
const TELEGRAM_DIGEST_CADENCE_ALIASES = {
    interval: 'interval',
    hourly: 'hourly',
    morning: 'morning',
    eod: 'end_of_day',
    end_of_day: 'end_of_day',
    'end-of-day': 'end_of_day',
};
function resolveLocalTimeZone() {
    try {
        const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone?.trim();
        if (timeZone) {
            return timeZone;
        }
    }
    catch {
        // ignore
    }
    return 'UTC';
}
function normalizeTelegramDigestCadence(value) {
    if (typeof value !== 'string') {
        return 'interval';
    }
    return TELEGRAM_DIGEST_CADENCE_ALIASES[value.trim().toLowerCase()] ?? 'interval';
}
function normalizeTelegramIntervalMinutes(value) {
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
function normalizeTelegramTime(value, fallback) {
    if (typeof value !== 'string') {
        return fallback;
    }
    const trimmed = value.trim();
    return /^\d{2}:\d{2}$/.test(trimmed) ? trimmed : fallback;
}
function normalizeTelegramTimeZone(value, fallback) {
    if (typeof value !== 'string') {
        return fallback;
    }
    const trimmed = value.trim();
    return trimmed || fallback;
}
function createDefaultTelegramNotificationSettings() {
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
function coerceTelegramNotificationSettings(value) {
    const defaults = createDefaultTelegramNotificationSettings();
    return {
        digestEnabled: typeof value?.digestEnabled === 'boolean' ? value.digestEnabled : defaults.digestEnabled,
        digestCadence: normalizeTelegramDigestCadence(value?.digestCadence),
        digestIntervalMinutes: normalizeTelegramIntervalMinutes(value?.digestIntervalMinutes),
        timezone: normalizeTelegramTimeZone(value?.timezone, defaults.timezone),
        quietHoursEnabled: typeof value?.quietHoursEnabled === 'boolean'
            ? value.quietHoursEnabled
            : defaults.quietHoursEnabled,
        quietHoursStart: normalizeTelegramTime(value?.quietHoursStart, defaults.quietHoursStart),
        quietHoursEnd: normalizeTelegramTime(value?.quietHoursEnd, defaults.quietHoursEnd),
        quietHoursTimezone: normalizeTelegramTimeZone(value?.quietHoursTimezone, defaults.quietHoursTimezone),
    };
}
function persistTelegramNotificationSettings(settings, source) {
    try {
        const payload = {
            source,
            settings,
        };
        localStorage.setItem(exports.TELEGRAM_NOTIFICATION_SETTINGS_STORAGE_KEY, JSON.stringify(payload));
    }
    catch {
        // ignore
    }
}
function clearTelegramNotificationSettings() {
    try {
        localStorage.removeItem(exports.TELEGRAM_NOTIFICATION_SETTINGS_STORAGE_KEY);
    }
    catch {
        // ignore
    }
}
function loadTelegramNotificationSettings() {
    const defaults = createDefaultTelegramNotificationSettings();
    try {
        const raw = localStorage.getItem(exports.TELEGRAM_NOTIFICATION_SETTINGS_STORAGE_KEY);
        if (!raw) {
            return { settings: defaults, source: 'default' };
        }
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object') {
            return { settings: defaults, source: 'default' };
        }
        const source = parsed.source === 'workspace' || parsed.source === 'local'
            ? parsed.source
            : 'local';
        return {
            settings: coerceTelegramNotificationSettings(parsed.settings),
            source,
        };
    }
    catch {
        return { settings: defaults, source: 'default' };
    }
}
function loadTheme() {
    try {
        return (0, themes_1.loadStoredTheme)(localStorage);
    }
    catch {
        return 'dark';
    }
}
function loadInitialDensity() {
    try {
        return (0, densityPersistence_1.loadStoredDensity)();
    }
    catch {
        return density_1.DEFAULT_DENSITY_MODE;
    }
}
function persistTheme(theme) {
    try {
        localStorage.setItem(themes_1.THEME_STORAGE_KEY, theme);
    }
    catch { }
}
function parseMissionHeaderEnabled(value) {
    if (value === null) {
        return true;
    }
    const normalized = value.trim().toLowerCase();
    return normalized !== '0' && normalized !== 'false' && normalized !== 'off';
}
function loadMissionHeaderEnabled() {
    try {
        return parseMissionHeaderEnabled(localStorage.getItem(exports.MISSION_HEADER_FLAG_STORAGE_KEY));
    }
    catch {
        return true;
    }
}
function parseIaV2Enabled(value) {
    if (value === null) {
        return true;
    }
    const normalized = value.trim().toLowerCase();
    return normalized !== '0' && normalized !== 'false' && normalized !== 'off';
}
function loadIaV2Enabled() {
    try {
        const params = new URLSearchParams(window.location.search);
        if (params.get('e2e_force_legacy_ia') === '1') {
            return false;
        }
        return parseIaV2Enabled(localStorage.getItem(exports.IA_V2_FLAG_STORAGE_KEY));
    }
    catch {
        return true;
    }
}
function persistIaV2Enabled(enabled) {
    try {
        localStorage.setItem(exports.IA_V2_FLAG_STORAGE_KEY, enabled ? 'true' : 'false');
    }
    catch { }
}
function persistMissionHeaderEnabled(enabled) {
    try {
        localStorage.setItem(exports.MISSION_HEADER_FLAG_STORAGE_KEY, enabled ? 'true' : 'false');
    }
    catch { }
}
function parseNewExecutionTimelineEnabled(value) {
    if (value === null) {
        return true;
    }
    const normalized = value.trim().toLowerCase();
    return normalized !== '0' && normalized !== 'false' && normalized !== 'off';
}
function loadNewExecutionTimelineEnabled() {
    try {
        return parseNewExecutionTimelineEnabled(localStorage.getItem(exports.NEW_EXECUTION_TIMELINE_FLAG_STORAGE_KEY));
    }
    catch {
        return true;
    }
}
function persistNewExecutionTimelineEnabled(enabled) {
    try {
        localStorage.setItem(exports.NEW_EXECUTION_TIMELINE_FLAG_STORAGE_KEY, enabled ? 'true' : 'false');
    }
    catch { }
}
function checkFirstRun() {
    try {
        return !localStorage.getItem(ONBOARDING_STORAGE_KEY);
    }
    catch {
        return true;
    }
}
function shouldSkipOnboardingForE2E() {
    if (typeof window === 'undefined') {
        return false;
    }
    try {
        const params = new URLSearchParams(window.location.search);
        return params.get('e2e_skip_onboarding') === '1';
    }
    catch {
        return false;
    }
}
const SKIP_ONBOARDING_FOR_E2E = shouldSkipOnboardingForE2E();
const initialTelegramNotificationSettings = loadTelegramNotificationSettings();
exports.useConfigStore = (0, zustand_1.create)((set, get) => ({
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
        (0, themes_1.applyThemeToDocument)(t);
        set({ theme: t });
    },
    toggleTheme: () => set((s) => {
        const next = (0, themes_1.getNextTheme)(s.theme);
        persistTheme(next);
        (0, themes_1.applyThemeToDocument)(next);
        return { theme: next };
    }),
    setDensity: (mode) => {
        (0, densityPersistence_1.persistDensity)(mode);
        (0, densityPersistence_1.applyDensityToDocument)(mode);
        set({ density: mode });
    },
    setDeepLinkReauth: (policy) => {
        persistDeepLinkReauth(policy);
        set({ deepLinkReauth: policy });
    },
    updateTelegramNotificationSettings: (patch) => set((state) => {
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
    hydrateTelegramNotificationSettingsFromWorkspace: (settings) => set((state) => {
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
        }
        catch {
            // localStorage may be unavailable (private mode); UI state below
            // still re-opens the wizard for this session.
        }
        set({ isFirstRun: true, showOnboarding: true });
    },
}));
// Apply on load
(0, themes_1.applyThemeToDocument)(loadTheme());
exports.__test = {
    coerceTelegramNotificationSettings,
    createDefaultTelegramNotificationSettings,
    loadTelegramNotificationSettings,
    normalizeTelegramDigestCadence,
};
