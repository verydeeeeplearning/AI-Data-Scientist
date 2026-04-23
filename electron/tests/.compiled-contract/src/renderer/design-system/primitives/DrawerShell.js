"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DrawerShell = DrawerShell;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const lucide_react_1 = require("lucide-react");
const focusManagement_1 = require("../../application/a11y/focusManagement");
const reducedMotion_1 = require("../../application/a11y/reducedMotion");
const utils_1 = require("./utils");
const SIZE_CLASSES = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
};
const PLACEMENT_CLASSES = {
    left: 'justify-start',
    right: 'justify-end',
};
function DrawerShell({ open = true, title, description, footer, size = 'md', placement = 'right', dismissLabel = 'Close panel', onDismiss, bodyClassName, panelClassName, overlayClassName, className, children, 'aria-describedby': ariaDescribedBy, ...rest }) {
    const generatedId = (0, react_1.useId)().replace(/:/g, '');
    const titleId = `ds-drawer-${generatedId}-title`;
    const descriptionId = description ? `ds-drawer-${generatedId}-description` : undefined;
    const panelRef = (0, react_1.useRef)(null);
    const trapRef = (0, react_1.useRef)(null);
    const focusTokenRef = (0, react_1.useRef)({ previous: null });
    const dismissButtonRef = (0, react_1.useRef)(null);
    const motionClass = (0, reducedMotion_1.prefersReducedMotion)()
        ? ''
        : 'transition-transform duration-ds-normal ease-ds-standard';
    (0, react_1.useEffect)(() => {
        const panel = panelRef.current;
        if (!open || !panel) {
            trapRef.current?.deactivate();
            trapRef.current = null;
            return undefined;
        }
        focusTokenRef.current = (0, focusManagement_1.captureFocus)();
        const trap = (0, focusManagement_1.createFocusTrap)(panel);
        trapRef.current = trap;
        trap.activate();
        const handle = window.requestAnimationFrame(() => {
            dismissButtonRef.current?.focus();
        });
        return () => {
            window.cancelAnimationFrame(handle);
            trap.deactivate();
            if (trapRef.current === trap) {
                trapRef.current = null;
            }
            (0, focusManagement_1.restoreFocus)(focusTokenRef.current);
            focusTokenRef.current = { previous: null };
        };
    }, [open]);
    if (!open) {
        return null;
    }
    const handleKeyDown = (event) => {
        if (event.key === 'Escape') {
            event.preventDefault();
            onDismiss?.();
            return;
        }
        if (event.key === 'Tab') {
            event.preventDefault();
            trapRef.current?.cycle(event.shiftKey ? 'backward' : 'forward');
        }
    };
    return ((0, jsx_runtime_1.jsx)("div", { className: (0, utils_1.cn)('fixed inset-0 z-40 flex bg-black/40 p-ds-3 sm:p-ds-4', PLACEMENT_CLASSES[placement], overlayClassName), children: (0, jsx_runtime_1.jsxs)("div", { ref: panelRef, role: "dialog", "aria-modal": "true", "aria-labelledby": titleId, "aria-describedby": (0, utils_1.joinIds)(descriptionId, ariaDescribedBy), className: (0, utils_1.cn)('flex h-full w-full flex-col rounded-ds-xl border border-ds-border bg-ds-surface-elevated/98 text-ds-text shadow-ds-lg', SIZE_CLASSES[size], motionClass, panelClassName, className), onKeyDown: handleKeyDown, ...rest, children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-start justify-between gap-ds-3 border-b border-ds-border/80 px-ds-4 py-ds-4", children: [(0, jsx_runtime_1.jsxs)("div", { className: "min-w-0 space-y-ds-2", children: [(0, jsx_runtime_1.jsx)("div", { id: titleId, className: "text-ds-lg font-semibold text-ds-text", children: title }), description ? ((0, jsx_runtime_1.jsx)("p", { id: descriptionId, className: "text-ds-sm leading-6 text-ds-muted", children: description })) : null] }), onDismiss ? ((0, jsx_runtime_1.jsx)("button", { ref: dismissButtonRef, type: "button", "aria-label": dismissLabel, className: (0, utils_1.cn)('inline-flex min-h-11 items-center justify-center rounded-ds-pill border border-transparent px-ds-3 text-ds-xs font-medium text-ds-muted shadow-ds-sm transition-all duration-ds-normal ease-ds-standard', 'hover:bg-ds-bg hover:text-ds-text', 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg'), onClick: onDismiss, children: (0, jsx_runtime_1.jsx)(lucide_react_1.X, { size: 16, "aria-hidden": "true" }) })) : null] }), (0, jsx_runtime_1.jsx)("div", { className: (0, utils_1.cn)('min-h-0 flex-1 overflow-y-auto px-ds-4 py-ds-4', bodyClassName), children: children }), footer ? ((0, jsx_runtime_1.jsx)("div", { className: "flex items-center justify-end gap-ds-2 border-t border-ds-border/80 px-ds-4 py-ds-4", children: footer })) : null] }) }));
}
