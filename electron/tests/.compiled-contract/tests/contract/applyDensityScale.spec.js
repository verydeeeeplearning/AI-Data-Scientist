"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const applyDensityScale_1 = require("../../src/renderer/application/layout/applyDensityScale");
const density_1 = require("../../src/renderer/domain/layout/density");
function run() {
    // domain invariants
    strict_1.default.deepEqual([...density_1.DENSITY_MODES].sort(), ['comfortable', 'compact', 'spacious']);
    strict_1.default.equal(density_1.DEFAULT_DENSITY_MODE, 'comfortable');
    strict_1.default.equal((0, density_1.isDensityMode)('compact'), true);
    strict_1.default.equal((0, density_1.isDensityMode)('cozy'), false);
    strict_1.default.equal((0, density_1.isDensityMode)(undefined), false);
    // scale table
    strict_1.default.deepEqual((0, density_1.getDensityScale)('compact'), { spacing: 0.75, font: 0.9 });
    strict_1.default.deepEqual((0, density_1.getDensityScale)('comfortable'), { spacing: 1, font: 1 });
    strict_1.default.deepEqual((0, density_1.getDensityScale)('spacious'), { spacing: 1.25, font: 1.1 });
    // application: comfortable mode preserves base values
    const comfortable = (0, applyDensityScale_1.applyDensityScale)('comfortable');
    strict_1.default.equal(comfortable['--ds-space-4'], '1rem');
    strict_1.default.equal(comfortable['--ds-font-size-md'], '1rem');
    strict_1.default.equal(comfortable['--ds-space-1'], '0.25rem');
    // application: compact mode shrinks both axes
    const compact = (0, applyDensityScale_1.applyDensityScale)('compact');
    strict_1.default.equal(compact['--ds-space-4'], '0.75rem');
    strict_1.default.equal(compact['--ds-font-size-md'], '0.9rem');
    // application: spacious mode enlarges both axes
    const spacious = (0, applyDensityScale_1.applyDensityScale)('spacious');
    strict_1.default.equal(spacious['--ds-space-4'], '1.25rem');
    strict_1.default.equal(spacious['--ds-font-size-md'], '1.1rem');
    // application emits both spacing and font variables in a single call
    const overrideKeys = Object.keys((0, applyDensityScale_1.applyDensityScale)('compact'));
    strict_1.default.ok(overrideKeys.some((key) => key.startsWith('--ds-space-')));
    strict_1.default.ok(overrideKeys.some((key) => key.startsWith('--ds-font-size-')));
    // pure function: same input → same output
    const a = (0, applyDensityScale_1.applyDensityScale)('spacious');
    const b = (0, applyDensityScale_1.applyDensityScale)('spacious');
    strict_1.default.deepEqual(a, b);
    console.log('[contract] PASS apply-density-scale (8 cases)');
}
run();
