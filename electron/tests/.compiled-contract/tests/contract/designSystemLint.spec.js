"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
// eslint-disable-next-line @typescript-eslint/no-require-imports
const path = require('node:path');
// eslint-disable-next-line @typescript-eslint/no-require-imports
const lint = require(path.resolve(__dirname, '..', '..', '..', '..', 'scripts', 'lintDesignSystemCore.cjs'));
const scanSourceFile = lint.scanSourceFile;
function run() {
    {
        const violations = scanSourceFile('src/renderer/design-system/primitives/Button.tsx', "export const Button = () => <div className=\"text-[#fff]\">x</div>;\n");
        strict_1.default.equal(violations.length, 2);
        strict_1.default.equal(violations[0].rule, 'hex-literal');
        strict_1.default.equal(violations[1].rule, 'tailwind-arbitrary-value');
    }
    {
        const violations = scanSourceFile('src/renderer/design-system/themes/dark.ts', "export const token = '#ffffff';\n");
        strict_1.default.equal(violations.length, 0);
    }
    {
        const violations = scanSourceFile('src/renderer/components/providers/ThemeProvider.tsx', "export const X = () => <div className=\"tracking-[0.18em]\" />;\n");
        strict_1.default.equal(violations.length, 1);
        strict_1.default.equal(violations[0].rule, 'tailwind-arbitrary-value');
    }
    {
        const violations = scanSourceFile('src/renderer/components/mission/MissionHeader.tsx', "export const X = () => <div className=\"tracking-[0.18em]\" />;\n");
        strict_1.default.equal(violations.length, 0);
    }
    console.log('[contract] PASS design-system-lint (4 cases)');
}
run();
