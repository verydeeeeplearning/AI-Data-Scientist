"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SettingsPage = SettingsPage;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_i18next_1 = require("react-i18next");
const WsProvider_1 = require("../../renderer/hooks/WsProvider");
const configStore_1 = require("../../renderer/stores/configStore");
const runtimeStore_1 = require("../../renderer/stores/runtimeStore");
const PushOptInCard_1 = require("../components/PushOptInCard");
const runtime_1 = require("../runtime");
function formatEpoch(seconds) {
    if (!seconds) {
        return '-';
    }
    return new Date(seconds * 1000).toLocaleString();
}
function SettingsPage() {
    const { t } = (0, react_i18next_1.useTranslation)('mobile');
    const { status, disconnectReason } = (0, WsProvider_1.useWs)();
    const locale = (0, configStore_1.useConfigStore)((state) => state.theme);
    const sessions = (0, runtimeStore_1.useRuntimeStore)((state) => state.sessions.slice(0, 5));
    const connection = (0, runtime_1.describeMobileConnection)(status, disconnectReason);
    return ((0, jsx_runtime_1.jsxs)("div", { className: "flex flex-col gap-3 p-4", children: [(0, jsx_runtime_1.jsx)("h1", { className: "text-lg font-semibold text-ds-text", children: t('nav.settings') }), (0, jsx_runtime_1.jsx)("p", { className: "text-sm text-ds-muted", children: t('settings.description') }), (0, jsx_runtime_1.jsxs)("section", { className: "rounded-2xl border border-ds-border bg-ds-surface/70 p-4", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-start justify-between gap-3", children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("h2", { className: "text-sm font-semibold text-ds-text", children: t('settings.connection.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1 text-xs leading-5 text-ds-muted", children: t('settings.connection.description') })] }), (0, jsx_runtime_1.jsx)("span", { className: `rounded-full px-2 py-1 text-[11px] font-medium ${connection.tone === 'success'
                                    ? 'bg-emerald-500/10 text-emerald-300'
                                    : connection.tone === 'warning'
                                        ? 'bg-amber-500/10 text-amber-200'
                                        : 'bg-rose-500/10 text-rose-200'}`, children: t(connection.labelKey) })] }), (0, jsx_runtime_1.jsx)("p", { className: "mt-3 text-sm text-ds-text", children: t(connection.detailKey) })] }), (0, jsx_runtime_1.jsxs)("section", { className: "rounded-2xl border border-ds-border bg-ds-surface/70 p-4", children: [(0, jsx_runtime_1.jsx)("h2", { className: "text-sm font-semibold text-ds-text", children: t('settings.sessions.title') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-4 space-y-3", children: sessions.length === 0 ? ((0, jsx_runtime_1.jsx)("div", { className: "rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3 text-sm text-ds-muted", children: t('settings.sessions.empty') })) : (sessions.map((session) => ((0, jsx_runtime_1.jsxs)("article", { className: "rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-sm font-medium text-ds-text", children: session.sessionLabel || session.sessionId }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1 text-xs text-ds-muted", children: session.surface }), (0, jsx_runtime_1.jsxs)("div", { className: "mt-2 text-xs text-ds-muted", children: [t('settings.sessions.updated'), ": ", formatEpoch(session.lastActive)] })] }, session.sessionId)))) })] }), (0, jsx_runtime_1.jsx)(PushOptInCard_1.PushOptInCard, {}), (0, jsx_runtime_1.jsxs)("section", { className: "rounded-2xl border border-ds-border bg-ds-surface/70 p-4", children: [(0, jsx_runtime_1.jsx)("h2", { className: "text-sm font-semibold text-ds-text", children: t('settings.device.title') }), (0, jsx_runtime_1.jsxs)("div", { className: "mt-4 rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[11px] uppercase tracking-[0.16em] text-ds-muted", children: t('settings.device.theme') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-2 text-sm font-medium text-ds-text", children: locale })] })] })] }));
}
