"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Chip = Chip;
const jsx_runtime_1 = require("react/jsx-runtime");
const utils_1 = require("./utils");
const TONE_CLASSES = {
    neutral: {
        base: 'border-ds-border bg-ds-bg text-ds-muted hover:border-ds-accent/40 hover:bg-ds-surface hover:text-ds-text',
        selected: 'border-ds-accent/40 bg-ds-accent/10 text-ds-accent',
    },
    accent: {
        base: 'border-ds-accent/20 bg-ds-accent/5 text-ds-accent hover:border-ds-accent/40 hover:bg-ds-accent/10',
        selected: 'border-transparent bg-ds-accent text-ds-accent-contrast',
    },
    success: {
        base: 'border-ds-success/20 bg-ds-success/5 text-ds-success hover:bg-ds-success/10',
        selected: 'border-ds-success/30 bg-ds-success/15 text-ds-success',
    },
    warning: {
        base: 'border-ds-warning/20 bg-ds-warning/5 text-ds-warning hover:bg-ds-warning/10',
        selected: 'border-ds-warning/30 bg-ds-warning/15 text-ds-warning',
    },
    danger: {
        base: 'border-ds-error/20 bg-ds-error/5 text-ds-error hover:bg-ds-error/10',
        selected: 'border-ds-error/30 bg-ds-error/15 text-ds-error',
    },
};
const SIZE_CLASSES = {
    sm: 'min-h-9 gap-ds-1 px-ds-3 text-ds-xs',
    md: 'min-h-10 gap-ds-2 px-ds-4 text-ds-sm',
};
function Chip({ tone = 'neutral', size = 'md', selected = false, leadingIcon, trailingIcon, className, children, disabled, type = 'button', 'aria-pressed': ariaPressed, ...rest }) {
    return ((0, jsx_runtime_1.jsxs)("button", { type: type, "aria-pressed": ariaPressed ?? selected, className: (0, utils_1.cn)('inline-flex items-center justify-center rounded-ds-pill border font-medium shadow-ds-sm transition-all duration-ds-fast ease-ds-standard', 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg', 'disabled:cursor-not-allowed disabled:opacity-50', SIZE_CLASSES[size], TONE_CLASSES[tone].base, selected ? TONE_CLASSES[tone].selected : '', className), disabled: disabled, ...rest, children: [leadingIcon, (0, jsx_runtime_1.jsx)("span", { className: "truncate", children: children }), trailingIcon] }));
}
