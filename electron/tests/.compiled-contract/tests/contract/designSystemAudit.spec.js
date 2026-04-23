"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const node_child_process_1 = require("node:child_process");
const node_path_1 = __importDefault(require("node:path"));
function run() {
    const repoRoot = node_path_1.default.resolve(__dirname, '..', '..', '..', '..');
    const output = (0, node_child_process_1.execFileSync)(process.execPath, ['scripts/audit-design-system-usage.mjs', '--json'], {
        cwd: repoRoot,
        encoding: 'utf8',
    });
    const audit = JSON.parse(output);
    strict_1.default.equal(typeof audit.storybook.exports, 'number');
    strict_1.default.equal(typeof audit.wave4SurfaceAdoption.percentage, 'number');
    strict_1.default.equal(typeof audit.legacyMigration.percentage, 'number');
    strict_1.default.ok(audit.storybook.exports >= 50);
    strict_1.default.ok(audit.wave4SurfaceAdoption.percentage >= 80);
    strict_1.default.ok(audit.legacyMigration.percentage >= 30);
    strict_1.default.equal(audit.storybook.passed, true);
    strict_1.default.equal(audit.wave4SurfaceAdoption.passed, true);
    strict_1.default.equal(audit.legacyMigration.passed, true);
    strict_1.default.equal(audit.overallPassed, true);
    console.log('[contract] PASS design-system-audit (4 cases)');
}
run();
