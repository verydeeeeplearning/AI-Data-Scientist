"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const themes_1 = require("../../src/renderer/design-system/themes");
function run() {
    {
        const theme = (0, themes_1.loadStoredTheme)({
            getItem: () => 'high-contrast',
        });
        strict_1.default.equal(theme, 'high-contrast');
    }
    {
        const theme = (0, themes_1.loadStoredTheme)({
            getItem: () => null,
        }, () => ({ matches: true }));
        strict_1.default.equal(theme, 'light');
    }
    {
        const dark = (0, themes_1.buildThemeTokenMap)('dark');
        const light = (0, themes_1.buildThemeTokenMap)('light');
        strict_1.default.ok(dark['--ds-space-4']);
        strict_1.default.ok(dark['--ds-font-size-sm']);
        strict_1.default.ok(dark['--ds-color-bg']);
        strict_1.default.notEqual(dark['--ds-color-bg'], light['--ds-color-bg']);
    }
    {
        strict_1.default.equal((0, themes_1.getNextTheme)('dark'), 'light');
        strict_1.default.equal((0, themes_1.getNextTheme)('light'), 'high-contrast');
        strict_1.default.equal((0, themes_1.getNextTheme)('high-contrast'), 'dark');
    }
    console.log('[contract] PASS design-system-theme (4 cases)');
}
run();
