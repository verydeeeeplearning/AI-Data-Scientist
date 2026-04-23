"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Badge = Badge;
const jsx_runtime_1 = require("react/jsx-runtime");
const utils_1 = require("./utils");
const TONE_CLASSES = {
    neutral: 'border-ds-border bg-ds-bg/60 text-ds-muted',
    accent: 'border-ds-accent/30 bg-ds-accent/10 text-ds-accent',
    success: 'border-ds-success/30 bg-ds-success/10 text-ds-success',
    warning: 'border-ds-warning/30 bg-ds-warning/10 text-ds-warning',
    danger: 'border-ds-error/30 bg-ds-error/10 text-ds-error',
    info: 'border-ds-info/30 bg-ds-info/10 text-ds-info',
};
function Badge({ as, tone = 'neutral', compact = false, leadingIcon, className, children, ...rest }) {
    const Component = as ?? 'span';
    return ((0, jsx_runtime_1.jsxs)(Component, { className: (0, utils_1.cn)('inline-flex min-w-0 items-center rounded-ds-pill border font-medium shadow-ds-sm transition-colors duration-ds-fast ease-ds-standard', compact ? 'gap-ds-1 px-ds-2 py-ds-1 text-ds-xs' : 'gap-ds-2 px-ds-3 py-ds-2 text-ds-xs', TONE_CLASSES[tone], className), ...rest, children: [leadingIcon, (0, jsx_runtime_1.jsx)("span", { className: "truncate", children: children })] }));
}
