"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const primitives_1 = require("../../src/renderer/design-system/primitives");
function run() {
    strict_1.default.equal(typeof primitives_1.Accordion, 'function');
    strict_1.default.equal(typeof primitives_1.Checkbox, 'function');
    strict_1.default.equal(typeof primitives_1.Chip, 'function');
    strict_1.default.equal(typeof primitives_1.Input, 'function');
    strict_1.default.equal(typeof primitives_1.Radio, 'function');
    strict_1.default.equal(typeof primitives_1.Textarea, 'function');
    strict_1.default.equal(typeof primitives_1.Spinner, 'function');
    strict_1.default.equal(typeof primitives_1.Skeleton, 'function');
    strict_1.default.equal(typeof primitives_1.DialogShell, 'function');
    strict_1.default.equal(typeof primitives_1.DrawerShell, 'function');
    strict_1.default.equal(typeof primitives_1.Tabs, 'function');
    strict_1.default.equal(typeof primitives_1.Tooltip, 'function');
    strict_1.default.equal(typeof primitives_1.Popover, 'function');
    strict_1.default.equal(typeof primitives_1.Toast, 'function');
    strict_1.default.equal(typeof primitives_1.ToastViewport, 'function');
    console.log('[contract] PASS design-system-primitives (15 exports)');
}
run();
