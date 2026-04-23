"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.WithoutDescription = exports.Default = void 0;
const Select_1 = require("./Select");
const meta = {
    title: 'Design System/Primitives/Select',
    component: Select_1.Select,
    tags: ['autodocs'],
    args: {
        id: 'storybook-select',
        label: 'Theme',
        description: 'Choose the operator console surface tone.',
        value: 'dark',
        options: [
            { value: 'dark', label: 'Dark' },
            { value: 'light', label: 'Light' },
            { value: 'high-contrast', label: 'High Contrast' },
        ],
    },
};
exports.default = meta;
exports.Default = {};
exports.WithoutDescription = {
    args: {
        description: undefined,
    },
};
