"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ViewportStack = exports.WarningWithAction = exports.Info = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const lucide_react_1 = require("lucide-react");
const Button_1 = require("./Button");
const Toast_1 = require("./Toast");
const meta = {
    title: 'Design System/Primitives/Toast',
    component: Toast_1.Toast,
    tags: ['autodocs'],
    parameters: {
        layout: 'fullscreen',
    },
    args: {
        title: 'Runtime notification',
        description: 'The autonomous runtime completed a background review and queued the next operator action.',
        tone: 'info',
        leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.Bell, { size: 14 }),
    },
};
exports.default = meta;
exports.Info = {
    render: (args) => ((0, jsx_runtime_1.jsx)("div", { className: "min-h-[240px] p-ds-6", children: (0, jsx_runtime_1.jsx)(Toast_1.Toast, { ...args }) })),
};
exports.WarningWithAction = {
    args: {
        title: 'Sandbox violation',
        description: 'The agent attempted an unapproved filesystem write outside the workspace boundary.',
        tone: 'warning',
        meta: 'write_file',
        leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.ShieldAlert, { size: 14 }),
    },
    render: (args) => ((0, jsx_runtime_1.jsx)("div", { className: "min-h-[240px] p-ds-6", children: (0, jsx_runtime_1.jsx)(Toast_1.Toast, { ...args, children: (0, jsx_runtime_1.jsxs)("div", { className: "flex gap-ds-2", children: [(0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "secondary", size: "sm", children: "Review trace" }), (0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "primary", size: "sm", children: "Adjust policy" })] }) }) })),
};
exports.ViewportStack = {
    render: () => ((0, jsx_runtime_1.jsx)("div", { className: "min-h-[320px] p-ds-6", children: (0, jsx_runtime_1.jsxs)(Toast_1.ToastViewport, { placement: "bottom-right", children: [(0, jsx_runtime_1.jsx)(Toast_1.Toast, { title: "Experiment promoted", description: "The latest baseline beat the previous champion on holdout precision.", tone: "success", meta: "model_eval", leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.CheckCircle2, { size: 14 }) }), (0, jsx_runtime_1.jsx)(Toast_1.Toast, { title: "Delivery fallback enabled", description: "Telegram quiet hours are active, so low-urgency alerts are being buffered.", tone: "info", meta: "operator_runtime", leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.Bell, { size: 14 }) }), (0, jsx_runtime_1.jsx)(Toast_1.Toast, { title: "Repeated blocked state", description: "The same network host has been denied three times in the last hour.", tone: "danger", meta: "network_sandbox", leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.AlertTriangle, { size: 14 }) })] }) })),
};
