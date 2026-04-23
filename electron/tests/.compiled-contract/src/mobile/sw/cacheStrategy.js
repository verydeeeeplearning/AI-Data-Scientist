"use strict";
/**
 * Pure cache-strategy decision helpers for the mobile PWA service worker.
 *
 * The actual service worker (`serviceWorker.ts`) wires these helpers to the
 * `fetch` event. Splitting them out keeps the SW global (`self`,
 * `clients`, `caches`) out of the hot-path logic, so unit tests can run in
 * Node without faking the entire Service Worker API surface.
 *
 * Strategy summary (see PLAN_06a):
 *   1. App-shell GETs (HTML/JS/CSS/manifest/icons) → cache-first.
 *   2. Same-origin GETs to `/api/` → stale-while-revalidate.
 *   3. Navigation requests → network with cached `index.html` fallback.
 *   4. Everything else (cross-origin, non-GET, WebSocket upgrade) → bypass.
 *
 * NOTE on WebSocket: the renderer reaches the backend through `ws://` (see
 * `src/renderer/hooks/useWebSocket.ts`). Service workers cannot intercept
 * the WS upgrade, so we deliberately do NOT cache live runtime events here.
 * The renderer/Zustand stores already persist last-known snapshots in
 * `localStorage`, which the cached `index.html` will rehydrate on offline
 * reload — that is the read-only "last-viewed" surface this lane delivers.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.APP_SHELL_URLS = exports.NAVIGATION_FALLBACK_URL = exports.MOBILE_CACHE_PREFIX = exports.MOBILE_CACHE_NAME = void 0;
exports.isSameOrigin = isSameOrigin;
exports.isApiRequest = isApiRequest;
exports.isNavigationRequest = isNavigationRequest;
exports.isAppShellRequest = isAppShellRequest;
exports.chooseStrategy = chooseStrategy;
exports.selectStaleCaches = selectStaleCaches;
exports.MOBILE_CACHE_NAME = 'ds-agent-mobile-v1';
exports.MOBILE_CACHE_PREFIX = 'ds-agent-mobile-';
exports.NAVIGATION_FALLBACK_URL = './index.html';
exports.APP_SHELL_URLS = [
    './',
    './index.html',
    './manifest.json',
];
/**
 * Same-origin if the request URL parses to the SW's own origin, OR is a
 * relative path the SW can serve from cache.
 */
function isSameOrigin(requestUrl, swOrigin) {
    try {
        const parsed = new URL(requestUrl, swOrigin);
        const swParsed = new URL(swOrigin);
        return parsed.origin === swParsed.origin;
    }
    catch {
        return false;
    }
}
/**
 * Treat any GET to `/api/...` (sync REST, server-sent snapshots, future
 * mobile read endpoints) as the API surface. `/ws` and `wss://` upgrades
 * are NOT considered API here — they are bypassed because SW cannot
 * intercept WebSocket traffic.
 */
function isApiRequest(requestUrl, swOrigin) {
    if (!isSameOrigin(requestUrl, swOrigin))
        return false;
    try {
        const parsed = new URL(requestUrl, swOrigin);
        return parsed.pathname.startsWith('/api/');
    }
    catch {
        return false;
    }
}
function isNavigationRequest(request) {
    if (request.mode === 'navigate')
        return true;
    if (request.destination === 'document')
        return true;
    const accept = request.headers?.get('accept') ?? '';
    return accept.includes('text/html');
}
function isAppShellRequest(requestUrl, swOrigin) {
    if (!isSameOrigin(requestUrl, swOrigin))
        return false;
    try {
        const parsed = new URL(requestUrl, swOrigin);
        const path = parsed.pathname;
        if (path === '/' || path.endsWith('/index.html'))
            return true;
        if (path.endsWith('/manifest.json'))
            return true;
        if (/\.(js|mjs|css|woff2?|ttf|svg|png|ico)$/.test(path))
            return true;
        return false;
    }
    catch {
        return false;
    }
}
/**
 * Single decision function used by the SW fetch listener. Pure: no DOM, no
 * fetch, no caches. Returning `'bypass'` means the SW must NOT call
 * `event.respondWith` — let the browser handle it normally.
 */
function chooseStrategy(request, swOrigin) {
    if (request.method !== 'GET')
        return 'bypass';
    // WebSocket upgrade requests are non-interceptable; fall through.
    const upgrade = request.headers?.get('upgrade');
    if (upgrade && upgrade.toLowerCase() === 'websocket')
        return 'bypass';
    if (isNavigationRequest(request))
        return 'navigation-fallback';
    if (isApiRequest(request.url, swOrigin))
        return 'stale-while-revalidate';
    if (isAppShellRequest(request.url, swOrigin))
        return 'cache-first';
    // Cross-origin or unknown: let the browser handle it. Caching it would
    // bloat the cache without any guarantee that the response is safe to
    // replay offline.
    return 'bypass';
}
/**
 * Returns the list of cache names that should be deleted on `activate`.
 * Anything matching the prefix but NOT the current name is stale.
 */
function selectStaleCaches(existingNames, currentName, prefix = exports.MOBILE_CACHE_PREFIX) {
    return existingNames.filter((name) => name.startsWith(prefix) && name !== currentName);
}
