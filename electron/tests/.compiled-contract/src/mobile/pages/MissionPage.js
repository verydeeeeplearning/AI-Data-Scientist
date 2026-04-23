"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MissionPage = MissionPage;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_i18next_1 = require("react-i18next");
const WsProvider_1 = require("../../renderer/hooks/WsProvider");
const agentStore_1 = require("../../renderer/stores/agentStore");
const runtimeStore_1 = require("../../renderer/stores/runtimeStore");
const workflowStore_1 = require("../../renderer/stores/workflowStore");
const runtime_1 = require("../runtime");
function MissionPage() {
    const { t } = (0, react_i18next_1.useTranslation)('mobile');
    const { status, disconnectReason } = (0, WsProvider_1.useWs)();
    const { model, mode } = (0, agentStore_1.useAgentStore)((state) => ({
        model: state.model,
        mode: state.mode,
    }));
    const runtimeStatus = (0, runtimeStore_1.useRuntimeStore)((state) => state.status);
    const pendingApprovals = (0, workflowStore_1.useWorkflowStore)((state) => state.approvals.filter((approval) => approval.status === 'pending').length);
    const connection = (0, runtime_1.describeMobileConnection)(status, disconnectReason);
    const stats = [
        {
            label: t('mission.stat.sessions'),
            value: String(runtimeStatus?.activeSessions ?? 0),
        },
        {
            label: t('mission.stat.runs'),
            value: String(runtimeStatus?.activeRuns ?? 0),
        },
        {
            label: t('mission.stat.tasks'),
            value: String(runtimeStatus?.activeTasks ?? 0),
        },
        {
            label: t('mission.stat.approvals'),
            value: String(pendingApprovals),
        },
    ];
    return ((0, jsx_runtime_1.jsxs)("div", { className: "flex flex-col gap-3 p-4", children: [(0, jsx_runtime_1.jsx)("h1", { className: "text-lg font-semibold text-ds-text", children: t('nav.mission') }), (0, jsx_runtime_1.jsx)("span", { className: "text-xs text-ds-muted", children: t('status.readOnly') }), (0, jsx_runtime_1.jsx)("p", { className: "text-sm text-ds-muted", children: t('mission.description') }), (0, jsx_runtime_1.jsxs)("section", { className: "rounded-2xl border border-ds-border bg-ds-surface/70 p-4", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-start justify-between gap-3", children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("h2", { className: "text-sm font-semibold text-ds-text", children: t('mission.connection.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1 text-xs leading-5 text-ds-muted", children: t('mission.connection.description') })] }), (0, jsx_runtime_1.jsx)("span", { className: `rounded-full px-2 py-1 text-[11px] font-medium ${connection.tone === 'success'
                                    ? 'bg-emerald-500/10 text-emerald-300'
                                    : connection.tone === 'warning'
                                        ? 'bg-amber-500/10 text-amber-200'
                                        : 'bg-rose-500/10 text-rose-200'}`, children: t(connection.labelKey) })] }), (0, jsx_runtime_1.jsx)("p", { className: "mt-3 text-sm text-ds-text", children: t(connection.detailKey) })] }), (0, jsx_runtime_1.jsxs)("section", { className: "rounded-2xl border border-ds-border bg-ds-surface/70 p-4", children: [(0, jsx_runtime_1.jsx)("h2", { className: "text-sm font-semibold text-ds-text", children: t('mission.runtimeSummary.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1 text-xs leading-5 text-ds-muted", children: t('mission.runtimeSummary.description') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-4 grid grid-cols-2 gap-3", children: stats.map((item) => ((0, jsx_runtime_1.jsxs)("div", { className: "rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[11px] uppercase tracking-[0.16em] text-ds-muted", children: item.label }), (0, jsx_runtime_1.jsx)("div", { className: "mt-2 text-lg font-semibold text-ds-text", children: item.value })] }, item.label))) })] }), (0, jsx_runtime_1.jsxs)("section", { className: "rounded-2xl border border-ds-border bg-ds-surface/70 p-4", children: [(0, jsx_runtime_1.jsx)("h2", { className: "text-sm font-semibold text-ds-text", children: t('mission.session.title') }), (0, jsx_runtime_1.jsxs)("div", { className: "mt-4 space-y-3", children: [(0, jsx_runtime_1.jsxs)("div", { className: "rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[11px] uppercase tracking-[0.16em] text-ds-muted", children: t('mission.stat.model') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-2 text-sm font-medium text-ds-text", children: model || t('common.none') })] }), (0, jsx_runtime_1.jsxs)("div", { className: "rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[11px] uppercase tracking-[0.16em] text-ds-muted", children: t('mission.stat.mode') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-2 text-sm font-medium text-ds-text", children: mode || t('common.none') })] })] })] })] }));
}
