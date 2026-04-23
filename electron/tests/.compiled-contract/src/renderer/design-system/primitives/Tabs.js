"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Tabs = Tabs;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const utils_1 = require("./utils");
function Tabs({ value, onValueChange, items, listClassName, tabClassName, panelClassName, className, ...rest }) {
    const generatedId = (0, react_1.useId)().replace(/:/g, '');
    const tabRefs = (0, react_1.useRef)([]);
    const activeIndex = (0, react_1.useMemo)(() => items.findIndex((item) => item.value === value), [items, value]);
    const activeItem = activeIndex >= 0 ? items[activeIndex] : items[0];
    const activeValue = activeItem?.value ?? value;
    const focusTab = (index) => {
        if (items.length === 0) {
            return;
        }
        const nextIndex = (index + items.length) % items.length;
        tabRefs.current[nextIndex]?.focus();
        onValueChange(items[nextIndex]?.value ?? value);
    };
    const selectedPanelId = activeValue ? `ds-tabs-${generatedId}-panel-${activeValue}` : undefined;
    return ((0, jsx_runtime_1.jsxs)("div", { className: (0, utils_1.cn)('space-y-ds-3', className), ...rest, children: [(0, jsx_runtime_1.jsx)("div", { role: "tablist", "aria-orientation": "horizontal", className: (0, utils_1.cn)('inline-flex max-w-full flex-wrap gap-ds-1 rounded-ds-pill border border-ds-border bg-ds-bg p-ds-1 shadow-ds-sm', listClassName), children: items.map((item, index) => {
                    const selected = item.value === activeValue;
                    const tabId = `ds-tabs-${generatedId}-tab-${item.value}`;
                    const panelId = `ds-tabs-${generatedId}-panel-${item.value}`;
                    return ((0, jsx_runtime_1.jsx)("button", { ref: (node) => {
                            tabRefs.current[index] = node;
                        }, id: tabId, type: "button", role: "tab", "aria-selected": selected, "aria-controls": panelId, tabIndex: selected ? 0 : -1, disabled: item.disabled, onClick: () => onValueChange(item.value), onKeyDown: (event) => {
                            if (item.disabled) {
                                return;
                            }
                            switch (event.key) {
                                case 'ArrowRight':
                                case 'ArrowDown':
                                    event.preventDefault();
                                    focusTab(index + 1);
                                    break;
                                case 'ArrowLeft':
                                case 'ArrowUp':
                                    event.preventDefault();
                                    focusTab(index - 1);
                                    break;
                                case 'Home':
                                    event.preventDefault();
                                    tabRefs.current[0]?.focus();
                                    onValueChange(items[0]?.value ?? value);
                                    break;
                                case 'End':
                                    event.preventDefault();
                                    tabRefs.current[items.length - 1]?.focus();
                                    onValueChange(items[items.length - 1]?.value ?? value);
                                    break;
                                case 'Enter':
                                case ' ':
                                    event.preventDefault();
                                    onValueChange(item.value);
                                    break;
                                default:
                                    break;
                            }
                        }, className: (0, utils_1.cn)('inline-flex min-h-11 items-center justify-center rounded-ds-pill px-ds-4 text-ds-sm font-medium transition-all duration-ds-fast ease-ds-standard', 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg', selected
                            ? 'border border-transparent bg-ds-accent text-ds-accent-contrast shadow-ds-sm'
                            : 'border border-transparent text-ds-muted hover:bg-ds-surface hover:text-ds-text', item.disabled ? 'cursor-not-allowed opacity-50 hover:bg-transparent hover:text-ds-muted' : '', tabClassName), children: item.label }, item.value));
                }) }), activeItem ? ((0, jsx_runtime_1.jsx)("div", { id: selectedPanelId, role: "tabpanel", "aria-labelledby": `ds-tabs-${generatedId}-tab-${activeItem.value}`, className: (0, utils_1.cn)('rounded-ds-xl border border-ds-border bg-ds-surface/92 p-ds-4 text-ds-text shadow-ds-sm', panelClassName), children: activeItem.content })) : null] }));
}
