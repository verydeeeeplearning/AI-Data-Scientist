"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ToastViewport = ToastViewport;
exports.Toast = Toast;
const jsx_runtime_1 = require("react/jsx-runtime");
const lucide_react_1 = require("lucide-react");
const utils_1 = require("./utils");
const VIEWPORT_PLACEMENT_CLASSES = {
    'top-left': 'left-4 top-4',
    'top-right': 'right-4 top-4',
    'bottom-left': 'bottom-4 left-4',
    'bottom-right': 'bottom-4 right-4',
};
const TONE_CLASSES = {
    neutral: {
        container: 'border-ds-border bg-ds-surface-elevated/96',
        icon: 'border-ds-border/70 bg-ds-bg/70 text-ds-muted',
    },
    info: {
        container: 'border-ds-info/30 bg-ds-info/10',
        icon: 'border-ds-info/30 bg-ds-info/15 text-ds-info',
    },
    success: {
        container: 'border-ds-success/30 bg-ds-success/10',
        icon: 'border-ds-success/30 bg-ds-success/15 text-ds-success',
    },
    warning: {
        container: 'border-ds-warning/30 bg-ds-warning/10',
        icon: 'border-ds-warning/30 bg-ds-warning/15 text-ds-warning',
    },
    danger: {
        container: 'border-ds-error/30 bg-ds-error/10',
        icon: 'border-ds-error/30 bg-ds-error/15 text-ds-error',
    },
};
function ToastViewport({ placement = 'bottom-right', label = 'Notifications', className, children, ...rest }) {
    return ((0, jsx_runtime_1.jsx)("div", { "aria-label": label, className: (0, utils_1.cn)('pointer-events-none fixed z-50 flex w-full max-w-ds-toast flex-col gap-ds-2 sm:w-auto', VIEWPORT_PLACEMENT_CLASSES[placement], className), role: "region", ...rest, children: children }));
}
function Toast({ title, description, meta, tone = 'neutral', leadingIcon, announce = 'polite', dismissLabel = 'Dismiss notification', onDismiss, className, children, ...rest }) {
    const role = announce === 'assertive' ? 'alert' : announce === 'off' ? 'group' : 'status';
    return ((0, jsx_runtime_1.jsx)("div", { "aria-live": announce === 'off' ? undefined : announce, className: (0, utils_1.cn)('pointer-events-auto rounded-ds-xl border px-ds-4 py-ds-3 text-ds-text shadow-ds-lg', TONE_CLASSES[tone].container, className), role: role, ...rest, children: (0, jsx_runtime_1.jsxs)("div", { className: "flex items-start gap-ds-3", children: [leadingIcon ? ((0, jsx_runtime_1.jsx)("div", { "aria-hidden": "true", className: (0, utils_1.cn)('mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-ds-pill border', TONE_CLASSES[tone].icon), children: leadingIcon })) : null, (0, jsx_runtime_1.jsx)("div", { className: "min-w-0 flex-1", children: (0, jsx_runtime_1.jsxs)("div", { className: "flex items-start gap-ds-2", children: [(0, jsx_runtime_1.jsxs)("div", { className: "min-w-0 flex-1 space-y-1", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-start justify-between gap-ds-2", children: [(0, jsx_runtime_1.jsxs)("div", { className: "min-w-0", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-ds-sm font-semibold text-ds-text", children: title }), description ? ((0, jsx_runtime_1.jsx)("div", { className: "mt-1 text-ds-xs leading-5 text-ds-text/90", children: description })) : null] }), meta ? ((0, jsx_runtime_1.jsx)("div", { className: "shrink-0 text-ds-2xs font-mono text-ds-muted", children: meta })) : null] }), children ? (0, jsx_runtime_1.jsx)("div", { className: "pt-ds-1", children: children }) : null] }), onDismiss ? ((0, jsx_runtime_1.jsx)("button", { type: "button", "aria-label": dismissLabel, className: (0, utils_1.cn)('inline-flex h-7 w-7 min-h-11 min-w-11 shrink-0 items-center justify-center rounded-ds-pill border border-transparent text-ds-muted transition-colors duration-ds-fast ease-ds-standard', 'hover:bg-ds-bg/70 hover:text-ds-text', 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg'), onClick: onDismiss, children: (0, jsx_runtime_1.jsx)(lucide_react_1.X, { size: 14, "aria-hidden": "true" }) })) : null] }) })] }) }));
}
