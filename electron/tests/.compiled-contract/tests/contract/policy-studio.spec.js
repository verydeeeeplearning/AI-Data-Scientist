"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const policyStudioCatalog_1 = require("../../src/renderer/components/settings/policyStudioCatalog");
function run() {
    strict_1.default.equal(policyStudioCatalog_1.POLICY_STUDIO_PRESETS.length, 4);
    strict_1.default.deepEqual(policyStudioCatalog_1.POLICY_STUDIO_PRESETS.map((preset) => preset.id), ['delegate-peer', 'executive-review', 'audit-guard', 'mentor-walkthrough']);
    strict_1.default.deepEqual(policyStudioCatalog_1.POLICY_STUDIO_PRESETS.find((preset) => preset.id === 'executive-review'), {
        id: 'executive-review',
        label: 'Executive Review',
        authority: 'supervised',
        audience: 'executive',
        summary: 'Keep approvals in the loop and shape the output as an executive brief.',
    });
    const exact = (0, policyStudioCatalog_1.buildLegacyModeMigrationPreview)('supervised');
    strict_1.default.equal(exact.legacyMode, 'supervised');
    strict_1.default.equal(exact.exactMatch, true);
    strict_1.default.equal(exact.authority, 'supervised');
    strict_1.default.equal(exact.audience, 'peer_ds');
    const approximate = (0, policyStudioCatalog_1.buildLegacyModeMigrationPreview)('step-by-step');
    strict_1.default.equal(approximate.legacyMode, 'step-by-step');
    strict_1.default.equal(approximate.exactMatch, false);
    strict_1.default.equal(approximate.authority, 'supervised');
    strict_1.default.equal(approximate.audience, 'junior_mentor');
    console.log('[contract] PASS policy-studio catalog');
}
run();
