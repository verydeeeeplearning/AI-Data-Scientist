"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SpaciousDensity = exports.ComfortableDensity = exports.CompactDensity = exports.WithIcon = exports.Loading = exports.Danger = exports.Secondary = exports.Primary = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const lucide_react_1 = require("lucide-react");
const applyDensityScale_1 = require("../../application/layout/applyDensityScale");
const Button_1 = require("./Button");
const meta = {
    title: 'Design System/Primitives/Button',
    component: Button_1.Button,
    tags: ['autodocs'],
    args: {
        children: 'Run analysis',
    },
};
exports.default = meta;
exports.Primary = {};
exports.Secondary = {
    args: {
        variant: 'secondary',
    },
};
exports.Danger = {
    args: {
        variant: 'danger',
        children: 'Delete draft',
    },
};
exports.Loading = {
    args: {
        loading: true,
    },
};
exports.WithIcon = {
    args: {
        trailingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.ArrowRight, { size: 14 }),
    },
};
function DensityShowcase({ mode, args }) {
    return ((0, jsx_runtime_1.jsxs)("div", { "data-density": mode, style: (0, applyDensityScale_1.applyDensityScale)(mode), className: "flex flex-wrap items-center gap-ds-3 bg-ds-bg p-ds-4", children: [(0, jsx_runtime_1.jsx)(Button_1.Button, { ...args, variant: "primary", children: "Run analysis" }), (0, jsx_runtime_1.jsx)(Button_1.Button, { ...args, variant: "secondary", children: "Cancel" }), (0, jsx_runtime_1.jsx)(Button_1.Button, { ...args, variant: "ghost", children: "More" }), (0, jsx_runtime_1.jsx)(Button_1.Button, { ...args, variant: "danger", children: "Delete" })] }));
}
exports.CompactDensity = {
    render: (args) => (0, jsx_runtime_1.jsx)(DensityShowcase, { mode: "compact", args: args }),
};
exports.ComfortableDensity = {
    render: (args) => (0, jsx_runtime_1.jsx)(DensityShowcase, { mode: "comfortable", args: args }),
};
exports.SpaciousDensity = {
    render: (args) => (0, jsx_runtime_1.jsx)(DensityShowcase, { mode: "spacious", args: args }),
};
