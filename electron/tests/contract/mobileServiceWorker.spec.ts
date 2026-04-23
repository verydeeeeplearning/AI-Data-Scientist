import assert from 'node:assert/strict';

import {
  MOBILE_CACHE_NAME,
  MOBILE_CACHE_PREFIX,
  chooseStrategy,
  isApiRequest,
  isAppShellRequest,
  isNavigationRequest,
  isSameOrigin,
  selectStaleCaches,
  type RequestLike,
} from '../../src/mobile/sw/cacheStrategy';

const ORIGIN = 'https://mobile.local';

function makeRequest(partial: Partial<RequestLike> & Pick<RequestLike, 'url'>): RequestLike {
  const headers = partial.headers ?? { get: () => null };
  return {
    method: 'GET',
    mode: undefined,
    destination: undefined,
    ...partial,
    headers,
  };
}

interface TestCase {
  name: string;
  fn: () => void;
}

const tests: TestCase[] = [];
function test(name: string, fn: () => void): void {
  tests.push({ name, fn });
}

test('cache name registry stays stable & versioned', () => {
  assert.equal(MOBILE_CACHE_NAME, 'ds-agent-mobile-v1');
  assert.ok(MOBILE_CACHE_NAME.startsWith(MOBILE_CACHE_PREFIX));
});

test('isSameOrigin handles absolute and relative URLs', () => {
  assert.equal(isSameOrigin(`${ORIGIN}/index.html`, ORIGIN), true);
  assert.equal(isSameOrigin('/api/runs', ORIGIN), true);
  assert.equal(isSameOrigin('https://other.example/x', ORIGIN), false);
  assert.equal(isSameOrigin('http://different.local:8080/', ORIGIN), false);
});

test('isApiRequest matches /api/ paths only', () => {
  assert.equal(isApiRequest(`${ORIGIN}/api/runs`, ORIGIN), true);
  assert.equal(isApiRequest(`${ORIGIN}/api/`, ORIGIN), true);
  assert.equal(isApiRequest(`${ORIGIN}/index.html`, ORIGIN), false);
  assert.equal(isApiRequest(`${ORIGIN}/manifest.json`, ORIGIN), false);
  assert.equal(isApiRequest('https://other.example/api/runs', ORIGIN), false);
});

test('isAppShellRequest covers shell assets and not API or cross-origin', () => {
  assert.equal(isAppShellRequest(`${ORIGIN}/`, ORIGIN), true);
  assert.equal(isAppShellRequest(`${ORIGIN}/index.html`, ORIGIN), true);
  assert.equal(isAppShellRequest(`${ORIGIN}/manifest.json`, ORIGIN), true);
  assert.equal(isAppShellRequest(`${ORIGIN}/assets/main-abc.js`, ORIGIN), true);
  assert.equal(isAppShellRequest(`${ORIGIN}/assets/main-abc.css`, ORIGIN), true);
  assert.equal(isAppShellRequest(`${ORIGIN}/icons/icon-192.png`, ORIGIN), true);
  assert.equal(isAppShellRequest(`${ORIGIN}/api/runs`, ORIGIN), false);
  assert.equal(isAppShellRequest('https://other.example/main.js', ORIGIN), false);
});

test('isNavigationRequest detects mode=navigate, document destination, accept html', () => {
  assert.equal(
    isNavigationRequest(makeRequest({ url: `${ORIGIN}/`, mode: 'navigate' })),
    true,
  );
  assert.equal(
    isNavigationRequest(
      makeRequest({ url: `${ORIGIN}/x`, destination: 'document' }),
    ),
    true,
  );
  assert.equal(
    isNavigationRequest(
      makeRequest({
        url: `${ORIGIN}/x`,
        headers: { get: (k) => (k === 'accept' ? 'text/html' : null) },
      }),
    ),
    true,
  );
  assert.equal(isNavigationRequest(makeRequest({ url: `${ORIGIN}/api/x` })), false);
});

test('chooseStrategy: GET navigation → navigation-fallback', () => {
  const req = makeRequest({ url: `${ORIGIN}/runs`, mode: 'navigate' });
  assert.equal(chooseStrategy(req, ORIGIN), 'navigation-fallback');
});

test('chooseStrategy: GET /api/* → stale-while-revalidate', () => {
  const req = makeRequest({ url: `${ORIGIN}/api/runs` });
  assert.equal(chooseStrategy(req, ORIGIN), 'stale-while-revalidate');
});

test('chooseStrategy: GET app-shell asset → cache-first', () => {
  const req = makeRequest({ url: `${ORIGIN}/assets/main-abc.js` });
  assert.equal(chooseStrategy(req, ORIGIN), 'cache-first');
});

test('chooseStrategy: non-GET, cross-origin, and WS upgrade → bypass', () => {
  assert.equal(
    chooseStrategy(
      makeRequest({ url: `${ORIGIN}/api/runs`, method: 'POST' }),
      ORIGIN,
    ),
    'bypass',
  );
  assert.equal(
    chooseStrategy(
      makeRequest({ url: 'https://other.example/x.png' }),
      ORIGIN,
    ),
    'bypass',
  );
  assert.equal(
    chooseStrategy(
      makeRequest({
        url: `${ORIGIN}/ws`,
        headers: { get: (k) => (k === 'upgrade' ? 'websocket' : null) },
      }),
      ORIGIN,
    ),
    'bypass',
  );
});

test('selectStaleCaches drops only sibling versions, never current or unrelated names', () => {
  const stale = selectStaleCaches(
    [
      'ds-agent-mobile-v0',
      'ds-agent-mobile-v1',
      'ds-agent-mobile-experimental',
      'unrelated-cache',
    ],
    'ds-agent-mobile-v1',
  );
  assert.deepEqual(stale.sort(), [
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
  } catch (error) {
    console.error(`  FAIL ${current.name}`);
    console.error(`    ${(error as Error).message}`);
    failed += 1;
  }
}

console.log(
  `\nmobileServiceWorker.spec - ${passed}/${passed + failed} passed${failed ? ` (${failed} failed)` : ''}`,
);

if (failed > 0) process.exit(1);
