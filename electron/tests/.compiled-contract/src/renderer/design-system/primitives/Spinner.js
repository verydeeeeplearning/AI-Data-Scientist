"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Spinner = Spinner;
const jsx_runtime_1 = require("react/jsx-runtime");
const lucide_react_1 = require("lucide-react");
const utils_1 = require("./utils");
const SIZE_MAP = {
    sm: 14,
    md: 18,
    lg: 22,
};
const TONE_CLASSES = {
    accent: 'text-ds-accent',
    muted: 'text-ds-muted',
    success: 'text-ds-success',
    warning: 'text-ds-warning',
    danger: 'text-ds-error',
};
function Spinner({ size = 'md', tone = 'accent', label, className, ...rest }) {
    return ((0, jsx_runtime_1.jsxs)("span", { className: (0, utils_1.cn)('inline-flex items-center gap-ds-2', className), role: label ? 'status' : undefined, "aria-live": label ? 'polite' : undefined, "aria-hidden": label ? undefined : true, ...rest, children: [(0, jsx_runtime_1.jsx)(lucide_react_1.Loader2, { size: SIZE_MAP[size], className: (0, utils_1.cn)('animate-spin', TONE_CLASSES[tone]), "aria-hidden": "true" }), label ? (0, jsx_runtime_1.jsx)("span", { className: "text-ds-sm text-ds-muted", children: label }) : null] }));
}
