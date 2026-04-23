"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Input = Input;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const Field_1 = require("./Field");
const utils_1 = require("./utils");
function Input({ id, type = 'text', label, description, hint, errorMessage, leadingIcon, trailingIcon, containerClassName, className, disabled = false, readOnly = false, required = false, 'aria-describedby': ariaDescribedBy, 'aria-invalid': ariaInvalid, ...rest }) {
    const generatedId = (0, react_1.useId)().replace(/:/g, '');
    const controlId = id ?? `ds-input-${generatedId}`;
    const descriptionId = description ? `${controlId}-description` : undefined;
    const hintId = hint ? `${controlId}-hint` : undefined;
    const errorId = errorMessage ? `${controlId}-error` : undefined;
    const invalid = (0, utils_1.isAriaInvalid)(ariaInvalid) || Boolean(errorMessage);
    return ((0, jsx_runtime_1.jsx)(Field_1.FieldFrame, { controlId: controlId, label: label, description: description, descriptionId: descriptionId, hint: hint, hintId: hintId, errorMessage: errorMessage, errorId: errorId, required: required, children: (0, jsx_runtime_1.jsxs)("div", { className: (0, utils_1.cn)('flex min-h-11 w-full items-center gap-ds-2 rounded-ds-md border px-ds-3 py-ds-2 shadow-ds-sm transition-colors duration-ds-fast ease-ds-standard', readOnly ? 'bg-ds-surface/80' : 'bg-ds-bg', invalid
                ? 'border-ds-error bg-ds-error/5 focus-within:border-ds-error focus-within:ring-ds-error/30'
                : 'border-ds-border focus-within:border-ds-accent focus-within:ring-ds-accent/70', 'focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-offset-ds-bg', disabled ? 'cursor-not-allowed opacity-60' : '', containerClassName), children: [leadingIcon ? ((0, jsx_runtime_1.jsx)("span", { className: "shrink-0 text-ds-muted", "aria-hidden": "true", children: leadingIcon })) : null, (0, jsx_runtime_1.jsx)("input", { id: controlId, type: type, "aria-describedby": (0, utils_1.joinIds)(descriptionId, errorId, hintId, ariaDescribedBy), "aria-invalid": invalid || undefined, disabled: disabled, readOnly: readOnly, required: required, className: (0, utils_1.cn)('min-w-0 flex-1 border-0 bg-transparent text-ds-sm text-ds-text outline-none placeholder:text-ds-muted/70 focus-visible:outline-none', className), ...rest }), trailingIcon ? ((0, jsx_runtime_1.jsx)("span", { className: (0, utils_1.cn)('shrink-0', invalid ? 'text-ds-error' : 'text-ds-muted'), "aria-hidden": "true", children: trailingIcon })) : null] }) }));
}
