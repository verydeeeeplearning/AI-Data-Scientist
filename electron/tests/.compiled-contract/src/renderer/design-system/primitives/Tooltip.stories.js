"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.PlacementGallery = exports.AccentTone = exports.Default = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const lucide_react_1 = require("lucide-react");
const Button_1 = require("./Button");
const Tooltip_1 = require("./Tooltip");
const meta = {
    title: 'Design System/Primitives/Tooltip',
    component: Tooltip_1.Tooltip,
    tags: ['autodocs'],
    parameters: {
        layout: 'centered',
    },
    args: {
        content: 'The latest runtime health check passed and operator delivery is active.',
        children: ((0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "secondary", leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.Info, { size: 14 }), children: "Runtime health" })),
    },
};
exports.default = meta;
exports.Default = {};
exports.AccentTone = {
    args: {
        tone: 'accent',
        content: 'This action will use the current policy template as the starting point.',
        children: ((0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "primary", leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.Info, { size: 14 }), children: "Recommended policy" })),
    },
};
exports.PlacementGallery = {
    render: () => ((0, jsx_runtime_1.jsxs)("div", { className: "grid grid-cols-2 gap-ds-6", children: [(0, jsx_runtime_1.jsx)(Tooltip_1.Tooltip, { placement: "top", content: "Top placement keeps the label close to the trigger.", children: (0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "secondary", children: "Top" }) }), (0, jsx_runtime_1.jsx)(Tooltip_1.Tooltip, { placement: "right", content: "Right placement is useful in dense table rows.", children: (0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "secondary", children: "Right" }) }), (0, jsx_runtime_1.jsx)(Tooltip_1.Tooltip, { placement: "bottom", tone: "accent", content: "Bottom placement works well beneath compact controls.", children: (0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "primary", children: "Bottom" }) }), (0, jsx_runtime_1.jsx)(Tooltip_1.Tooltip, { placement: "left", tone: "danger", content: "This override bypasses the default network sandbox allowlist.", children: (0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "danger", leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.AlertTriangle, { size: 14 }), children: "Left" }) })] })),
};
