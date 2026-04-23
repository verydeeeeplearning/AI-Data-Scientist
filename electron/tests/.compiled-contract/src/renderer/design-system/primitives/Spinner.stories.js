"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Warning = exports.WithLabel = exports.Default = void 0;
const Spinner_1 = require("./Spinner");
const meta = {
    title: 'Design System/Primitives/Spinner',
    component: Spinner_1.Spinner,
    tags: ['autodocs'],
    args: {
        tone: 'accent',
        size: 'md',
    },
};
exports.default = meta;
exports.Default = {};
exports.WithLabel = {
    args: {
        label: 'Running profile checks',
    },
};
exports.Warning = {
    args: {
        tone: 'warning',
        size: 'lg',
        label: 'Waiting on approval',
    },
};
