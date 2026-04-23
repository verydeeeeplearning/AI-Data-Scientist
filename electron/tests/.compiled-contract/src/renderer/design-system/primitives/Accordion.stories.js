"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.NoCollapse = exports.Default = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const Accordion_1 = require("./Accordion");
const noop = () => undefined;
const meta = {
    title: 'Design System/Primitives/Accordion',
    component: Accordion_1.Accordion,
    tags: ['autodocs'],
    args: {
        value: 'delivery',
        onValueChange: noop,
        items: [
            {
                value: 'delivery',
                title: 'Delivery policy',
                content: ((0, jsx_runtime_1.jsx)("div", { className: "space-y-ds-2", children: (0, jsx_runtime_1.jsx)("p", { className: "text-ds-sm leading-6 text-ds-muted", children: "Outcome digests respect quiet hours and notify only the subscribed operator set." }) })),
            },
            {
                value: 'sessions',
                title: 'Session isolation',
                content: ((0, jsx_runtime_1.jsx)("p", { className: "text-ds-sm leading-6 text-ds-muted", children: "Channel identity stays canonical so retries resume into the correct thread." })),
            },
            {
                value: 'guards',
                title: 'Safety guards',
                content: ((0, jsx_runtime_1.jsx)("p", { className: "text-ds-sm leading-6 text-ds-muted", children: "Sandbox violations block execution until the approval flow captures a human decision." })),
            },
        ],
    },
};
exports.default = meta;
function AccordionStory(args) {
    const [value, setValue] = (0, react_1.useState)(args.value);
    return (0, jsx_runtime_1.jsx)(Accordion_1.Accordion, { ...args, value: value, onValueChange: setValue });
}
exports.Default = {
    args: {
        onValueChange: noop,
    },
    render: (args) => (0, jsx_runtime_1.jsx)(AccordionStory, { ...args }),
};
exports.NoCollapse = {
    args: {
        value: 'delivery',
        onValueChange: noop,
        allowCollapse: false,
    },
    render: (args) => (0, jsx_runtime_1.jsx)(AccordionStory, { ...args }),
};
