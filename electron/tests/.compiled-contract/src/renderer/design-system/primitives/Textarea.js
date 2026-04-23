"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Textarea = Textarea;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const Field_1 = require("./Field");
const utils_1 = require("./utils");
const RESIZE_CLASSES = {
    vertical: 'resize-y',
    none: 'resize-none',
};
function Textarea({ id, label, description, hint, errorMessage, resize = 'vertical', rows = 5, className, disabled = false, readOnly = false, required = false, 'aria-describedby': ariaDescribedBy, 'aria-invalid': ariaInvalid, ...rest }) {
    const generatedId = (0, react_1.useId)().replace(/:/g, '');
    const controlId = id ?? `ds-textarea-${generatedId}`;
    const descriptionId = description ? `${controlId}-description` : undefined;
    const hintId = hint ? `${controlId}-hint` : undefined;
    const errorId = errorMessage ? `${controlId}-error` : undefined;
    const invalid = (0, utils_1.isAriaInvalid)(ariaInvalid) || Boolean(errorMessage);
    return ((0, jsx_runtime_1.jsx)(Field_1.FieldFrame, { controlId: controlId, label: label, description: description, descriptionId: descriptionId, hint: hint, hintId: hintId, errorMessage: errorMessage, errorId: errorId, required: required, children: (0, jsx_runtime_1.jsx)("textarea", { id: controlId, rows: rows, "aria-describedby": (0, utils_1.joinIds)(descriptionId, errorId, hintId, ariaDescribedBy), "aria-invalid": invalid || undefined, disabled: disabled, readOnly: readOnly, required: required, className: (0, utils_1.cn)('min-h-32 w-full rounded-ds-md border px-ds-3 py-ds-3 text-ds-sm text-ds-text shadow-ds-sm transition-colors duration-ds-fast ease-ds-standard outline-none placeholder:text-ds-muted/70 focus-visible:outline-none', readOnly ? 'bg-ds-surface/80' : 'bg-ds-bg', invalid
                ? 'border-ds-error bg-ds-error/5 focus:border-ds-error focus-visible:ring-ds-error/30'
                : 'border-ds-border focus:border-ds-accent focus-visible:ring-ds-accent/70', 'focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg', disabled ? 'cursor-not-allowed opacity-60' : '', RESIZE_CLASSES[resize], className), ...rest }) }));
}
