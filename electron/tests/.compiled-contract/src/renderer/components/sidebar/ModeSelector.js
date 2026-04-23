"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ModeSelector = ModeSelector;
const jsx_runtime_1 = require("react/jsx-runtime");
/**
 * Mode selector — auto / supervised / step-by-step radio buttons.
 */
const lucide_react_1 = require("lucide-react");
const primitives_1 = require("../../design-system/primitives");
const agentStore_1 = require("../../stores/agentStore");
const MODES = [
    { value: 'auto', label: 'Auto', desc: 'Agent runs freely' },
    { value: 'supervised', label: 'Supervised', desc: 'Confirm before actions' },
    { value: 'step-by-step', label: 'Step-by-Step', desc: 'Approve each step' },
];
function ModeSelector({ onChange }) {
    const { mode } = (0, agentStore_1.useAgentStore)();
    return ((0, jsx_runtime_1.jsx)("div", { className: "px-3 py-1.5", children: (0, jsx_runtime_1.jsxs)("fieldset", { className: "space-y-ds-3", "aria-label": "Execution mode", children: [(0, jsx_runtime_1.jsxs)("legend", { className: "mb-1 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-ds-muted", children: [(0, jsx_runtime_1.jsx)(lucide_react_1.Settings, { size: 12, "aria-hidden": "true" }), "Mode"] }), (0, jsx_runtime_1.jsx)(primitives_1.Card, { className: "space-y-ds-2 bg-ds-bg/40 px-ds-3 py-ds-3 shadow-none", children: MODES.map((m) => ((0, jsx_runtime_1.jsx)(primitives_1.Radio, { name: "sidebar-execution-mode", value: m.value, checked: mode === m.value, onChange: () => onChange(m.value), label: m.label, description: m.desc, className: "rounded-ds-lg px-ds-2 py-ds-2 hover:bg-ds-bg/60" }, m.value))) })] }) }));
}
