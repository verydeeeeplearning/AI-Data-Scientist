"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Disabled = exports.ErrorState = exports.Checked = exports.Default = void 0;
const Checkbox_1 = require("./Checkbox");
const meta = {
    title: 'Design System/Primitives/Checkbox',
    component: Checkbox_1.Checkbox,
    tags: ['autodocs'],
    args: {
        id: 'storybook-checkbox',
        label: 'Require operator acknowledgement',
        description: 'Block autonomous execution until a human confirms the risk summary.',
        hint: 'Use this for high-impact actions during quiet hours.',
    },
};
exports.default = meta;
exports.Default = {};
exports.Checked = {
    args: {
        id: 'storybook-checkbox-checked',
        label: 'Auto-close after completion',
        description: 'Dismiss the dialog when the delivery policy finishes sending the outcome digest.',
        defaultChecked: true,
    },
};
exports.ErrorState = {
    args: {
        id: 'storybook-checkbox-error',
        label: 'Allow irreversible action',
        description: 'This approval bypasses the default rollback checkpoint.',
        errorMessage: 'Irreversible actions require a typed rationale before approval.',
    },
};
exports.Disabled = {
    args: {
        id: 'storybook-checkbox-disabled',
        label: 'Mute follow-up notifications',
        description: 'This control becomes available after the current alert is acknowledged.',
        disabled: true,
    },
};
