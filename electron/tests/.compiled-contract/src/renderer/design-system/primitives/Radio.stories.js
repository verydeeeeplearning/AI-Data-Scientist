"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ErrorState = exports.ApprovalGroup = exports.Selected = exports.Default = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const Radio_1 = require("./Radio");
const meta = {
    title: 'Design System/Primitives/Radio',
    component: Radio_1.Radio,
    tags: ['autodocs'],
    args: {
        id: 'storybook-radio',
        name: 'storybook-approval-decision',
        label: 'Escalate immediately',
        description: 'Notify the operator as soon as the blocked state crosses the configured threshold.',
        hint: 'Use a shared name across radios to build a full decision group.',
    },
};
exports.default = meta;
exports.Default = {};
exports.Selected = {
    args: {
        id: 'storybook-radio-selected',
        label: 'Queue for digest',
        description: 'Hold the notification until the next operator digest window.',
        defaultChecked: true,
    },
};
exports.ApprovalGroup = {
    render: () => ((0, jsx_runtime_1.jsxs)("div", { className: "space-y-ds-3", children: [(0, jsx_runtime_1.jsx)(Radio_1.Radio, { id: "storybook-radio-group-now", name: "storybook-approval-group", label: "Approve now", description: "Release the action token and continue without waiting for the next digest.", defaultChecked: true }), (0, jsx_runtime_1.jsx)(Radio_1.Radio, { id: "storybook-radio-group-hold", name: "storybook-approval-group", label: "Hold for review", description: "Pause execution and keep the task parked in the approval inbox." }), (0, jsx_runtime_1.jsx)(Radio_1.Radio, { id: "storybook-radio-group-reject", name: "storybook-approval-group", label: "Reject request", description: "Return the run to the operator with a blocked outcome." })] })),
};
exports.ErrorState = {
    args: {
        id: 'storybook-radio-error',
        label: 'Bypass secondary review',
        description: 'Only use this for emergency maintenance windows.',
        errorMessage: 'A bypass decision must be paired with an incident reference.',
    },
};
