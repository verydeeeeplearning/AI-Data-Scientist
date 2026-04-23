"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Select = Select;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const utils_1 = require("./utils");
function Select({ id, label, description, options, className, ...rest }) {
    const generatedId = (0, react_1.useId)().replace(/:/g, '');
    const controlId = id ?? `ds-select-${generatedId}`;
    const descriptionId = description ? `${controlId}-description` : undefined;
    return ((0, jsx_runtime_1.jsxs)("div", { className: "space-y-ds-2", children: [label ? ((0, jsx_runtime_1.jsx)("label", { htmlFor: controlId, className: "block text-ds-xs font-medium text-ds-text", children: label })) : null, description ? ((0, jsx_runtime_1.jsx)("p", { id: descriptionId, className: "text-ds-xs leading-5 text-ds-muted", children: description })) : null, (0, jsx_runtime_1.jsx)("select", { id: controlId, "aria-describedby": descriptionId, className: (0, utils_1.cn)('min-h-11 w-full rounded-ds-md border border-ds-border bg-ds-bg px-ds-3 py-ds-2 text-ds-sm text-ds-text shadow-ds-sm transition-colors', 'focus:border-ds-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg', className), ...rest, children: options.map((option) => ((0, jsx_runtime_1.jsx)("option", { value: option.value, children: option.label }, option.value))) })] }));
}
