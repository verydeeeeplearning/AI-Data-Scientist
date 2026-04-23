"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ResultCardShell = ResultCardShell;
exports.ResultCardMetaRow = ResultCardMetaRow;
exports.ResultCardPill = ResultCardPill;
exports.ResultCardPillButton = ResultCardPillButton;
exports.ResultCardIconFrame = ResultCardIconFrame;
exports.ResultCardFooter = ResultCardFooter;
exports.ResultCardSectionTitle = ResultCardSectionTitle;
exports.ResultCardSectionPanel = ResultCardSectionPanel;
exports.ResultCardMetricPanel = ResultCardMetricPanel;
exports.ResultCardDetailBlock = ResultCardDetailBlock;
exports.ResultCardActionButton = ResultCardActionButton;
const jsx_runtime_1 = require("react/jsx-runtime");
const primitives_1 = require("../primitives");
const utils_1 = require("../primitives/utils");
function ResultCardShell({ className, children, ...rest }) {
    return ((0, jsx_runtime_1.jsx)("article", { className: (0, utils_1.cn)('rounded-ds-xl border border-ds-border bg-ds-surface/80 p-ds-4 text-ds-text shadow-ds-sm shadow-black/10', className), ...rest, children: children }));
}
function ResultCardMetaRow({ className, children, ...rest }) {
    return ((0, jsx_runtime_1.jsx)("div", { className: (0, utils_1.cn)('flex flex-wrap items-center gap-ds-2 text-ds-xs text-ds-muted', className), ...rest, children: children }));
}
function ResultCardPill({ compact = true, className, children, ...rest }) {
    return ((0, jsx_runtime_1.jsx)(primitives_1.Badge, { compact: compact, className: (0, utils_1.cn)('normal-case tracking-normal', className), ...rest, children: children }));
}
function ResultCardPillButton({ className, children, type = 'button', ...rest }) {
    return ((0, jsx_runtime_1.jsx)(primitives_1.Badge, { as: "button", type: type, compact: true, className: (0, utils_1.cn)('normal-case tracking-normal transition-colors duration-ds-fast ease-ds-standard', 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg', 'hover:border-ds-accent/40 hover:text-ds-accent disabled:cursor-not-allowed disabled:opacity-50', className), ...rest, children: children }));
}
function ResultCardIconFrame({ className, children, ...rest }) {
    return ((0, jsx_runtime_1.jsx)("div", { className: (0, utils_1.cn)('flex h-10 w-10 items-center justify-center rounded-ds-lg border px-ds-3 py-ds-2', className), ...rest, children: children }));
}
function ResultCardFooter({ className, children, ...rest }) {
    return ((0, jsx_runtime_1.jsx)("footer", { className: (0, utils_1.cn)('mt-ds-4 space-y-ds-3 border-t border-ds-border/60 pt-ds-3', className), ...rest, children: children }));
}
function ResultCardSectionTitle({ className, children, ...rest }) {
    return ((0, jsx_runtime_1.jsx)("h4", { className: (0, utils_1.cn)('text-ds-xs font-semibold uppercase tracking-widest text-ds-muted', className), ...rest, children: children }));
}
function ResultCardSectionPanel({ className, children, ...rest }) {
    return ((0, jsx_runtime_1.jsx)("section", { className: (0, utils_1.cn)('rounded-ds-lg border border-ds-border/70 bg-ds-bg/60 p-ds-3', className), ...rest, children: children }));
}
function ResultCardMetricPanel({ label, value, hint, className, }) {
    return ((0, jsx_runtime_1.jsxs)("section", { className: (0, utils_1.cn)('rounded-ds-lg border border-ds-accent/20 bg-ds-accent/5 p-ds-3', className), children: [(0, jsx_runtime_1.jsx)(ResultCardSectionTitle, { children: label }), (0, jsx_runtime_1.jsx)("div", { className: "mt-ds-2 text-ds-2xl font-semibold text-ds-text", children: value }), hint && (0, jsx_runtime_1.jsx)("div", { className: "mt-ds-1 text-ds-xs text-ds-muted", children: hint })] }));
}
function ResultCardDetailBlock({ label, value, className, }) {
    return ((0, jsx_runtime_1.jsxs)(ResultCardSectionPanel, { className: className, children: [(0, jsx_runtime_1.jsx)(ResultCardSectionTitle, { children: label }), (0, jsx_runtime_1.jsx)("div", { className: "mt-ds-2 text-ds-sm text-ds-text", children: value })] }));
}
const ACTION_TONE_CLASSES = {
    default: '',
    accent: 'border-ds-accent/40 bg-ds-accent/5 text-ds-accent hover:bg-ds-accent/10',
};
function ResultCardActionButton({ tone = 'default', className, leadingIcon, trailingIcon, children, ...rest }) {
    if (tone === 'danger') {
        return ((0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "danger", size: "sm", leadingIcon: leadingIcon, trailingIcon: trailingIcon, className: className, ...rest, children: children }));
    }
    return ((0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "secondary", size: "sm", leadingIcon: leadingIcon, trailingIcon: trailingIcon, className: (0, utils_1.cn)(ACTION_TONE_CLASSES[tone], className), ...rest, children: children }));
}
