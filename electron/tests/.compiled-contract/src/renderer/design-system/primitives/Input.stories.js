"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SpaciousDensity = exports.ComfortableDensity = exports.CompactDensity = exports.Disabled = exports.ErrorState = exports.WithLeadingIcon = exports.Default = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const lucide_react_1 = require("lucide-react");
const applyDensityScale_1 = require("../../application/layout/applyDensityScale");
const Input_1 = require("./Input");
const meta = {
    title: 'Design System/Primitives/Input',
    component: Input_1.Input,
    tags: ['autodocs'],
    args: {
        id: 'storybook-input',
        label: 'Workspace name',
        description: 'Use a concise label that operators can recognize in Telegram and desktop views.',
        placeholder: 'North America retention refresh',
    },
};
exports.default = meta;
exports.Default = {};
exports.WithLeadingIcon = {
    args: {
        label: 'Search runs',
        description: 'Filter the latest completed analyses by keyword.',
        placeholder: 'Find a regression audit',
        leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.Search, { size: 14 }),
    },
};
exports.ErrorState = {
    args: {
        label: 'Webhook URL',
        description: 'Provide an HTTPS endpoint for operator callbacks.',
        value: 'http://localhost:8000/events',
        trailingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.CircleAlert, { size: 14 }),
        errorMessage: 'Webhook URLs must start with https://.',
        readOnly: true,
    },
};
exports.Disabled = {
    args: {
        label: 'Run identifier',
        value: 'run_2026_04_20_114500',
        hint: 'Generated automatically after the backend handshake succeeds.',
        disabled: true,
    },
};
function DensityShowcase({ mode, args }) {
    return ((0, jsx_runtime_1.jsxs)("div", { "data-density": mode, style: (0, applyDensityScale_1.applyDensityScale)(mode), className: "flex flex-col gap-ds-3 bg-ds-bg p-ds-4", children: [(0, jsx_runtime_1.jsx)(Input_1.Input, { ...args, id: `density-${mode}-input-1`, label: "Workspace name", placeholder: "North America retention refresh" }), (0, jsx_runtime_1.jsx)(Input_1.Input, { ...args, id: `density-${mode}-input-2`, label: "Search runs", placeholder: "Find a regression audit", leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.Search, { size: 14 }) })] }));
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
