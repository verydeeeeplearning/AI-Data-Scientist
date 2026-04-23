"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CardComposition = exports.Avatar = exports.Line = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const Card_1 = require("./Card");
const Skeleton_1 = require("./Skeleton");
const meta = {
    title: 'Design System/Primitives/Skeleton',
    component: Skeleton_1.Skeleton,
    tags: ['autodocs'],
    args: {
        shape: 'line',
    },
};
exports.default = meta;
exports.Line = {};
exports.Avatar = {
    args: {
        shape: 'avatar',
    },
};
exports.CardComposition = {
    render: () => ((0, jsx_runtime_1.jsxs)(Card_1.Card, { className: "max-w-xl space-y-ds-3", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-center gap-ds-3", children: [(0, jsx_runtime_1.jsx)(Skeleton_1.Skeleton, { shape: "avatar" }), (0, jsx_runtime_1.jsxs)("div", { className: "flex-1 space-y-ds-2", children: [(0, jsx_runtime_1.jsx)(Skeleton_1.Skeleton, { className: "max-w-sm" }), (0, jsx_runtime_1.jsx)(Skeleton_1.Skeleton, { className: "max-w-md", tone: "muted" })] })] }), (0, jsx_runtime_1.jsx)(Skeleton_1.Skeleton, { shape: "block" }), (0, jsx_runtime_1.jsxs)("div", { className: "flex gap-ds-2", children: [(0, jsx_runtime_1.jsx)(Skeleton_1.Skeleton, { shape: "pill" }), (0, jsx_runtime_1.jsx)(Skeleton_1.Skeleton, { shape: "pill", tone: "muted" })] })] })),
};
