"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Popover = Popover;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const focusManagement_1 = require("../../application/a11y/focusManagement");
const utils_1 = require("./utils");
const POSITION_CLASSES = {
    top: {
        start: 'bottom-full left-0 mb-ds-2',
        center: 'bottom-full left-1/2 mb-ds-2 -translate-x-1/2',
        end: 'bottom-full right-0 mb-ds-2',
    },
    right: {
        start: 'left-full top-0 ml-ds-2',
        center: 'left-full top-1/2 ml-ds-2 -translate-y-1/2',
        end: 'left-full bottom-0 ml-ds-2',
    },
    bottom: {
        start: 'left-0 top-full mt-ds-2',
        center: 'left-1/2 top-full mt-ds-2 -translate-x-1/2',
        end: 'right-0 top-full mt-ds-2',
    },
    left: {
        start: 'right-full top-0 mr-ds-2',
        center: 'right-full top-1/2 mr-ds-2 -translate-y-1/2',
        end: 'right-full bottom-0 mr-ds-2',
    },
};
const TONE_CLASSES = {
    default: 'border-ds-border bg-ds-surface-elevated/98',
    accent: 'border-ds-accent/30 bg-ds-surface-elevated/98',
    danger: 'border-ds-error/30 bg-ds-surface-elevated/98',
};
function useControllableOpenState(open, defaultOpen, onOpenChange) {
    const [uncontrolledOpen, setUncontrolledOpen] = (0, react_1.useState)(defaultOpen);
    const isControlled = open !== undefined;
    const resolvedOpen = isControlled ? open : uncontrolledOpen;
    const setOpen = (nextOpen) => {
        if (!isControlled) {
            setUncontrolledOpen(nextOpen);
        }
        onOpenChange?.(nextOpen);
    };
    return [resolvedOpen, setOpen];
}
function composeEventHandlers(original, next) {
    return (event) => {
        original?.(event);
        next?.(event);
    };
}
function Popover({ trigger, children, title, description, placement = 'bottom', align = 'start', tone = 'default', open, defaultOpen = false, onOpenChange, disabled = false, closeOnInteractOutside = true, closeOnEscape = true, contentClassName, className, 'aria-describedby': ariaDescribedBy, ...rest }) {
    const generatedId = (0, react_1.useId)().replace(/:/g, '');
    const panelId = `ds-popover-${generatedId}`;
    const titleId = title ? `${panelId}-title` : undefined;
    const descriptionId = description ? `${panelId}-description` : undefined;
    const [visible, setVisible] = useControllableOpenState(open, defaultOpen, onOpenChange);
    const wrapperRef = (0, react_1.useRef)(null);
    const panelRef = (0, react_1.useRef)(null);
    const focusTokenRef = (0, react_1.useRef)({ previous: null });
    const triggerElement = trigger;
    (0, react_1.useEffect)(() => {
        if (disabled && visible) {
            setVisible(false);
        }
    }, [disabled, visible, setVisible]);
    (0, react_1.useEffect)(() => {
        if (!visible) {
            return undefined;
        }
        focusTokenRef.current = (0, focusManagement_1.captureFocus)();
        const frameHandle = window.requestAnimationFrame(() => {
            const panel = panelRef.current;
            if (!panel) {
                return;
            }
            const [firstFocusable] = (0, focusManagement_1.findFocusableElements)(panel);
            (firstFocusable ?? panel).focus();
        });
        const handlePointerDown = (event) => {
            if (!closeOnInteractOutside) {
                return;
            }
            const wrapper = wrapperRef.current;
            if (!wrapper || wrapper.contains(event.target)) {
                return;
            }
            setVisible(false);
        };
        const handleFocusIn = (event) => {
            if (!closeOnInteractOutside) {
                return;
            }
            const wrapper = wrapperRef.current;
            if (!wrapper || wrapper.contains(event.target)) {
                return;
            }
            setVisible(false);
        };
        document.addEventListener('pointerdown', handlePointerDown);
        document.addEventListener('focusin', handleFocusIn);
        return () => {
            window.cancelAnimationFrame(frameHandle);
            document.removeEventListener('pointerdown', handlePointerDown);
            document.removeEventListener('focusin', handleFocusIn);
            (0, focusManagement_1.restoreFocus)(focusTokenRef.current);
            focusTokenRef.current = { previous: null };
        };
    }, [closeOnInteractOutside, setVisible, visible]);
    const clonedTrigger = (0, react_1.cloneElement)(triggerElement, {
        'aria-controls': visible ? panelId : triggerElement.props['aria-controls'],
        'aria-expanded': visible,
        'aria-haspopup': 'dialog',
        onClick: composeEventHandlers(triggerElement.props.onClick, () => {
            if (!disabled) {
                setVisible(!visible);
            }
        }),
        onKeyDown: composeEventHandlers(triggerElement.props.onKeyDown, (event) => {
            if (event.key === 'Escape' && closeOnEscape && visible) {
                event.preventDefault();
                setVisible(false);
            }
        }),
    });
    return ((0, jsx_runtime_1.jsxs)("div", { ref: wrapperRef, className: (0, utils_1.cn)('relative inline-flex', className), ...rest, children: [clonedTrigger, visible && !disabled ? ((0, jsx_runtime_1.jsxs)("div", { ref: panelRef, id: panelId, role: "dialog", "aria-modal": "false", "aria-labelledby": titleId, "aria-describedby": (0, utils_1.joinIds)(descriptionId, ariaDescribedBy), tabIndex: -1, className: (0, utils_1.cn)('absolute z-50 w-ds-popover rounded-ds-xl border p-ds-4 text-ds-text shadow-ds-lg', POSITION_CLASSES[placement][align], TONE_CLASSES[tone], contentClassName), onKeyDown: (event) => {
                    if (event.key === 'Escape' && closeOnEscape) {
                        event.preventDefault();
                        setVisible(false);
                    }
                }, children: [title || description ? ((0, jsx_runtime_1.jsxs)("div", { className: "min-w-0 space-y-ds-2", children: [title ? ((0, jsx_runtime_1.jsx)("div", { id: titleId, className: "text-ds-sm font-semibold text-ds-text", children: title })) : null, description ? ((0, jsx_runtime_1.jsx)("p", { id: descriptionId, className: "text-ds-xs leading-5 text-ds-muted", children: description })) : null] })) : null, (0, jsx_runtime_1.jsx)("div", { className: (0, utils_1.cn)(title || description ? 'mt-ds-3' : ''), children: children })] })) : null] }));
}
