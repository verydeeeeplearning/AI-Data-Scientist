"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Accordion = Accordion;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const lucide_react_1 = require("lucide-react");
const utils_1 = require("./utils");
function Accordion({ value, onValueChange, items, allowCollapse = true, itemClassName, triggerClassName, contentClassName, className, ...rest }) {
    const generatedId = (0, react_1.useId)().replace(/:/g, '');
    return ((0, jsx_runtime_1.jsx)("div", { className: (0, utils_1.cn)('space-y-ds-2', className), ...rest, children: items.map((item) => {
            const open = item.value === value;
            const triggerId = `ds-accordion-${generatedId}-trigger-${item.value}`;
            const panelId = `ds-accordion-${generatedId}-panel-${item.value}`;
            return ((0, jsx_runtime_1.jsxs)("div", { className: (0, utils_1.cn)('rounded-ds-xl border border-ds-border bg-ds-surface/92 shadow-ds-sm', itemClassName), children: [(0, jsx_runtime_1.jsxs)("button", { type: "button", id: triggerId, "aria-expanded": open, "aria-controls": panelId, disabled: item.disabled, onClick: () => {
                            if (item.disabled) {
                                return;
                            }
                            onValueChange(open && allowCollapse ? null : item.value);
                        }, className: (0, utils_1.cn)('flex w-full items-center justify-between gap-ds-3 rounded-ds-xl px-ds-4 py-ds-3 text-left text-ds-sm font-medium text-ds-text transition-colors duration-ds-fast ease-ds-standard', 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg', open ? 'bg-ds-bg' : 'hover:bg-ds-bg', item.disabled ? 'cursor-not-allowed opacity-50 hover:bg-transparent' : '', triggerClassName), children: [(0, jsx_runtime_1.jsx)("span", { className: "min-w-0", children: item.title }), (0, jsx_runtime_1.jsx)(lucide_react_1.ChevronDown, { size: 16, "aria-hidden": "true", className: (0, utils_1.cn)('shrink-0 text-ds-muted transition-transform duration-ds-fast ease-ds-standard', open ? 'rotate-180 text-ds-text' : '') })] }), open ? ((0, jsx_runtime_1.jsx)("div", { id: panelId, role: "region", "aria-labelledby": triggerId, className: (0, utils_1.cn)('border-t border-ds-border px-ds-4 py-ds-4', contentClassName), children: item.content })) : null] }, item.value));
        }) }));
}
