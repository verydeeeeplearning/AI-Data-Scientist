"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const missionBriefModel_1 = require("../../src/renderer/components/mission/missionBriefModel");
function run() {
    strict_1.default.equal((0, missionBriefModel_1.normalizeDeliveryTenant)('  acme  '), 'acme');
    strict_1.default.equal((0, missionBriefModel_1.normalizeDeliveryTenant)(''), 'default');
    strict_1.default.equal((0, missionBriefModel_1.resolveThemeId)({ theme_id: ' deloitte_v1 ', region: 'apac' }), 'deloitte_v1');
    strict_1.default.deepEqual((0, missionBriefModel_1.buildDeliveryGlobalContext)({ region: 'apac', theme_id: 'legacy_v1' }, ' acme_v2 '), { region: 'apac', theme_id: 'acme_v2' });
    strict_1.default.deepEqual((0, missionBriefModel_1.buildDeliveryGlobalContext)({ region: 'apac', theme_id: 'legacy_v1' }, '   '), { region: 'apac' });
    strict_1.default.deepEqual((0, missionBriefModel_1.resolveProviderBackedRenderOptions)(false, 'openai/gpt-5.4'), { providerBacked: false });
    strict_1.default.deepEqual((0, missionBriefModel_1.resolveProviderBackedRenderOptions)(true, ' openai/gpt-5.4 '), { providerBacked: true, model: 'openai/gpt-5.4' });
    strict_1.default.equal((0, missionBriefModel_1.formatRenderResultNotice)({
        pack_id: 'DP-2026-001',
        artifact_id: 'ART-2026-001',
        output_path: 'C:/tmp/exec-brief.pptx',
        format: 'pptx',
        verifier_status: 'pass',
        flagged_claims: [],
        pack_status: 'rendered',
        new_version: 4,
        renderer_mode: 'provider-backed',
        renderer_model: 'openai/gpt-5.4',
    }), 'Rendered ART-2026-001 (pptx) to C:/tmp/exec-brief.pptx. Renderer: provider-backed | Model: openai/gpt-5.4.');
    console.log('[contract] PASS mission-brief model');
}
run();
