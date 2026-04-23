"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.__test = void 0;
exports.TelegramNotificationSettings = TelegramNotificationSettings;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const primitives_1 = require("../../design-system/primitives");
const configStore_1 = require("../../stores/configStore");
const i18nStore_1 = require("../../stores/i18nStore");
const DIGEST_CADENCE_OPTIONS = [
    { value: 'interval', labelKey: 'settings.telegram.digestCadence.interval' },
    { value: 'hourly', labelKey: 'settings.telegram.digestCadence.hourly' },
    { value: 'morning', labelKey: 'settings.telegram.digestCadence.morning' },
    { value: 'end_of_day', labelKey: 'settings.telegram.digestCadence.endOfDay' },
];
const DEFAULT_FALLBACK_TIMEZONE = 'UTC';
function TelegramNotificationSettings({ rpc }) {
    const { t, locale } = (0, i18nStore_1.useI18n)();
    const settings = (0, configStore_1.useConfigStore)((state) => state.telegramNotificationSettings);
    const source = (0, configStore_1.useConfigStore)((state) => state.telegramNotificationSettingsSource);
    const updateSettings = (0, configStore_1.useConfigStore)((state) => state.updateTelegramNotificationSettings);
    const hydrateFromWorkspace = (0, configStore_1.useConfigStore)((state) => state.hydrateTelegramNotificationSettingsFromWorkspace);
    const replaceSettings = (0, configStore_1.useConfigStore)((state) => state.replaceTelegramNotificationSettings);
    const resetSettings = (0, configStore_1.useConfigStore)((state) => state.resetTelegramNotificationSettings);
    const [snapshot, setSnapshot] = (0, react_1.useState)(null);
    const [selectedChatId, setSelectedChatId] = (0, react_1.useState)('');
    const [loading, setLoading] = (0, react_1.useState)(true);
    const [loadError, setLoadError] = (0, react_1.useState)(null);
    const selectedPreference = (0, react_1.useMemo)(() => {
        if (!snapshot?.chatPreferences.length) {
            return null;
        }
        return (snapshot.chatPreferences.find((entry) => entry.chatId === selectedChatId)
            ?? snapshot.chatPreferences[0]);
    }, [selectedChatId, snapshot?.chatPreferences]);
    const snapshotDraft = (0, react_1.useMemo)(() => buildDraftFromWorkspace(selectedPreference, snapshot?.deliveryPolicy ?? null), [selectedPreference, snapshot?.deliveryPolicy]);
    const timezoneError = (0, react_1.useMemo)(() => validateTimeZone(settings.timezone, t('settings.telegram.timezone.invalid')), [settings.timezone, t]);
    const quietHoursTimezoneError = (0, react_1.useMemo)(() => validateTimeZone(settings.quietHoursTimezone, t('settings.telegram.timezone.invalid')), [settings.quietHoursTimezone, t]);
    const refreshSnapshot = (0, react_1.useCallback)(async () => {
        setLoading(true);
        setLoadError(null);
        const [preferencesResult, policyResult] = await Promise.all([
            loadWorkspaceJsonSnapshot(rpc, '.ds_agent/operator_preferences.json'),
            loadWorkspaceJsonSnapshot(rpc, '.ds_agent/delivery_policy.json'),
        ]);
        const nextSnapshot = {
            chatPreferences: parseOperatorPreferences(preferencesResult.data),
            deliveryPolicy: parseDeliveryPolicy(policyResult.data),
        };
        const errors = [preferencesResult.error, policyResult.error].filter((value) => Boolean(value));
        setSnapshot(nextSnapshot);
        setSelectedChatId((current) => {
            if (current
                && nextSnapshot.chatPreferences.some((entry) => entry.chatId === current)) {
                return current;
            }
            return nextSnapshot.chatPreferences[0]?.chatId ?? '';
        });
        setLoadError(errors[0] ?? null);
        setLoading(false);
    }, [rpc]);
    (0, react_1.useEffect)(() => {
        void refreshSnapshot();
    }, [refreshSnapshot]);
    (0, react_1.useEffect)(() => {
        if (!snapshotDraft) {
            return;
        }
        hydrateFromWorkspace(snapshotDraft);
    }, [hydrateFromWorkspace, snapshotDraft]);
    const sourceLabelKey = source === 'local'
        ? 'settings.telegram.editor.source.local'
        : source === 'workspace'
            ? 'settings.telegram.editor.source.workspace'
            : 'settings.telegram.editor.source.default';
    const copySnapshotToEditor = () => {
        if (!snapshotDraft) {
            return;
        }
        replaceSettings(snapshotDraft, 'workspace');
    };
    return ((0, jsx_runtime_1.jsxs)("div", { className: "space-y-4", children: [(0, jsx_runtime_1.jsxs)("div", { className: "rounded-lg border border-ds-border bg-ds-bg p-3", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex flex-wrap items-start justify-between gap-3", children: [(0, jsx_runtime_1.jsxs)("div", { className: "space-y-1", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-xs font-medium text-ds-text", children: t('settings.telegram.title') }), (0, jsx_runtime_1.jsx)("p", { className: "text-[11px] leading-5 text-ds-muted", children: t('settings.telegram.description') })] }), (0, jsx_runtime_1.jsx)("span", { className: "rounded-full bg-ds-surface px-2 py-1 text-[10px] font-medium text-ds-muted", children: t(sourceLabelKey) })] }), (0, jsx_runtime_1.jsx)("p", { className: "mt-3 text-[11px] leading-5 text-ds-muted", children: t('settings.telegram.localOnly') })] }), (0, jsx_runtime_1.jsxs)("div", { className: "rounded-lg border border-ds-border bg-ds-bg p-3", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex flex-wrap items-start justify-between gap-3", children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-xs font-medium text-ds-text", children: t('settings.telegram.snapshot.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1 text-[11px] leading-5 text-ds-muted", children: t('settings.telegram.snapshot.description') })] }), (0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "ghost", size: "sm", onClick: () => void refreshSnapshot(), loading: loading, children: t('settings.telegram.snapshot.refresh') })] }), loadError ? ((0, jsx_runtime_1.jsx)("div", { className: "mt-3 rounded-lg border border-ds-error/30 bg-ds-error/10 px-3 py-2 text-[11px] text-ds-error", children: loadError })) : null, snapshot?.chatPreferences.length ? ((0, jsx_runtime_1.jsxs)("div", { className: "mt-3 space-y-3", children: [(0, jsx_runtime_1.jsx)(primitives_1.Select, { id: "telegram-snapshot-chat", label: t('settings.telegram.snapshot.chat'), description: t('settings.telegram.snapshot.chatDescription'), value: selectedPreference?.chatId ?? '', onChange: (event) => setSelectedChatId(event.target.value), options: snapshot.chatPreferences.map((entry) => ({
                                    value: entry.chatId,
                                    label: entry.chatId,
                                })) }), (0, jsx_runtime_1.jsx)(SnapshotRow, { label: t('settings.telegram.snapshot.digest'), value: formatDigestSummary(selectedPreference, t) }), (0, jsx_runtime_1.jsx)(SnapshotRow, { label: t('settings.telegram.snapshot.quietHours'), value: formatQuietHoursSummary(snapshot.deliveryPolicy, t) }), (0, jsx_runtime_1.jsx)(SnapshotRow, { label: t('settings.telegram.snapshot.policy'), value: formatPolicySummary(snapshot.deliveryPolicy, t) }), selectedPreference?.updatedAt ? ((0, jsx_runtime_1.jsx)(SnapshotRow, { label: t('settings.telegram.snapshot.updated'), value: new Date(selectedPreference.updatedAt * 1000).toLocaleString(locale) })) : null, (0, jsx_runtime_1.jsxs)("div", { className: "flex flex-wrap gap-2 pt-1", children: [(0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "secondary", size: "sm", onClick: copySnapshotToEditor, disabled: !snapshotDraft, children: t('settings.telegram.snapshot.copy') }), (0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "ghost", size: "sm", onClick: resetSettings, children: t('settings.telegram.editor.reset') })] })] })) : ((0, jsx_runtime_1.jsx)("div", { className: "mt-3 rounded-lg border border-ds-border/50 bg-ds-surface px-3 py-2 text-[11px] leading-5 text-ds-muted", children: snapshot?.deliveryPolicy
                            ? t('settings.telegram.snapshot.policyOnly')
                            : t('settings.telegram.snapshot.empty') }))] }), (0, jsx_runtime_1.jsxs)("div", { className: "space-y-4 rounded-lg border border-ds-border bg-ds-bg p-3", children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-xs font-medium text-ds-text", children: t('settings.telegram.editor.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1 text-[11px] leading-5 text-ds-muted", children: t('settings.telegram.editor.description') })] }), (0, jsx_runtime_1.jsx)(primitives_1.Checkbox, { checked: settings.digestEnabled, onChange: (event) => updateSettings({
                            digestEnabled: event.target.checked,
                        }), label: t('settings.telegram.editor.digestEnabled'), description: t('settings.telegram.editor.digestEnabledDescription') }), (0, jsx_runtime_1.jsxs)("div", { className: "grid gap-3 md:grid-cols-[minmax(0,1fr)_180px]", children: [(0, jsx_runtime_1.jsx)(primitives_1.Select, { id: "telegram-digest-cadence", label: t('settings.telegram.editor.digestCadence'), description: t('settings.telegram.editor.digestCadenceDescription'), value: settings.digestCadence, onChange: (event) => updateSettings({
                                    digestCadence: event.target.value,
                                }), options: DIGEST_CADENCE_OPTIONS.map((option) => ({
                                    value: option.value,
                                    label: t(option.labelKey),
                                })) }), (0, jsx_runtime_1.jsx)(primitives_1.Input, { id: "telegram-digest-interval", type: "number", min: 1, step: 1, label: t('settings.telegram.editor.digestInterval'), description: t('settings.telegram.editor.digestIntervalDescription'), value: String(settings.digestIntervalMinutes), onChange: (event) => updateSettings({
                                    digestIntervalMinutes: normalizeIntervalMinutes(event.target.value),
                                }), disabled: settings.digestCadence !== 'interval' })] }), (0, jsx_runtime_1.jsx)(primitives_1.Input, { id: "telegram-digest-timezone", label: t('settings.telegram.editor.timezone'), description: t('settings.telegram.editor.timezoneDescription'), value: settings.timezone, onChange: (event) => updateSettings({
                            timezone: event.target.value,
                        }), errorMessage: timezoneError, placeholder: t('settings.telegram.timezone.placeholder') }), (0, jsx_runtime_1.jsx)(primitives_1.Checkbox, { checked: settings.quietHoursEnabled, onChange: (event) => updateSettings({
                            quietHoursEnabled: event.target.checked,
                        }), label: t('settings.telegram.editor.quietHoursEnabled'), description: t('settings.telegram.editor.quietHoursEnabledDescription') }), (0, jsx_runtime_1.jsxs)("div", { className: "grid gap-3 md:grid-cols-3", children: [(0, jsx_runtime_1.jsx)(primitives_1.Input, { id: "telegram-quiet-hours-start", type: "time", label: t('settings.telegram.editor.quietHoursStart'), value: settings.quietHoursStart, onChange: (event) => updateSettings({
                                    quietHoursStart: normalizeTimeValue(event.target.value, settings.quietHoursStart),
                                }), disabled: !settings.quietHoursEnabled }), (0, jsx_runtime_1.jsx)(primitives_1.Input, { id: "telegram-quiet-hours-end", type: "time", label: t('settings.telegram.editor.quietHoursEnd'), value: settings.quietHoursEnd, onChange: (event) => updateSettings({
                                    quietHoursEnd: normalizeTimeValue(event.target.value, settings.quietHoursEnd),
                                }), disabled: !settings.quietHoursEnabled }), (0, jsx_runtime_1.jsx)(primitives_1.Input, { id: "telegram-quiet-hours-timezone", label: t('settings.telegram.editor.quietHoursTimezone'), value: settings.quietHoursTimezone, onChange: (event) => updateSettings({
                                    quietHoursTimezone: event.target.value,
                                }), errorMessage: settings.quietHoursEnabled ? quietHoursTimezoneError : undefined, placeholder: t('settings.telegram.timezone.placeholder'), disabled: !settings.quietHoursEnabled })] }), (0, jsx_runtime_1.jsxs)("div", { className: "rounded-lg border border-ds-border/50 bg-ds-surface px-3 py-2", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[10px] uppercase tracking-wider text-ds-muted", children: t('settings.telegram.editor.summary') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1 text-[11px] text-ds-text", children: formatEditorSummary(settings, t) })] })] })] }));
}
function SnapshotRow({ label, value }) {
    return ((0, jsx_runtime_1.jsxs)("div", { className: "flex flex-wrap items-center justify-between gap-2 rounded-lg border border-ds-border/50 bg-ds-surface px-3 py-2 text-[11px]", children: [(0, jsx_runtime_1.jsx)("span", { className: "text-ds-muted", children: label }), (0, jsx_runtime_1.jsx)("span", { className: "font-medium text-ds-text", children: value })] }));
}
function isRecord(value) {
    return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}
