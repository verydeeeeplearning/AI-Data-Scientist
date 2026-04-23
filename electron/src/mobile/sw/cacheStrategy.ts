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

export const MOBILE_CACHE_NAME = 'ds-agent-mobile-v1';
export const MOBILE_CACHE_PREFIX = 'ds-agent-mobile-';
export const NAVIGATION_FALLBACK_URL = './index.html';

export const APP_SHELL_URLS: readonly string[] = [
  './',
  './index.html',
  './manifest.json',
];

export type CacheStrategy =
  | 'cache-first'
  | 'stale-while-revalidate'
  | 'navigation-fallback'
  | 'bypass';

export interface RequestLike {
  readonly method: string;
  readonly url: string;
  readonly mode?: string;
  readonly destination?: string;
  readonly headers?: { get(name: string): string | null } | undefined;
}

/**
 * Same-origin if the request URL parses to the SW's own origin, OR is a
 * relative path the SW can serve from cache.
 */
export function isSameOrigin(requestUrl: string, swOrigin: string): boolean {
  try {
    const parsed = new URL(requestUrl, swOrigin);
    const swParsed = new URL(swOrigin);
    return parsed.origin === swParsed.origin;
  } catch {
    return false;
  }
}

/**
 * Treat any GET to `/api/...` (sync REST, server-sent snapshots, future
 * mobile read endpoints) as the API surface. `/ws` and `wss://` upgrades
 * are NOT considered API here — they are bypassed because SW cannot
 * intercept WebSocket traffic.
 */
export function isApiRequest(requestUrl: string, swOrigin: string): boolean {
  if (!isSameOrigin(requestUrl, swOrigin)) return false;
  try {
    const parsed = new URL(requestUrl, swOrigin);
    return parsed.pathname.startsWith('/api/');
  } catch {
    return false;
  }
}

export function isNavigationRequest(request: RequestLike): boolean {
  if (request.mode === 'navigate') return true;
  if (request.destination === 'document') return true;
  const accept = request.headers?.get('accept') ?? '';
  return accept.includes('text/html');
}

export function isAppShellRequest(requestUrl: string, swOrigin: string): boolean {
  if (!isSameOrigin(requestUrl, swOrigin)) return false;
  try {
    const parsed = new URL(requestUrl, swOrigin);
    const path = parsed.pathname;
    if (path === '/' || path.endsWith('/index.html')) return true;
    if (path.endsWith('/manifest.json')) return true;
    if (/\.(js|mjs|css|woff2?|ttf|svg|png|ico)$/.test(path)) return true;
    return false;
  } catch {
    return false;
  }
}

/**
 * Single decision function used by the SW fetch listener. Pure: no DOM, no
 * fetch, no caches. Returning `'bypass'` means the SW must NOT call
 * `event.respondWith` — let the browser handle it normally.
 */
export function chooseStrategy(
  request: RequestLike,
  swOrigin: string,
): CacheStrategy {
  if (request.method !== 'GET') return 'bypass';

  // WebSocket upgrade requests are non-interceptable; fall through.
  const upgrade = request.headers?.get('upgrade');
  if (upgrade && upgrade.toLowerCase() === 'websocket') return 'bypass';

  if (isNavigationRequest(request)) return 'navigation-fallback';
  if (isApiRequest(request.url, swOrigin)) return 'stale-while-revalidate';
  if (isAppShellRequest(request.url, swOrigin)) return 'cache-first';

  // Cross-origin or unknown: let the browser handle it. Caching it would
  // bloat the cache without any guarantee that the response is safe to
  // replay offline.
  return 'bypass';
}

/**
 * Returns the list of cache names that should be deleted on `activate`.
 * Anything matching the prefix but NOT the current name is stale.
 */
export function selectStaleCaches(
  existingNames: readonly string[],
  currentName: string,
  prefix: string = MOBILE_CACHE_PREFIX,
): string[] {
  return existingNames.filter(
    (name) => name.startsWith(prefix) && name !== currentName,
  );
}
