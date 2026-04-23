"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const handleDeepLink_1 = require("../../src/renderer/application/deepLink/handleDeepLink");
const deepLink_1 = require("../../src/renderer/domain/deepLink/deepLink");
function makeDeps(overrides = {}, log) {
    const callLog = log ?? {
        navigate: [],
        warn: [],
        reauthRequests: 0,
        markedSessionReauthed: 0,
    };
    let sessionReauthed = false;
    const deps = {
        parseUri: deepLink_1.parseDeepLink,
        navigate: (path) => {
            callLog.navigate.push(path);
        },
        warnInvalid: (error, uri) => {
            callLog.warn.push({ error, uri });
        },
        getReauthPolicy: () => 'none',
        requestReauth: async () => {
            callLog.reauthRequests += 1;
            return true;
        },
        hasReauthedThisSession: () => sessionReauthed,
        markSessionReauthed: () => {
            sessionReauthed = true;
            callLog.markedSessionReauthed += 1;
        },
        ...overrides,
    };
    return { deps, log: callLog };
}
async function run() {
    // Case 1: valid URI → navigate called with correct path
    {
        const { deps, log } = makeDeps();
        await (0, handleDeepLink_1.handleDeepLink)('ds-agent://workspace/ws-1/run/r-1', deps);
        strict_1.default.deepEqual(log.navigate, ['/workspace/ws-1/run/r-1']);
        strict_1.default.equal(log.warn.length, 0);
    }
    // Case 2: valid URI with action → path includes ?action=
    {
        const { deps, log } = makeDeps();
        await (0, handleDeepLink_1.handleDeepLink)('ds-agent://workspace/ws-1/run/r-9?action=compare', deps);
        strict_1.default.deepEqual(log.navigate, ['/workspace/ws-1/run/r-9?action=compare']);
    }
    // Case 3: invalid URI (scheme spoofing) → warn, no navigate
    {
        const { deps, log } = makeDeps();
        await (0, handleDeepLink_1.handleDeepLink)('http://workspace/ws-1/run/r-1', deps);
        strict_1.default.equal(log.navigate.length, 0);
        strict_1.default.equal(log.warn.length, 1);
        strict_1.default.equal(log.warn[0].error, 'invalid_scheme');
    }
    // Case 4: invalid URI (extra segment / path traversal) → warn
    {
        const { deps, log } = makeDeps();
        await (0, handleDeepLink_1.handleDeepLink)('ds-agent://workspace/ws-1/run/r-1/extra', deps);
        strict_1.default.equal(log.navigate.length, 0);
        strict_1.default.equal(log.warn[0].error, 'path_traversal');
    }
    // Case 5: invalid URI (too long)
    {
        const { deps, log } = makeDeps();
        const big = `ds-agent://workspace/ws-1/run/${'x'.repeat(2200)}`;
        await (0, handleDeepLink_1.handleDeepLink)(big, deps);
        strict_1.default.equal(log.navigate.length, 0);
        strict_1.default.equal(log.warn[0].error, 'too_long');
    }
    // Case 6: reauth policy 'none' → requestReauth never called
    {
        const { deps, log } = makeDeps({ getReauthPolicy: () => 'none' });
        await (0, handleDeepLink_1.handleDeepLink)('ds-agent://workspace/ws-1/run/r-1', deps);
        strict_1.default.equal(log.reauthRequests, 0);
        strict_1.default.equal(log.navigate.length, 1);
    }
    // Case 7: 'once-per-session' + not authed → requestReauth called, marked
    {
        const { deps, log } = makeDeps({ getReauthPolicy: () => 'once-per-session' });
        await (0, handleDeepLink_1.handleDeepLink)('ds-agent://workspace/ws-1/run/r-1', deps);
        strict_1.default.equal(log.reauthRequests, 1);
        strict_1.default.equal(log.markedSessionReauthed, 1);
        strict_1.default.equal(log.navigate.length, 1);
    }
    // Case 8: 'once-per-session' + already authed → no reauth, navigate
    {
        let sessionReauthed = true;
        const log = { navigate: [], warn: [], reauthRequests: 0, markedSessionReauthed: 0 };
        const deps = {
            parseUri: deepLink_1.parseDeepLink,
            navigate: (path) => {
                log.navigate.push(path);
            },
            warnInvalid: (error, uri) => {
                log.warn.push({ error, uri });
            },
            getReauthPolicy: () => 'once-per-session',
            requestReauth: async () => {
                log.reauthRequests += 1;
                return true;
            },
            hasReauthedThisSession: () => sessionReauthed,
            markSessionReauthed: () => {
                sessionReauthed = true;
                log.markedSessionReauthed += 1;
            },
        };
        await (0, handleDeepLink_1.handleDeepLink)('ds-agent://workspace/ws-1/run/r-1', deps);
        strict_1.default.equal(log.reauthRequests, 0);
        strict_1.default.equal(log.navigate.length, 1);
    }
    // Case 9: 'always' → reauth every invocation
    {
        const { deps, log } = makeDeps({ getReauthPolicy: () => 'always' });
        await (0, handleDeepLink_1.handleDeepLink)('ds-agent://workspace/ws-1/run/r-1', deps);
        await (0, handleDeepLink_1.handleDeepLink)('ds-agent://workspace/ws-1/run/r-2', deps);
        strict_1.default.equal(log.reauthRequests, 2);
        strict_1.default.equal(log.markedSessionReauthed, 0); // never marked under 'always'
        strict_1.default.equal(log.navigate.length, 2);
    }
    // Case 10: reauth returns false (denied) → no navigate
    {
        const { deps, log } = makeDeps({
            getReauthPolicy: () => 'always',
            requestReauth: async () => false,
        });
        await (0, handleDeepLink_1.handleDeepLink)('ds-agent://workspace/ws-1/run/r-1', deps);
        strict_1.default.equal(log.navigate.length, 0);
    }
    // Case 11: workspace_id preserved in path
    {
        const { deps, log } = makeDeps();
        await (0, handleDeepLink_1.handleDeepLink)('ds-agent://workspace/proj-7/artifact/art-99', deps);
        strict_1.default.equal(log.navigate[0], '/workspace/proj-7/artifact/art-99');
    }
    // Case 12: all 4 resource types navigate correctly
    {
        const types = ['run', 'artifact', 'checkpoint', 'verifier_result'];
        for (const type of types) {
            const { deps, log } = makeDeps();
            await (0, handleDeepLink_1.handleDeepLink)(`ds-agent://workspace/ws-1/${type}/id-1`, deps);
            strict_1.default.equal(log.navigate[0], `/workspace/ws-1/${type}/id-1`);
        }
    }
    // Pure helper: buildDeepLinkRoute is consistent with handler output
    strict_1.default.equal((0, handleDeepLink_1.buildDeepLinkRoute)({
        workspaceId: 'ws-1',
        resourceType: 'run',
        resourceId: 'r-1',
        action: null,
    }), '/workspace/ws-1/run/r-1');
    strict_1.default.equal((0, handleDeepLink_1.buildDeepLinkRoute)({
        workspaceId: 'ws-1',
        resourceType: 'artifact',
        resourceId: 'art-1',
        action: 'promote',
    }), '/workspace/ws-1/artifact/art-1?action=promote');
    // Type guard: DeepLinkReauthPolicy values exist
    const policies = ['none', 'once-per-session', 'always'];
    strict_1.default.equal(policies.length, 3);
    console.log('[contract] PASS deep-link-handler (12 cases)');
}
void run();
