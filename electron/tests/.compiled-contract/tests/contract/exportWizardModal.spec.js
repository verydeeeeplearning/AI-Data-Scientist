"use strict";
/**
 * Contract test for ExportWizardModal helper expectations.
 *
 * The modal is a pure render component, so we exercise the component's
 * default port shape and its serialization surface without mounting React.
 */
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const ExportWizardModal_1 = require("../../src/renderer/components/workspace/ExportWizardModal");
const results = [];
function test(name, fn) {
    try {
        fn();
        results.push({ name, ok: true });
    }
    catch (error) {
        results.push({ name, ok: false, error });
    }
}
test('ExportWizardModal default export is a React component function', () => {
    strict_1.default.equal(typeof ExportWizardModal_1.ExportWizardModal, 'function');
});
test('ExportPort type accepts the documented call shape including audience', () => {
    const port = async ({ path, format, audience }) => ({
        path,
        format,
        audience,
        ok: true,
    });
    return port({ path: '/tmp/file.csv', format: 'html', audience: 'exec' }).then((payload) => {
        strict_1.default.equal(payload.path, '/tmp/file.csv');
        strict_1.default.equal(payload.format, 'html');
        strict_1.default.equal(payload.audience, 'exec');
    });
});
test('ExportWizardCandidate accepts the documented field set', () => {
    const sample = {
        id: 'c1',
        name: 'Sample',
        path: '/tmp/sample.csv',
        type: 'csv',
        formats: ['json', 'parquet'],
    };
    strict_1.default.equal(sample.formats.length, 2);
});
test('ExportWizardModal props can carry a default audience', () => {
    const props = {
        open: true,
        candidates: [],
        defaultAudience: 'ml',
        exportPort: (async () => ({})),
        onClose: () => undefined,
    };
    strict_1.default.equal(props.defaultAudience, 'ml');
});
const failed = results.filter((entry) => !entry.ok);
for (const entry of results) {
    console.log(`  ${entry.ok ? 'ok' : 'FAIL'}  ${entry.name}`);
    if (!entry.ok) {
        console.log('       ', entry.error);
    }
}
console.log(`\nexportWizardModal.spec — ${results.length - failed.length}/${results.length} passed`);
if (failed.length > 0) {
    process.exitCode = 1;
}
