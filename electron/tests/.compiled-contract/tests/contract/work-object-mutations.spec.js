"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const workObjectPanelModel_1 = require("../../src/renderer/components/workflow/workObjectPanelModel");
function run() {
    // nextPhase: normal progression
    strict_1.default.equal((0, workObjectPanelModel_1.nextPhase)('intake'), 'executing');
    strict_1.default.equal((0, workObjectPanelModel_1.nextPhase)('executing'), 'review');
    strict_1.default.equal((0, workObjectPanelModel_1.nextPhase)('review'), 'documenting');
    strict_1.default.equal((0, workObjectPanelModel_1.nextPhase)('documenting'), 'followup');
    strict_1.default.equal((0, workObjectPanelModel_1.nextPhase)('followup'), 'closed');
    // nextPhase: terminal phases return null
    strict_1.default.equal((0, workObjectPanelModel_1.nextPhase)('closed'), null);
    strict_1.default.equal((0, workObjectPanelModel_1.nextPhase)('failed'), null);
    // canAdvance: true for active phases
    const advanceable = ['intake', 'executing', 'review', 'documenting', 'followup'];
    for (const phase of advanceable) {
        strict_1.default.equal((0, workObjectPanelModel_1.canAdvance)(phase), true, `canAdvance('${phase}') should be true`);
    }
    // canAdvance: false for terminal phases
    strict_1.default.equal((0, workObjectPanelModel_1.canAdvance)('closed'), false);
    strict_1.default.equal((0, workObjectPanelModel_1.canAdvance)('failed'), false);
    // canClose: true for all non-terminal phases
    for (const phase of advanceable) {
        strict_1.default.equal((0, workObjectPanelModel_1.canClose)(phase), true, `canClose('${phase}') should be true`);
    }
    // canClose: false for terminal phases
    strict_1.default.equal((0, workObjectPanelModel_1.canClose)('closed'), false);
    strict_1.default.equal((0, workObjectPanelModel_1.canClose)('failed'), false);
    console.log('[contract] PASS work-object-mutations model');
}
run();
