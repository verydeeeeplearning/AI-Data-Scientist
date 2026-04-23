"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.FieldFrame = FieldFrame;
const jsx_runtime_1 = require("react/jsx-runtime");
const utils_1 = require("./utils");
function FieldFrame({ controlId, label, description, descriptionId, hint, hintId, errorMessage, errorId, required = false, children, }) {
    return ((0, jsx_runtime_1.jsxs)("div", { className: "space-y-ds-2", children: [label ? ((0, jsx_runtime_1.jsxs)("label", { htmlFor: controlId, className: "flex items-center gap-ds-1 text-ds-xs font-medium text-ds-text", children: [(0, jsx_runtime_1.jsx)("span", { children: label }), required ? ((0, jsx_runtime_1.jsx)("span", { className: "text-ds-error", "aria-hidden": "true", children: "*" })) : null] })) : null, description ? ((0, jsx_runtime_1.jsx)("p", { id: descriptionId, className: "text-ds-xs leading-5 text-ds-muted", children: description })) : null, children, errorMessage ? ((0, jsx_runtime_1.jsx)("p", { id: errorId, className: "text-ds-xs leading-5 text-ds-error", children: errorMessage })) : null, hint ? ((0, jsx_runtime_1.jsx)("p", { id: hintId, className: (0, utils_1.cn)('text-ds-xs leading-5', errorMessage ? 'text-ds-muted/80' : 'text-ds-muted'), children: hint })) : null] }));
}
