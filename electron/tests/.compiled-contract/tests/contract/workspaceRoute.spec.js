"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const workspaceRoute_1 = require("../../src/renderer/application/workspace/workspaceRoute");
function run() {
    strict_1.default.equal((0, workspaceRoute_1.normalizeArtifactsView)({ subPath: 'workspace/charts' }), 'workspace');
    strict_1.default.equal((0, workspaceRoute_1.normalizeArtifactsView)({ subPath: 'workspace' }), 'workspace');
    strict_1.default.equal((0, workspaceRoute_1.normalizeArtifactsView)({ subPath: 'unknown' }), 'files');
    strict_1.default.equal((0, workspaceRoute_1.normalizeEvidenceWorkspaceTab)({ subPath: 'workspace/files' }), 'overview');
    strict_1.default.equal((0, workspaceRoute_1.normalizeEvidenceWorkspaceTab)({ subPath: 'workspace/highlight/card/card-1' }), 'overview');
    strict_1.default.equal((0, workspaceRoute_1.normalizeEvidenceWorkspaceTab)({ subPath: 'workspace/not-a-tab' }), 'overview');
    strict_1.default.equal((0, workspaceRoute_1.normalizeEvidenceWorkspaceTab)({ subPath: 'files' }), 'overview');
    strict_1.default.equal((0, workspaceRoute_1.normalizeEvidenceWorkspaceFocus)({ subPath: 'workspace/files' }), null);
    strict_1.default.deepEqual((0, workspaceRoute_1.normalizeEvidenceWorkspaceFocus)({ subPath: 'workspace/highlight/card/card-1' }), {
        mode: 'highlight',
        target: 'card',
        value: 'card-1',
    });
    strict_1.default.deepEqual((0, workspaceRoute_1.parseEvidenceWorkspaceRoute)({ subPath: 'workspace/export/detail/result/result%2Fwith%2Fslash' }), {
        tab: 'export',
        focus: {
            mode: 'detail',
            target: 'result',
            value: 'result/with/slash',
        },
    });
    strict_1.default.deepEqual((0, workspaceRoute_1.parseEvidenceWorkspaceRoute)({ subPath: 'workspace/detail/message/msg-7' }), {
        tab: 'overview',
        focus: {
            mode: 'detail',
            target: 'message',
            value: 'msg-7',
        },
    });
    strict_1.default.equal((0, workspaceRoute_1.normalizeEvidenceWorkspaceFocus)({ subPath: 'workspace/summary/highlight/unknown/card-1' }), null);
    strict_1.default.equal((0, workspaceRoute_1.buildEvidenceWorkspacePath)('overview'), '/artifacts/workspace/overview');
    strict_1.default.equal((0, workspaceRoute_1.buildEvidenceWorkspacePath)('export'), '/artifacts/workspace/export');
    strict_1.default.equal((0, workspaceRoute_1.buildEvidenceWorkspacePath)('overview', {
        mode: 'detail',
        target: 'card',
        value: 'card-1',
    }), '/artifacts/workspace/overview/detail/card/card-1');
    console.log('[contract] PASS workspace-route (13 cases)');
}
run();
