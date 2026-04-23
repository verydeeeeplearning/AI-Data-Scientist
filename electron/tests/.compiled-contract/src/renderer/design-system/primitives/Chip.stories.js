"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Disabled = exports.CompactDanger = exports.ApprovalFilters = exports.SelectedAccent = exports.Neutral = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const lucide_react_1 = require("lucide-react");
const Chip_1 = require("./Chip");
const meta = {
    title: 'Design System/Primitives/Chip',
    component: Chip_1.Chip,
    tags: ['autodocs'],
    args: {
        children: 'Primary reviewer',
    },
};
exports.default = meta;
exports.Neutral = {};
exports.SelectedAccent = {
    args: {
        tone: 'accent',
        selected: true,
        leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.Sparkles, { size: 14 }),
        children: 'Recommended policy',
    },
};
exports.ApprovalFilters = {
    render: () => ((0, jsx_runtime_1.jsxs)("div", { className: "flex flex-wrap gap-ds-2", children: [(0, jsx_runtime_1.jsx)(Chip_1.Chip, { leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.Tag, { size: 14 }), children: "All requests" }), (0, jsx_runtime_1.jsx)(Chip_1.Chip, { tone: "accent", selected: true, leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.ShieldCheck, { size: 14 }), children: "Needs review" }), (0, jsx_runtime_1.jsx)(Chip_1.Chip, { tone: "warning", selected: true, leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.CircleAlert, { size: 14 }), children: "Escalated" })] })),
};
exports.CompactDanger = {
    args: {
        tone: 'danger',
        size: 'sm',
        selected: true,
        children: 'Override enabled',
    },
};
exports.Disabled = {
    args: {
        tone: 'neutral',
        children: 'Digest locked',
        disabled: true,
    },
};
