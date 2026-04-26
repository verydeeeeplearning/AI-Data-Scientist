"use strict";
/**
 * Config + UI state — Zustand store for settings, theme, and onboarding.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.__test = exports.useConfigStore = exports.NEW_EXECUTION_TIMELINE_FLAG_STORAGE_KEY = exports.MISSION_HEADER_FLAG_STORAGE_KEY = exports.TELEGRAM_NOTIFICATION_SETTINGS_STORAGE_KEY = exports.DEEP_LINK_REAUTH_STORAGE_KEY = void 0;
exports.createDefaultTelegramNotificationSettings = createDefaultTelegramNotificationSettings;
exports.parseFlag = parseFlag;
exports.parseMissionHeaderEnabled = parseMissionHeaderEnabled;
exports.loadMissionHeaderEnabled = loadMissionHeaderEnabled;
exports.parseNewExecutionTimelineEnabled = parseNewExecutionTimelineEnabled;
exports.loadNewExecutionTimelineEnabled = loadNewExecutionTimelineEnabled;
exports.syncConfigStoreFromStorageEvent = syncConfigStoreFromStorageEvent;
const zustand_1 = require("zustand");
const themes_1 = require("../design-system/themes");
const density_1 = require("../domain/layout/density");
const densityPersistence_1 = require("../infrastructure/layout/densityPersistence");
const ariaLive_1 = require("../application/a11y/ariaLive");
const i18nStore_1 = require("./i18nStore");
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
    return persistStorageValue(exports.DEEP_LINK_REAUTH_STORAGE_KEY, policy);
}
const ONBOARDING_STORAGE_KEY = 'ds-agent-onboarded-v2';
const LEGACY_ONBOARDING_STORAGE_KEY = 'ds-agent-onboarded';
exports.MISSION_HEADER_FLAG_STORAGE_KEY = 'ds-agent-feature-mission-header';
exports.NEW_EXECUTION_TIMELINE_FLAG_STORAGE_KEY = 'ds-agent-feature-new-execution-timeline';
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
    if (!trimmed) {
        return fallback;
    }
    try {
        new Intl.DateTimeFormat(undefined, { timeZone: trimmed }).format(new Date(0));
        return trimmed;
    }
    catch {
        return fallback;
    }
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
        return true;
    }
    catch {
        return false;
    }
}
function clearTelegramNotificationSettings() {
    try {
        localStorage.removeItem(exports.TELEGRAM_NOTIFICATION_SETTINGS_STORAGE_KEY);
        return true;
    }
    catch {
        return false;
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
function persistStorageValue(key, value) {
    try {
        localStorage.setItem(key, value);
        return true;
    }
    catch {
        return false;
    }
}
function notifySessionOnlyPersist() {
    (0, ariaLive_1.announce)((0, i18nStore_1.translateKey)('common.storage.persistFailed'));
}
function notifyIfPersistFailed(persisted) {
    if (!persisted) {
        notifySessionOnlyPersist();
    }
}
function serializeFlag(enabled) {
    return enabled ? 'true' : 'false';
}
function persistTheme(theme) {
    return persistStorageValue(themes_1.THEME_STORAGE_KEY, theme);
}
function persistDensityMode(mode) {
    return persistStorageValue(densityPersistence_1.DENSITY_STORAGE_KEY, mode);
}
function parseFlag(value, defaultValue) {
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
function parseMissionHeaderEnabled(value) {
    return parseFlag(value, true);
}
function loadMissionHeaderEnabled() {
    try {
        return parseMissionHeaderEnabled(localStorage.getItem(exports.MISSION_HEADER_FLAG_STORAGE_KEY));
    }
    catch {
        return true;
    }
}
function persistMissionHeaderEnabled(enabled) {
    return persistStorageValue(exports.MISSION_HEADER_FLAG_STORAGE_KEY, serializeFlag(enabled));
}
function parseNewExecutionTimelineEnabled(value) {
    return parseFlag(value, true);
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
    return persistStorageValue(exports.NEW_EXECUTION_TIMELINE_FLAG_STORAGE_KEY, serializeFlag(enabled));
}
function checkFirstRun() {
    try {
        return (!localStorage.getItem(ONBOARDING_STORAGE_KEY)
            && !localStorage.getItem(LEGACY_ONBOARDING_STORAGE_KEY));
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
        (0, themes_1.applyThemeToDocument)(t);
        set({ theme: t });
        notifyIfPersistFailed(persisted);
    },
    toggleTheme: () => {
        const next = (0, themes_1.getNextTheme)(get().theme);
        const persisted = persistTheme(next);
        (0, themes_1.applyThemeToDocument)(next);
        set({ theme: next });
        notifyIfPersistFailed(persisted);
    },
    setDensity: (mode) => {
        const persisted = persistDensityMode(mode);
        (0, densityPersistence_1.applyDensityToDocument)(mode);
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
        }
        catch {
            persisted = false;
            // localStorage may be unavailable (private mode); UI state below
            // still re-opens the wizard for this session.
        }
        set({ isFirstRun: true, showOnboarding: true });
        notifyIfPersistFailed(persisted);
    },
}));
function isConfigStorageEvent(event) {
    if (typeof window === 'undefined') {
        return false;
    }
    try {
        return event.storageArea === null || event.storageArea === window.localStorage;
    }
    catch {
        return event.storageArea === null;
    }
}
function readStoredValue(key) {
    try {
        return localStorage.getItem(key);
    }
    catch {
        return null;
    }
}
function syncThemeFromStorage(value) {
    const theme = (0, themes_1.normalizeTheme)(value) ?? loadTheme();
    (0, themes_1.applyThemeToDocument)(theme);
    exports.useConfigStore.setState({ theme });
}
function syncDensityFromStorage(value) {
    const density = (0, density_1.isDensityMode)(value) ? value : loadInitialDensity();
    (0, densityPersistence_1.applyDensityToDocument)(density);
    exports.useConfigStore.setState({ density });
}
function syncDeepLinkReauthFromStorage(value) {
    exports.useConfigStore.setState({
        deepLinkReauth: isDeepLinkReauthPolicy(value) ? value : loadDeepLinkReauth(),
    });
}
function syncTelegramNotificationSettingsFromStorage() {
    const next = loadTelegramNotificationSettings();
    exports.useConfigStore.setState({
        telegramNotificationSettings: next.settings,
        telegramNotificationSettingsSource: next.source,
    });
}
function syncLocaleFromStorage(value) {
    const locale = (0, i18nStore_1.normalizeLocale)(value);
    if (locale) {
        (0, i18nStore_1.setLocale)(locale);
    }
}
function syncAllConfigStorage() {
    syncThemeFromStorage(readStoredValue(themes_1.THEME_STORAGE_KEY));
    syncDensityFromStorage(readStoredValue(densityPersistence_1.DENSITY_STORAGE_KEY));
    exports.useConfigStore.setState({
        missionHeaderEnabled: loadMissionHeaderEnabled(),
        useNewExecutionTimeline: loadNewExecutionTimelineEnabled(),
        deepLinkReauth: loadDeepLinkReauth(),
    });
    syncTelegramNotificationSettingsFromStorage();
    syncLocaleFromStorage(readStoredValue(i18nStore_1.LOCALE_STORAGE_KEY));
}
function syncConfigStoreFromStorageEvent(event) {
    if (!isConfigStorageEvent(event)) {
        return;
    }
    if (event.key === null) {
        syncAllConfigStorage();
        return;
    }
    switch (event.key) {
        case themes_1.THEME_STORAGE_KEY:
            syncThemeFromStorage(event.newValue);
            break;
        case densityPersistence_1.DENSITY_STORAGE_KEY:
            syncDensityFromStorage(event.newValue);
            break;
        case exports.MISSION_HEADER_FLAG_STORAGE_KEY:
            exports.useConfigStore.setState({
                missionHeaderEnabled: parseMissionHeaderEnabled(event.newValue),
            });
            break;
        case exports.NEW_EXECUTION_TIMELINE_FLAG_STORAGE_KEY:
            exports.useConfigStore.setState({
                useNewExecutionTimeline: parseNewExecutionTimelineEnabled(event.newValue),
            });
            break;
        case exports.DEEP_LINK_REAUTH_STORAGE_KEY:
            syncDeepLinkReauthFromStorage(event.newValue);
            break;
        case exports.TELEGRAM_NOTIFICATION_SETTINGS_STORAGE_KEY:
            syncTelegramNotificationSettingsFromStorage();
            break;
        case i18nStore_1.LOCALE_STORAGE_KEY:
            syncLocaleFromStorage(event.newValue);
            break;
        default:
            break;
    }
}
// Apply on load
(0, themes_1.applyThemeToDocument)(loadTheme());
exports.__test = {
    coerceTelegramNotificationSettings,
    createDefaultTelegramNotificationSettings,
    loadTelegramNotificationSettings,
    normalizeTelegramDigestCadence,
};
