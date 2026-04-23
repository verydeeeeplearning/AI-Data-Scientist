"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Tooltip = Tooltip;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const utils_1 = require("./utils");
const PLACEMENT_CLASSES = {
    top: 'bottom-full left-1/2 mb-ds-2 -translate-x-1/2',
    right: 'left-full top-1/2 ml-ds-2 -translate-y-1/2',
    bottom: 'left-1/2 top-full mt-ds-2 -translate-x-1/2',
    left: 'right-full top-1/2 mr-ds-2 -translate-y-1/2',
};
const TONE_CLASSES = {
    default: 'border-ds-border bg-ds-surface-elevated/96 text-ds-text',
    accent: 'border-ds-accent/30 bg-ds-accent/10 text-ds-text',
    danger: 'border-ds-error/30 bg-ds-error/10 text-ds-text',
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
function Tooltip({ children, content, placement = 'top', tone = 'default', open, defaultOpen = false, onOpenChange, delayMs = 150, disabled = false, className, ...rest }) {
    const generatedId = (0, react_1.useId)().replace(/:/g, '');
    const tooltipId = `ds-tooltip-${generatedId}`;
    const [visible, setVisible] = useControllableOpenState(open, defaultOpen, onOpenChange);
    const delayTimerRef = (0, react_1.useRef)(null);
    const trigger = react_1.Children.only(children);
    const clearDelayTimer = () => {
        if (delayTimerRef.current !== null) {
            window.clearTimeout(delayTimerRef.current);
            delayTimerRef.current = null;
        }
    };
    const showTooltip = (immediate) => {
        if (disabled) {
            return;
        }
        clearDelayTimer();
        if (immediate || delayMs <= 0) {
            setVisible(true);
            return;
        }
        delayTimerRef.current = window.setTimeout(() => {
            setVisible(true);
            delayTimerRef.current = null;
        }, delayMs);
    };
    const hideTooltip = () => {
        clearDelayTimer();
        setVisible(false);
    };
    (0, react_1.useEffect)(() => clearDelayTimer, []);
    (0, react_1.useEffect)(() => {
        if (disabled && visible) {
            hideTooltip();
        }
    }, [disabled, visible]);
    const triggerElement = (0, react_1.cloneElement)(trigger, {
        'aria-describedby': disabled
            ? trigger.props['aria-describedby']
            : (0, utils_1.joinIds)(trigger.props['aria-describedby'], visible ? tooltipId : undefined),
        onFocus: composeEventHandlers(trigger.props.onFocus, () => showTooltip(true)),
        onBlur: composeEventHandlers(trigger.props.onBlur, hideTooltip),
        onMouseEnter: composeEventHandlers(trigger.props.onMouseEnter, () => showTooltip(false)),
        onMouseLeave: composeEventHandlers(trigger.props.onMouseLeave, hideTooltip),
        onKeyDown: composeEventHandlers(trigger.props.onKeyDown, (event) => {
            if (event.key === 'Escape') {
                hideTooltip();
            }
        }),
    });
    return ((0, jsx_runtime_1.jsxs)("span", { className: (0, utils_1.cn)('relative inline-flex', className), "data-state": visible ? 'open' : 'closed', ...rest, children: [triggerElement, !disabled && visible ? ((0, jsx_runtime_1.jsx)("span", { id: tooltipId, role: "tooltip", className: (0, utils_1.cn)('pointer-events-none absolute z-50 max-w-ds-tooltip rounded-ds-lg border px-ds-3 py-ds-2 text-ds-xs leading-5 shadow-ds-md', PLACEMENT_CLASSES[placement], TONE_CLASSES[tone]), children: content })) : null] }));
}
