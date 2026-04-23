"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Card = Card;
const jsx_runtime_1 = require("react/jsx-runtime");
const utils_1 = require("./utils");
const TONE_CLASSES = {
    default: 'border-ds-border bg-ds-surface/92',
    elevated: 'border-ds-border bg-ds-surface-elevated/96 shadow-ds-md',
    accent: 'border-ds-accent/30 bg-ds-accent/5',
    danger: 'border-ds-error/30 bg-ds-error/10',
};
function Card({ tone = 'default', className, children, ...rest }) {
    return ((0, jsx_runtime_1.jsx)("div", { className: (0, utils_1.cn)('rounded-ds-xl border p-ds-4 text-ds-text shadow-ds-sm', TONE_CLASSES[tone], className), ...rest, children: children }));
}
