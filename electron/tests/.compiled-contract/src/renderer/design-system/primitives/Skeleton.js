"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Skeleton = Skeleton;
const jsx_runtime_1 = require("react/jsx-runtime");
const utils_1 = require("./utils");
const SHAPE_CLASSES = {
    line: 'h-4 w-full rounded-ds-pill',
    block: 'h-24 w-full rounded-ds-lg',
    avatar: 'h-12 w-12 rounded-full',
    pill: 'h-8 w-24 rounded-ds-pill',
};
const TONE_CLASSES = {
    default: 'bg-ds-border/70',
    muted: 'bg-ds-muted/20',
};
function Skeleton({ shape = 'line', tone = 'default', animated = true, className, ...rest }) {
    return ((0, jsx_runtime_1.jsx)("div", { className: (0, utils_1.cn)('shrink-0', animated ? 'animate-pulse' : '', SHAPE_CLASSES[shape], TONE_CLASSES[tone], className), "aria-hidden": "true", ...rest }));
}
