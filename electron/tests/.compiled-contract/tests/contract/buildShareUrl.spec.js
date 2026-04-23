"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const buildShareUrl_1 = require("../../src/renderer/application/sharing/buildShareUrl");
function run() {
    // run resource builds correct path
    strict_1.default.equal((0, buildShareUrl_1.buildShareUrl)({ resourceType: 'run', resourceId: 'run-42' }).url, '/runs/run-42');
    // artifact / session / mission cover all 4 resource types
    strict_1.default.equal((0, buildShareUrl_1.buildShareUrl)({ resourceType: 'artifact', resourceId: 'art-abc' }).url, '/artifacts/art-abc');
    strict_1.default.equal((0, buildShareUrl_1.buildShareUrl)({ resourceType: 'session', resourceId: 's-1' }).url, '/sessions/s-1');
    strict_1.default.equal((0, buildShareUrl_1.buildShareUrl)({ resourceType: 'mission', resourceId: 'm-9' }).url, '/missions/m-9');
    // baseUrl prefix is prepended
    strict_1.default.equal((0, buildShareUrl_1.buildShareUrl)({
        resourceType: 'run',
        resourceId: 'run-1',
        baseUrl: 'https://ds-agent.local',
    }).url, 'https://ds-agent.local/runs/run-1');
    // baseUrl trailing slash is normalized
    strict_1.default.equal((0, buildShareUrl_1.buildShareUrl)({
        resourceType: 'run',
        resourceId: 'run-1',
        baseUrl: 'https://ds-agent.local/',
    }).url, 'https://ds-agent.local/runs/run-1');
    // resourceId whitespace is trimmed
    const trimmed = (0, buildShareUrl_1.buildShareUrl)({ resourceType: 'run', resourceId: '  run-77  ' });
    strict_1.default.equal(trimmed.resourceId, 'run-77');
    strict_1.default.ok(trimmed.url.endsWith('/runs/run-77'));
    // empty resourceId throws
    strict_1.default.throws(() => (0, buildShareUrl_1.buildShareUrl)({ resourceType: 'run', resourceId: '   ' }), /resourceId is required/);
    // resourceId with special chars is encoded
    const encoded = (0, buildShareUrl_1.buildShareUrl)({ resourceType: 'run', resourceId: 'run/with/slash' });
    strict_1.default.ok(encoded.url.includes('run%2Fwith%2Fslash'));
    console.log('[contract] PASS build-share-url (10 cases)');
}
run();
