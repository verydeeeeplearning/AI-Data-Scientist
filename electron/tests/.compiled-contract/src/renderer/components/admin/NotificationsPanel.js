"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.NotificationsPanel = NotificationsPanel;
exports.statusBadgeClass = statusBadgeClass;
const jsx_runtime_1 = require("react/jsx-runtime");
const lucide_react_1 = require("lucide-react");
const TelegramConnectFlow_1 = require("../settings/telegram/TelegramConnectFlow");
const TelegramNotificationSettings_1 = require("../settings/TelegramNotificationSettings");
const i18nStore_1 = require("../../stores/i18nStore");
const telegramStore_1 = require("../../stores/telegramStore");
function NotificationsPanel({ rpc }) {
    const { t } = (0, i18nStore_1.useI18n)();
    const telegramStatus = (0, telegramStore_1.useTelegramStore)((state) => state.status);
    const pairedChat = (0, telegramStore_1.useTelegramStore)((state) => state.pairedChat);
    const lastError = (0, telegramStore_1.useTelegramStore)((state) => state.lastError);
    return ((0, jsx_runtime_1.jsxs)("div", { className: "space-y-4", children: [(0, jsx_runtime_1.jsxs)("section", { className: "rounded-lg border border-ds-border bg-ds-surface p-4", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex flex-wrap items-start justify-between gap-3", children: [(0, jsx_runtime_1.jsxs)("div", { className: "min-w-0", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-center gap-2 text-sm font-semibold text-ds-text", children: [(0, jsx_runtime_1.jsx)(lucide_react_1.MessageCircle, { size: 16, "aria-hidden": "true" }), (0, jsx_runtime_1.jsx)("span", { children: t('settings.notifications.title') })] }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1 text-xs leading-5 text-ds-muted", children: t('settings.notifications.description') })] }), (0, jsx_runtime_1.jsx)("span", { className: `rounded-full px-2 py-1 text-[10px] font-medium ${statusBadgeClass(telegramStatus, Boolean(pairedChat))}`, children: pairedChat
                                    ? t('settings.telegramConnect.status.connected')
                                    : t(`settings.telegramConnect.status.${telegramStatus}`) })] }), lastError ? ((0, jsx_runtime_1.jsx)("div", { className: "mt-3 rounded-lg border border-ds-error/30 bg-ds-error/10 px-3 py-2 text-[11px] text-ds-error", children: lastError })) : null] }), (0, jsx_runtime_1.jsx)(TelegramConnectFlow_1.TelegramConnectFlow, { rpc: rpc, embedded: true }), (0, jsx_runtime_1.jsx)(TelegramNotificationSettings_1.TelegramNotificationSettings, { rpc: rpc }), (0, jsx_runtime_1.jsxs)("div", { className: "grid gap-3 md:grid-cols-2", children: [(0, jsx_runtime_1.jsx)(ComingSoonChannel, { icon: (0, jsx_runtime_1.jsx)(lucide_react_1.Hash, { size: 15, "aria-hidden": "true" }), title: t('settings.notifications.slack.title'), badge: t('settings.notifications.comingSoon') }), (0, jsx_runtime_1.jsx)(ComingSoonChannel, { icon: (0, jsx_runtime_1.jsx)(lucide_react_1.Mail, { size: 15, "aria-hidden": "true" }), title: t('settings.notifications.email.title'), badge: t('settings.notifications.comingSoon') })] })] }));
}
function ComingSoonChannel({ badge, icon, title, }) {
    return ((0, jsx_runtime_1.jsx)("section", { "aria-disabled": "true", className: "rounded-lg border border-ds-border bg-ds-surface/60 p-4 opacity-70", children: (0, jsx_runtime_1.jsxs)("div", { className: "flex items-center justify-between gap-3", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex min-w-0 items-center gap-2 text-sm font-semibold text-ds-text", children: [(0, jsx_runtime_1.jsx)("span", { className: "text-ds-muted", children: icon }), (0, jsx_runtime_1.jsx)("span", { children: title })] }), (0, jsx_runtime_1.jsx)("span", { className: "rounded-full bg-ds-bg px-2 py-1 text-[10px] font-medium text-ds-muted", children: badge })] }) }));
}
function statusBadgeClass(status, paired) {
    if (status === 'running' && paired) {
        return 'bg-ds-success/15 text-ds-success';
    }
    if (status === 'error') {
        return 'bg-ds-error/15 text-ds-error';
    }
    if (status === 'starting' || status === 'stopping' || status === 'running') {
        return 'bg-ds-warning/15 text-ds-warning';
    }
    return 'bg-ds-bg text-ds-muted';
}
