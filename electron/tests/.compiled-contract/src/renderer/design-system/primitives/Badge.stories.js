"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Danger = exports.Warning = exports.Success = exports.Accent = exports.Neutral = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const lucide_react_1 = require("lucide-react");
const Badge_1 = require("./Badge");
const meta = {
    title: 'Design System/Primitives/Badge',
    component: Badge_1.Badge,
    tags: ['autodocs'],
    args: {
        children: 'Trust ready',
    },
};
exports.default = meta;
exports.Neutral = {};
exports.Accent = {
    args: {
        tone: 'accent',
        leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.Sparkles, { size: 12 }),
        children: 'Recommended',
    },
};
exports.Success = {
    args: {
        tone: 'success',
        leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.CheckCircle2, { size: 12 }),
        children: 'Verifier passed',
    },
};
exports.Warning = {
    args: {
        tone: 'warning',
        leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.CircleAlert, { size: 12 }),
        children: 'Approval pending',
    },
};
exports.Danger = {
    args: {
        tone: 'danger',
        leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.ShieldAlert, { size: 12 }),
        children: 'High risk',
    },
};