function normalizeCadence(value) {
    if (typeof value !== 'string') {
        return 'interval';
    }
    const normalized = value.trim().toLowerCase();
    if (normalized === 'hourly') {
        return 'hourly';
    }
    if (normalized === 'morning') {
        return 'morning';
    }
    if (normalized === 'eod' || normalized === 'end-of-day' || normalized === 'end_of_day') {
        return 'end_of_day';
    }
    return 'interval';
}
function normalizeIntervalMinutes(value) {
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
function normalizeIntervalSeconds(value) {
    if (typeof value !== 'number' || !Number.isFinite(value)) {
        return 15;
    }
    return Math.max(1, Math.round(value / 60));
}
function normalizeTimeValue(value, fallback) {
    if (typeof value !== 'string') {
        return fallback;
    }
    const trimmed = value.trim();
    return /^\d{2}:\d{2}$/.test(trimmed) ? trimmed : fallback;
}
function validateTimeZone(value, message) {
    const trimmed = value.trim();
    if (!trimmed) {
        return message;
    }
    try {
        new Intl.DateTimeFormat(undefined, { timeZone: trimmed });
        return undefined;
    }
    catch {
        return message;
    }
}
function parseOperatorPreferences(raw) {
    if (!isRecord(raw)) {
        return [];
    }
    return Object.entries(raw)
        .map(([chatId, value]) => {
        if (!isRecord(value)) {
            return null;
        }
        return {
            chatId: String(value.chat_id ?? chatId),
            digestEnabled: Boolean(value.digest_mode),
            digestCadence: normalizeCadence(value.digest_cadence),
            digestIntervalMinutes: normalizeIntervalSeconds(value.digest_interval_seconds),
            timezone: typeof value.timezone === 'string' && value.timezone.trim()
                ? value.timezone.trim()
                : DEFAULT_FALLBACK_TIMEZONE,
            updatedAt: typeof value.updated_at === 'number' && Number.isFinite(value.updated_at)
                ? value.updated_at
                : null,
        };
    })
        .filter((entry) => Boolean(entry))
        .sort((left, right) => {
        const leftUpdated = left.updatedAt ?? 0;
        const rightUpdated = right.updatedAt ?? 0;
        if (leftUpdated !== rightUpdated) {
            return rightUpdated - leftUpdated;
        }
        return left.chatId.localeCompare(right.chatId);
    });
}
function parseDeliveryPolicy(raw) {
    if (!isRecord(raw)) {
        return null;
    }
    const payload = isRecord(raw.default_policy) ? raw.default_policy : raw;
    return {
        digestEnabled: Boolean(payload.digest_enabled),
        digestIntervalMinutes: normalizeIntervalSeconds(payload.digest_interval_seconds),
        quietHoursStart: normalizeTimeValue(payload.quiet_hours_start, ''),
        quietHoursEnd: normalizeTimeValue(payload.quiet_hours_end, ''),
        quietHoursTimezone: typeof payload.quiet_hours_timezone === 'string' && payload.quiet_hours_timezone.trim()
            ? payload.quiet_hours_timezone.trim()
            : DEFAULT_FALLBACK_TIMEZONE,
    };
}
function buildDraftFromWorkspace(preference, policy) {
    if (!preference && !policy) {
        return null;
    }
    const digestTimeZone = preference?.timezone
        ?? policy?.quietHoursTimezone
        ?? DEFAULT_FALLBACK_TIMEZONE;
    const quietHoursEnabled = Boolean(policy?.quietHoursStart && policy?.quietHoursEnd);
    return {
        digestEnabled: preference?.digestEnabled ?? false,
        digestCadence: preference?.digestCadence ?? 'interval',
        digestIntervalMinutes: preference?.digestIntervalMinutes ?? policy?.digestIntervalMinutes ?? 15,
        timezone: digestTimeZone,
        quietHoursEnabled,
        quietHoursStart: policy?.quietHoursStart || '22:00',
        quietHoursEnd: policy?.quietHoursEnd || '07:00',
        quietHoursTimezone: policy?.quietHoursTimezone || digestTimeZone,
    };
}
async function loadWorkspaceJsonSnapshot(rpc, path) {
    try {
        const preview = (await rpc('files.preview', { path }));
        if (preview.kind !== 'text' || typeof preview.content !== 'string') {
            return {
                data: null,
                error: `Unsupported preview payload for ${path}.`,
            };
        }
        return {
            data: JSON.parse(preview.content),
            error: null,
        };
    }
    catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        if (message.includes('No such file')) {
            return { data: null, error: null };
        }
        return {
            data: null,
            error: message,
        };
    }
}
function formatCadenceLabel(cadence, intervalMinutes, t) {
    if (cadence === 'interval') {
        return t('settings.telegram.digestCadence.intervalSummary', {
            minutes: intervalMinutes,
        });
    }
    return t(`settings.telegram.digestCadence.${cadence === 'end_of_day' ? 'endOfDay' : cadence}`);
}
function formatDigestSummary(preference, t) {
    if (!preference) {
        return t('settings.telegram.snapshot.unavailable');
    }
    if (!preference.digestEnabled) {
        return t('settings.telegram.snapshot.digestDisabled', {
            timezone: preference.timezone,
        });
    }
    return t('settings.telegram.snapshot.digestEnabled', {
        cadence: formatCadenceLabel(preference.digestCadence, preference.digestIntervalMinutes, t),
        timezone: preference.timezone,
    });
}
function formatPolicySummary(policy, t) {
    if (!policy) {
        return t('settings.telegram.snapshot.unavailable');
    }
    if (!policy.digestEnabled) {
        return t('settings.telegram.snapshot.policyDigestDisabled');
    }
    return t('settings.telegram.snapshot.policyDigestEnabled', {
        cadence: formatCadenceLabel('interval', policy.digestIntervalMinutes, t),
    });
}
function formatQuietHoursSummary(policy, t) {
    if (!policy) {
        return t('settings.telegram.snapshot.unavailable');
    }
    if (!policy.quietHoursStart || !policy.quietHoursEnd) {
        return t('settings.telegram.snapshot.quietHoursDisabled');
    }
    return t('settings.telegram.snapshot.quietHoursEnabled', {
        start: policy.quietHoursStart,
        end: policy.quietHoursEnd,
        timezone: policy.quietHoursTimezone,
    });
}
function formatEditorSummary(settings, t) {
    const digestSummary = settings.digestEnabled
        ? t('settings.telegram.editor.digestSummaryEnabled', {
            cadence: formatCadenceLabel(settings.digestCadence, settings.digestIntervalMinutes, t),
            timezone: settings.timezone.trim() || DEFAULT_FALLBACK_TIMEZONE,
        })
        : t('settings.telegram.editor.digestSummaryDisabled', {
            timezone: settings.timezone.trim() || DEFAULT_FALLBACK_TIMEZONE,
        });
    const quietHoursSummary = settings.quietHoursEnabled
        ? t('settings.telegram.editor.quietHoursSummaryEnabled', {
            start: settings.quietHoursStart,
            end: settings.quietHoursEnd,
            timezone: settings.quietHoursTimezone.trim() || DEFAULT_FALLBACK_TIMEZONE,
        })
        : t('settings.telegram.editor.quietHoursSummaryDisabled');
    return `${digestSummary} | ${quietHoursSummary}`;
}
exports.__test = {
    buildDraftFromWorkspace,
    parseDeliveryPolicy,
    parseOperatorPreferences,
    validateTimeZone,
};
