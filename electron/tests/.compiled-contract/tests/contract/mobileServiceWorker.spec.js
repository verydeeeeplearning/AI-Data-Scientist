"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const cacheStrategy_1 = require("../../src/mobile/sw/cacheStrategy");
const ORIGIN = 'https://mobile.local';
function makeRequest(partial) {
    const headers = partial.headers ?? { get: () => null };
    return {
        method: 'GET',
        mode: undefined,
        destination: undefined,
        ...partial,
        headers,
    };
}
const tests = [];
function test(name, fn) {
    tests.push({ name, fn });
}
test('cache name registry stays stable & versioned', () => {
    strict_1.default.equal(cacheStrategy_1.MOBILE_CACHE_NAME, 'ds-agent-mobile-v1');
    strict_1.default.ok(cacheStrategy_1.MOBILE_CACHE_NAME.startsWith(cacheStrategy_1.MOBILE_CACHE_PREFIX));
});
test('isSameOrigin handles absolute and relative URLs', () => {
    strict_1.default.equal((0, cacheStrategy_1.isSameOrigin)(`${ORIGIN}/index.html`, ORIGIN), true);
    strict_1.default.equal((0, cacheStrategy_1.isSameOrigin)('/api/runs', ORIGIN), true);
    strict_1.default.equal((0, cacheStrategy_1.isSameOrigin)('https://other.example/x', ORIGIN), false);
    strict_1.default.equal((0, cacheStrategy_1.isSameOrigin)('http://different.local:8080/', ORIGIN), false);
});
test('isApiRequest matches /api/ paths only', () => {
    strict_1.default.equal((0, cacheStrategy_1.isApiRequest)(`${ORIGIN}/api/runs`, ORIGIN), true);
    strict_1.default.equal((0, cacheStrategy_1.isApiRequest)(`${ORIGIN}/api/`, ORIGIN), true);
    strict_1.default.equal((0, cacheStrategy_1.isApiRequest)(`${ORIGIN}/index.html`, ORIGIN), false);
    strict_1.default.equal((0, cacheStrategy_1.isApiRequest)(`${ORIGIN}/manifest.json`, ORIGIN), false);
    strict_1.default.equal((0, cacheStrategy_1.isApiRequest)('https://other.example/api/runs', ORIGIN), false);
});
test('isAppShellRequest covers shell assets and not API or cross-origin', () => {
    strict_1.default.equal((0, cacheStrategy_1.isAppShellRequest)(`${ORIGIN}/`, ORIGIN), true);
    strict_1.default.equal((0, cacheStrategy_1.isAppShellRequest)(`${ORIGIN}/index.html`, ORIGIN), true);
    strict_1.default.equal((0, cacheStrategy_1.isAppShellRequest)(`${ORIGIN}/manifest.json`, ORIGIN), true);
    strict_1.default.equal((0, cacheStrategy_1.isAppShellRequest)(`${ORIGIN}/assets/main-abc.js`, ORIGIN), true);
    strict_1.default.equal((0, cacheStrategy_1.isAppShellRequest)(`${ORIGIN}/assets/main-abc.css`, ORIGIN), true);
    strict_1.default.equal((0, cacheStrategy_1.isAppShellRequest)(`${ORIGIN}/icons/icon-192.png`, ORIGIN), true);
    strict_1.default.equal((0, cacheStrategy_1.isAppShellRequest)(`${ORIGIN}/api/runs`, ORIGIN), false);
    strict_1.default.equal((0, cacheStrategy_1.isAppShellRequest)('https://other.example/main.js', ORIGIN), false);
});
test('isNavigationRequest detects mode=navigate, document destination, accept html', () => {
    strict_1.default.equal((0, cacheStrategy_1.isNavigationRequest)(makeRequest({ url: `${ORIGIN}/`, mode: 'navigate' })), true);
    strict_1.default.equal((0, cacheStrategy_1.isNavigationRequest)(makeRequest({ url: `${ORIGIN}/x`, destination: 'document' })), true);
    strict_1.default.equal((0, cacheStrategy_1.isNavigationRequest)(makeRequest({
        url: `${ORIGIN}/x`,
        headers: { get: (k) => (k === 'accept' ? 'text/html' : null) },
    })), true);
    strict_1.default.equal((0, cacheStrategy_1.isNavigationRequest)(makeRequest({ url: `${ORIGIN}/api/x` })), false);
});
test('chooseStrategy: GET navigation → navigation-fallback', () => {
    const req = makeRequest({ url: `${ORIGIN}/runs`, mode: 'navigate' });
    strict_1.default.equal((0, cacheStrategy_1.chooseStrategy)(req, ORIGIN), 'navigation-fallback');
});
test('chooseStrategy: GET /api/* → stale-while-revalidate', () => {
    const req = makeRequest({ url: `${ORIGIN}/api/runs` });
    strict_1.default.equal((0, cacheStrategy_1.chooseStrategy)(req, ORIGIN), 'stale-while-revalidate');
});
test('chooseStrategy: GET app-shell asset → cache-first', () => {
    const req = makeRequest({ url: `${ORIGIN}/assets/main-abc.js` });
    strict_1.default.equal((0, cacheStrategy_1.chooseStrategy)(req, ORIGIN), 'cache-first');
});
test('chooseStrategy: non-GET, cross-origin, and WS upgrade → bypass', () => {
    strict_1.default.equal((0, cacheStrategy_1.chooseStrategy)(makeRequest({ url: `${ORIGIN}/api/runs`, method: 'POST' }), ORIGIN), 'bypass');
    strict_1.default.equal((0, cacheStrategy_1.chooseStrategy)(makeRequest({ url: 'https://other.example/x.png' }), ORIGIN), 'bypass');
    strict_1.default.equal((0, cacheStrategy_1.chooseStrategy)(makeRequest({
        url: `${ORIGIN}/ws`,
        headers: { get: (k) => (k === 'upgrade' ? 'websocket' : null) },
    }), ORIGIN), 'bypass');
});
test('selectStaleCaches drops only sibling versions, never current or unrelated names', () => {
    const stale = (0, cacheStrategy_1.selectStaleCaches)([
        'ds-agent-mobile-v0',
        'ds-agent-mobile-v1',
        'ds-agent-mobile-experimental',
        'unrelated-cache',
    ], 'ds-agent-mobile-v1');
    strict_1.default.deepEqual(stale.sort(), [
        'ds-agent-mobile-experimental',
        'ds-agent-mobile-v0',
    ]);
});
let passed = 0;
let failed = 0;
for (const current of tests) {
    try {
        current.fn();
        console.log(`  ok  ${current.name}`);
        passed += 1;
    }
    catch (error) {
        console.error(`  FAIL ${current.name}`);
        console.error(`    ${error.message}`);
        failed += 1;
    }
}
console.log(`\nmobileServiceWorker.spec - ${passed}/${passed + failed} passed${failed ? ` (${failed} failed)` : ''}`);
if (failed > 0)
    process.exit(1);
