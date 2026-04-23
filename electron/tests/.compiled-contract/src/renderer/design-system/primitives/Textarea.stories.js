"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ErrorState = exports.WithHint = exports.Default = void 0;
const Textarea_1 = require("./Textarea");
const meta = {
    title: 'Design System/Primitives/Textarea',
    component: Textarea_1.Textarea,
    tags: ['autodocs'],
    args: {
        id: 'storybook-textarea',
        label: 'Mission brief',
        description: 'Capture the business context, target metric, and delivery deadline.',
        placeholder: 'Summarize the churn drivers for the Q2 renewal committee...',
    },
};
exports.default = meta;
exports.Default = {};
exports.WithHint = {
    args: {
        hint: 'Keep this under 500 characters so the operator digest stays readable.',
        defaultValue: 'Review the latest churn model and prepare a one-page summary for the subscription leadership team.',
    },
};
exports.ErrorState = {
    args: {
        value: 'Need help soon.',
        errorMessage: 'Include the target dataset, success metric, and delivery date.',
        resize: 'none',
    },
};
