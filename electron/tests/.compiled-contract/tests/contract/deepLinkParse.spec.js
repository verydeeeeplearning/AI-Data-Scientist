"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const deepLink_1 = require("../../src/renderer/domain/deepLink/deepLink");
function expectFailure(input, error) {
    const result = (0, deepLink_1.parseDeepLink)(input);
    strict_1.default.equal(result.ok, false, `Expected failure for ${JSON.stringify(input)}`);
    if (result.ok === false) {
        strict_1.default.equal(result.error, error, `Expected error=${error} got=${result.error}`);
    }
}
function run() {
    // Happy path: every resource type round-trips.
    for (const resourceType of deepLink_1.DEEP_LINK_RESOURCE_TYPES) {
        const uri = `ds-agent://workspace/ws-1/${resourceType}/abc-123`;
        const result = (0, deepLink_1.parseDeepLink)(uri);
        strict_1.default.equal(result.ok, true, `Expected ok for ${uri}`);
        if (result.ok) {
            strict_1.default.equal(result.value.workspaceId, 'ws-1');
            strict_1.default.equal(result.value.resourceType, resourceType);
            strict_1.default.equal(result.value.resourceId, 'abc-123');
            strict_1.default.equal(result.value.action, null);
        }
    }
    // Action query param surfaced when present.
    const withAction = (0, deepLink_1.parseDeepLink)('ds-agent://workspace/ws-1/run/r-9?action=compare');
    strict_1.default.equal(withAction.ok, true);
    if (withAction.ok) {
        strict_1.default.equal(withAction.value.action, 'compare');
    }
    // build → parse round-trip
    const round = (0, deepLink_1.parseDeepLink)((0, deepLink_1.buildDeepLinkUri)({ workspaceId: 'ws-1', resourceType: 'artifact', resourceId: 'art-7', action: 'promote' }));
    strict_1.default.equal(round.ok, true);
    if (round.ok) {
        strict_1.default.equal(round.value.workspaceId, 'ws-1');
        strict_1.default.equal(round.value.resourceType, 'artifact');
        strict_1.default.equal(round.value.resourceId, 'art-7');
        strict_1.default.equal(round.value.action, 'promote');
    }
    // Sanitize: scheme spoofing
    expectFailure('http://workspace/ws-1/run/r-1', 'invalid_scheme');
    expectFailure('javascript://workspace/ws-1/run/r-1', 'invalid_scheme');
    // Sanitize: wrong host
    expectFailure('ds-agent://settings/ws-1/run/r-1', 'invalid_host');
    // Sanitize: path traversal disguise via extra segments. URL parsing already
    // normalizes literal `..`, so the explicit guard catches the residual case
    // of "more than one segment after the resource type".
    expectFailure('ds-agent://workspace/ws-1/run/r-1/extra', 'path_traversal');
    expectFailure('ds-agent://workspace/ws-1/run/r-1/extra/more', 'path_traversal');
    // Sanitize: oversized URI
    const big = `ds-agent://workspace/ws-1/run/${'x'.repeat(2200)}`;
    expectFailure(big, 'too_long');
    // Sanitize: unknown resource type
    expectFailure('ds-agent://workspace/ws-1/secret/r-1', 'unknown_resource_type');
    // Sanitize: missing parts
    expectFailure('ds-agent://workspace', 'missing_workspace');
    expectFailure('ds-agent://workspace/ws-1', 'unknown_resource_type');
    expectFailure('ds-agent://workspace/ws-1/run', 'missing_resource_id');
    // Sanitize: invalid characters in workspace / id
    expectFailure('ds-agent://workspace/ws%20with%20space/run/r-1', 'invalid_workspace');
    expectFailure('ds-agent://workspace/ws-1/run/r%20one', 'invalid_resource_id');
    // Sanitize: invalid action characters
    expectFailure('ds-agent://workspace/ws-1/run/r-1?action=do%20it', 'invalid_action');
    // Empty / non-string input rejected
    expectFailure('', 'invalid_scheme');
    console.log('[contract] PASS deep-link-parse (16 cases)');
}
run();
