"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DialogShell = DialogShell;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const lucide_react_1 = require("lucide-react");
const Button_1 = require("./Button");
const utils_1 = require("./utils");
const SIZE_CLASSES = {
    sm: 'max-w-lg',
    md: 'max-w-2xl',
    lg: 'max-w-4xl',
};
const TONE_CLASSES = {
    default: 'border-ds-border bg-ds-surface-elevated/96',
    danger: 'border-ds-error/40 bg-ds-surface-elevated/96',
};
function DialogShell({ open = true, title, description, footer, size = 'md', tone = 'default', dismissLabel = 'Close dialog', onDismiss, className, children, 'aria-describedby': ariaDescribedBy, ...rest }) {
    const generatedId = (0, react_1.useId)().replace(/:/g, '');
    const titleId = `ds-dialog-${generatedId}-title`;
    const descriptionId = description ? `ds-dialog-${generatedId}-description` : undefined;
    const borderClass = tone === 'danger' ? 'border-ds-error/20' : 'border-ds-border/80';
    if (!open) {
        return null;
    }
    return ((0, jsx_runtime_1.jsx)("div", { className: "fixed inset-0 z-50 flex items-center justify-center bg-ds-bg/75 p-ds-4", children: (0, jsx_runtime_1.jsxs)("div", { role: "dialog", "aria-modal": "true", "aria-labelledby": titleId, "aria-describedby": (0, utils_1.joinIds)(descriptionId, ariaDescribedBy), className: (0, utils_1.cn)('w-full rounded-ds-xl border text-ds-text shadow-ds-lg', SIZE_CLASSES[size], TONE_CLASSES[tone], className), ...rest, children: [(0, jsx_runtime_1.jsxs)("div", { className: (0, utils_1.cn)('flex items-start justify-between gap-ds-3 border-b px-ds-4 py-ds-4', borderClass), children: [(0, jsx_runtime_1.jsxs)("div", { className: "min-w-0 space-y-ds-2", children: [(0, jsx_runtime_1.jsx)("div", { id: titleId, className: "text-ds-lg font-semibold text-ds-text", children: title }), description ? ((0, jsx_runtime_1.jsx)("p", { id: descriptionId, className: "text-ds-sm leading-6 text-ds-muted", children: description })) : null] }), onDismiss ? ((0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "ghost", size: "sm", "aria-label": dismissLabel, className: "shrink-0", onClick: onDismiss, children: (0, jsx_runtime_1.jsx)(lucide_react_1.X, { size: 16, "aria-hidden": "true" }) })) : null] }), (0, jsx_runtime_1.jsx)("div", { className: "px-ds-4 py-ds-4", children: children }), footer ? ((0, jsx_runtime_1.jsx)("div", { className: (0, utils_1.cn)('flex items-center justify-end gap-ds-2 border-t px-ds-4 py-ds-4', borderClass), children: footer })) : null] }) }));
}
