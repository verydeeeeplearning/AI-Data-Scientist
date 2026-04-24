"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ApprovalsPage = ApprovalsPage;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const react_i18next_1 = require("react-i18next");
const lucide_react_1 = require("lucide-react");
const WsProvider_1 = require("../../renderer/hooks/WsProvider");
const workflowStore_1 = require("../../renderer/stores/workflowStore");
const useAccessRole_1 = require("../../renderer/hooks/useAccessRole");
const approvalAdapter_1 = require("../approvals/approvalAdapter");
const mobileError_1 = require("../errors/mobileError");
const indexedDbOutbox_1 = require("../outbox/indexedDbOutbox");
function ApprovalsPage() {
    const { t } = (0, react_i18next_1.useTranslation)('mobile');
    const { rpc, status } = (0, WsProvider_1.useWs)();
    const approvals = (0, workflowStore_1.useWorkflowStore)((state) => state.approvals);
    const { isViewer } = (0, useAccessRole_1.useAccessRole)();
    const [busyId, setBusyId] = (0, react_1.useState)(null);
    const [errorId, setErrorId] = (0, react_1.useState)(null);
    const [errorKey, setErrorKey] = (0, react_1.useState)(null);
    const [pending, setPending] = (0, react_1.useState)(null);
    const [queuedCount, setQueuedCount] = (0, react_1.useState)(0);
    const [queueMessage, setQueueMessage] = (0, react_1.useState)(null);
    const views = (0, react_1.useMemo)(() => (0, approvalAdapter_1.selectPendingApprovals)(approvals).map(approvalAdapter_1.toMobileApprovalView), [approvals]);
    const connected = status === 'connected';
    (0, react_1.useEffect)(() => {
        let cancelled = false;
        const refreshQueuedCount = async () => {
            const count = await (0, approvalAdapter_1.getQueuedApprovalCount)();
            if (!cancelled) {
                setQueuedCount(count);
            }
        };
        const handleOutboxChanged = () => {
            void refreshQueuedCount();
        };
        void refreshQueuedCount();
        window.addEventListener(indexedDbOutbox_1.OUTBOX_CHANGED_EVENT, handleOutboxChanged);
        return () => {
            cancelled = true;
            window.removeEventListener(indexedDbOutbox_1.OUTBOX_CHANGED_EVENT, handleOutboxChanged);
        };
    }, []);
    const handleClick = (approval, decision) => {
        setErrorId(null);
        setErrorKey(null);
        if (decision === 'rejected' || approval.requiresConfirmation) {
            setPending({ approval, decision });
            return;
        }
        void runDecision(approval, decision);
    };
    const runDecision = async (approval, decision) => {
        setBusyId(approval.approvalId);
        let outcome;
        try {
            outcome = await (0, approvalAdapter_1.submitMobileApproval)(rpc, {
                approvalId: approval.approvalId,
                decision,
                response: decision === 'approved' ? approval.defaultResponse : null,
                actor: 'mobile',
            });
        }
        catch (error) {
            setBusyId(null);
            setErrorId(approval.approvalId);
            setErrorKey((0, mobileError_1.getApprovalErrorKey)((0, mobileError_1.resolveApprovalErrorCode)(error)));
            return;
        }
        setBusyId(null);
        if (outcome.queued) {
            setErrorId(null);
            setErrorKey(null);
            setQueueMessage(t('approvals.queue.saved'));
            return;
        }
        if (!outcome.ok) {
            setErrorId(approval.approvalId);
            setQueueMessage(null);
            setErrorKey((0, mobileError_1.getApprovalErrorKey)(outcome.errorCode ?? 'approval_submit_failed'));
            return;
        }
        setQueueMessage(null);
    };
    const handleConfirm = async () => {
        if (!pending)
            return;
        const snapshot = pending;
        setPending(null);
        await runDecision(snapshot.approval, snapshot.decision);
    };
    const handleCancel = () => {
        setPending(null);
    };
    return ((0, jsx_runtime_1.jsxs)("div", { className: "flex flex-col gap-3 p-4", children: [(0, jsx_runtime_1.jsx)("h1", { className: "text-lg font-semibold text-ds-text", children: t('nav.approvals') }), (0, jsx_runtime_1.jsx)("p", { className: "text-sm text-ds-muted", children: t('approvals.description') }), isViewer && ((0, jsx_runtime_1.jsxs)("section", { role: "status", className: "rounded-2xl border border-ds-border bg-ds-surface/70 p-4 text-sm text-ds-muted", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-center gap-2 text-ds-text", children: [(0, jsx_runtime_1.jsx)(lucide_react_1.ShieldAlert, { size: 16, "aria-hidden": "true" }), (0, jsx_runtime_1.jsx)("span", { className: "font-medium", children: t('approvals.viewer.title') })] }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2", children: t('approvals.viewer.description') })] })), !connected && ((0, jsx_runtime_1.jsx)("section", { role: "status", className: "rounded-2xl border border-ds-border bg-ds-surface/70 p-4 text-sm text-ds-muted", children: t('approvals.connection.waiting') })), (queuedCount > 0 || queueMessage) && ((0, jsx_runtime_1.jsxs)("section", { role: "status", className: "rounded-2xl border border-ds-border bg-ds-surface/70 p-4 text-sm text-ds-muted", children: [(0, jsx_runtime_1.jsx)("div", { className: "font-medium text-ds-text", children: t('approvals.queue.title') }), queuedCount > 0 ? ((0, jsx_runtime_1.jsx)("p", { className: "mt-2", children: t('approvals.queue.count', { count: queuedCount }) })) : null, queueMessage ? (0, jsx_runtime_1.jsx)("p", { className: "mt-2", children: queueMessage }) : null] })), (0, jsx_runtime_1.jsxs)("section", { className: "rounded-2xl border border-ds-border bg-ds-surface/70 p-4", children: [(0, jsx_runtime_1.jsx)("h2", { className: "text-sm font-semibold text-ds-text", children: t('approvals.list.title') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-4 space-y-3", children: views.length === 0 ? ((0, jsx_runtime_1.jsx)("div", { className: "rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3 text-sm text-ds-muted", children: t('approvals.list.empty') })) : (views.map((view) => ((0, jsx_runtime_1.jsx)(ApprovalRow, { view: view, disabled: isViewer || !connected || busyId === view.approvalId, busy: busyId === view.approvalId, errorKey: errorId === view.approvalId ? errorKey : null, onAct: (decision) => handleClick(view, decision), t: t }, view.approvalId)))) })] }), pending && ((0, jsx_runtime_1.jsx)(ConfirmSheet, { view: pending.approval, decision: pending.decision, onConfirm: () => void handleConfirm(), onCancel: handleCancel }))] }));
}
function ApprovalRow({ view, disabled, busy, errorKey, onAct, t, }) {
    return ((0, jsx_runtime_1.jsxs)("article", { className: "rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3", "aria-busy": busy, children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-start justify-between gap-3", children: [(0, jsx_runtime_1.jsxs)("div", { className: "min-w-0", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-sm font-medium text-ds-text", children: view.question }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1 break-all text-[11px] text-ds-muted", children: view.approvalId })] }), view.risk && ((0, jsx_runtime_1.jsx)("span", { className: `shrink-0 rounded-full px-2 py-1 text-[11px] font-medium ${view.risk === 'high'
                            ? 'bg-rose-500/10 text-rose-200'
                            : view.risk === 'medium'
                                ? 'bg-amber-500/10 text-amber-200'
                                : 'bg-emerald-500/10 text-emerald-300'}`, children: t(`approvals.risk.${view.risk}`) }))] }), view.proposalType && ((0, jsx_runtime_1.jsxs)("div", { className: "mt-2 text-[11px] text-ds-muted", children: [t('approvals.field.type'), ": ", (0, jsx_runtime_1.jsx)("span", { className: "text-ds-text", children: view.proposalType })] })), view.targetId && ((0, jsx_runtime_1.jsxs)("div", { className: "mt-1 break-all text-[11px] text-ds-muted", children: [t('approvals.field.target'), ": ", (0, jsx_runtime_1.jsx)("span", { className: "text-ds-text", children: view.targetId })] })), (0, jsx_runtime_1.jsxs)("div", { className: "mt-3 flex flex-wrap gap-2", children: [(0, jsx_runtime_1.jsxs)("button", { type: "button", "aria-label": `${t('approvals.action.approve')} ${view.approvalId}`, onClick: () => onAct('approved'), disabled: disabled, style: {
                            minHeight: '44px',
                            minWidth: '44px',
                            flex: '1 1 140px',
                            padding: '0 12px',
                            borderRadius: '12px',
                            border: '1px solid var(--ds-border)',
                            background: disabled ? 'var(--ds-surface)' : 'var(--ds-accent)',
                            color: disabled ? 'var(--ds-muted)' : 'var(--ds-bg)',
                            fontSize: '14px',
                            fontWeight: 600,
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '6px',
                            cursor: disabled ? 'not-allowed' : 'pointer',
                        }, children: [(0, jsx_runtime_1.jsx)(lucide_react_1.Check, { size: 16, "aria-hidden": "true" }), t('approvals.action.approve')] }), (0, jsx_runtime_1.jsxs)("button", { type: "button", "aria-label": `${t('approvals.action.reject')} ${view.approvalId}`, onClick: () => onAct('rejected'), disabled: disabled, style: {
                            minHeight: '44px',
                            minWidth: '44px',
                            flex: '1 1 140px',
                            padding: '0 12px',
                            borderRadius: '12px',
                            border: '1px solid var(--ds-border)',
                            background: 'transparent',
                            color: 'var(--ds-text)',
                            fontSize: '14px',
                            fontWeight: 600,
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '6px',
                            cursor: disabled ? 'not-allowed' : 'pointer',
                        }, children: [(0, jsx_runtime_1.jsx)(lucide_react_1.X, { size: 16, "aria-hidden": "true" }), t('approvals.action.reject')] })] }), errorKey && ((0, jsx_runtime_1.jsxs)("div", { role: "alert", className: "mt-3 text-xs text-rose-300", children: [t('approvals.error.submit'), ": ", t(errorKey)] }))] }));
}
function ConfirmSheet({ view, decision, onConfirm, onCancel, }) {
    const { t } = (0, react_i18next_1.useTranslation)('mobile');
    const titleKey = decision === 'approved'
        ? 'approvals.confirm.approve.title'
        : 'approvals.confirm.reject.title';
    const bodyKey = decision === 'approved'
        ? 'approvals.confirm.approve.body'
        : 'approvals.confirm.reject.body';
    return ((0, jsx_runtime_1.jsx)("div", { role: "dialog", "aria-modal": "true", "aria-labelledby": "mobile-approval-confirm-title", style: {
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'center',
            zIndex: 50,
        }, onClick: onCancel, children: (0, jsx_runtime_1.jsxs)("div", { onClick: (event) => event.stopPropagation(), style: {
                width: '100%',
                maxWidth: '480px',
                background: 'var(--ds-surface)',
                color: 'var(--ds-text)',
                borderTopLeftRadius: '20px',
                borderTopRightRadius: '20px',
                padding: '20px 16px calc(20px + env(safe-area-inset-bottom, 0px))',
                boxShadow: '0 -4px 20px rgba(0,0,0,0.4)',
            }, children: [(0, jsx_runtime_1.jsx)("h2", { id: "mobile-approval-confirm-title", style: { fontSize: '16px', fontWeight: 600, margin: 0 }, children: t(titleKey) }), (0, jsx_runtime_1.jsx)("p", { style: { marginTop: '8px', fontSize: '13px', color: 'var(--ds-muted)' }, children: t(bodyKey) }), (0, jsx_runtime_1.jsx)("div", { style: {
                        marginTop: '12px',
                        padding: '12px',
                        border: '1px solid var(--ds-border)',
                        borderRadius: '12px',
                        fontSize: '13px',
                    }, children: view.question }), (0, jsx_runtime_1.jsxs)("div", { style: { marginTop: '16px', display: 'flex', gap: '8px' }, children: [(0, jsx_runtime_1.jsx)("button", { type: "button", onClick: onCancel, style: {
                                flex: 1,
                                minHeight: '44px',
                                borderRadius: '12px',
                                border: '1px solid var(--ds-border)',
                                background: 'transparent',
                                color: 'var(--ds-text)',
                                fontWeight: 600,
                                cursor: 'pointer',
                            }, children: t('approvals.confirm.cancel') }), (0, jsx_runtime_1.jsx)("button", { type: "button", onClick: onConfirm, style: {
                                flex: 1,
                                minHeight: '44px',
                                borderRadius: '12px',
                                border: 'none',
                                background: decision === 'rejected'
                                    ? 'rgba(244, 63, 94, 0.85)'
                                    : 'var(--ds-accent)',
                                color: decision === 'rejected' ? '#fff' : 'var(--ds-bg)',
                                fontWeight: 600,
                                cursor: 'pointer',
                            }, children: t('approvals.confirm.proceed') })] })] }) }));
}
