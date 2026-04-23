"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Radio = Radio;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const utils_1 = require("./utils");
function Radio({ id, label, description, hint, errorMessage, className, disabled = false, required = false, 'aria-describedby': ariaDescribedBy, 'aria-invalid': ariaInvalid, ...rest }) {
    const generatedId = (0, react_1.useId)().replace(/:/g, '');
    const controlId = id ?? `ds-radio-${generatedId}`;
    const descriptionId = description ? `${controlId}-description` : undefined;
    const hintId = hint ? `${controlId}-hint` : undefined;
    const errorId = errorMessage ? `${controlId}-error` : undefined;
    const invalid = (0, utils_1.isAriaInvalid)(ariaInvalid) || Boolean(errorMessage);
    return ((0, jsx_runtime_1.jsxs)("div", { className: "space-y-ds-2", children: [(0, jsx_runtime_1.jsxs)("label", { htmlFor: controlId, className: (0, utils_1.cn)('flex min-h-11 items-start gap-ds-3 rounded-ds-md transition-colors duration-ds-fast ease-ds-standard', disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer', className), children: [(0, jsx_runtime_1.jsx)("input", { id: controlId, type: "radio", "aria-describedby": (0, utils_1.joinIds)(descriptionId, errorId, hintId, ariaDescribedBy), "aria-invalid": invalid || undefined, disabled: disabled, required: required, className: "peer sr-only", ...rest }), (0, jsx_runtime_1.jsx)("span", { className: (0, utils_1.cn)('mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-ds-pill border bg-ds-bg text-transparent shadow-ds-sm transition-all duration-ds-fast ease-ds-standard', 'peer-focus-visible:outline-none peer-focus-visible:ring-2 peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-ds-bg', 'peer-disabled:bg-ds-surface', invalid
                            ? 'border-ds-error peer-checked:border-ds-error peer-checked:bg-ds-error/10 peer-checked:text-ds-error peer-focus-visible:ring-ds-error/30'
                            : 'border-ds-border peer-checked:border-ds-accent peer-checked:bg-ds-accent/10 peer-checked:text-ds-accent peer-focus-visible:ring-ds-accent/70'), "aria-hidden": "true", children: (0, jsx_runtime_1.jsx)("span", { className: "h-2 w-2 rounded-ds-pill bg-current" }) }), (0, jsx_runtime_1.jsxs)("span", { className: "min-w-0 space-y-ds-1 pt-0.5", children: [label ? ((0, jsx_runtime_1.jsxs)("span", { className: "block text-ds-sm font-medium text-ds-text", children: [label, required ? ((0, jsx_runtime_1.jsx)("span", { className: "ml-ds-1 text-ds-error", "aria-hidden": "true", children: "*" })) : null] })) : null, description ? ((0, jsx_runtime_1.jsx)("span", { id: descriptionId, className: "block text-ds-xs leading-5 text-ds-muted", children: description })) : null] })] }), errorMessage ? ((0, jsx_runtime_1.jsx)("p", { id: errorId, className: "text-ds-xs leading-5 text-ds-error", children: errorMessage })) : null, hint ? ((0, jsx_runtime_1.jsx)("p", { id: hintId, className: (0, utils_1.cn)('text-ds-xs leading-5', errorMessage ? 'text-ds-muted/80' : 'text-ds-muted'), children: hint })) : null] }));
}
