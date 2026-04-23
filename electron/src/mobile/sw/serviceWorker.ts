/// <reference lib="webworker" />
/**
 * Mobile PWA service worker.
 *
 * Compiled to `dist/mobile/sw.js` at build root so the SW scope covers the
 * whole mobile surface. Decision logic lives in `./cacheStrategy.ts` so it
 * can be unit-tested in Node (the SW global APIs cannot).
 *
 * Strategy:
 *   - install   → precache app shell.
 *   - activate  → drop stale caches, claim clients.
 *   - fetch     → cache-first / stale-while-revalidate / nav-fallback /
 *                 bypass per `chooseStrategy`.
 *   - push      → surface an encrypted Web Push payload immediately.
 *   - sync      → ask open clients to flush queued approval submissions.
 *
 * What this SW intentionally does NOT do:
 *   - WebSocket interception (browsers do not allow it).
 */

import {
  APP_SHELL_URLS,
  MOBILE_CACHE_NAME,
  NAVIGATION_FALLBACK_URL,
  chooseStrategy,
  selectStaleCaches,
} from './cacheStrategy';
import { OUTBOX_SYNC_TAG } from '../outbox/indexedDbOutbox';
import {
  normalizePushNotification,
  resolveNotificationClickTarget,
} from './pushPayload';

declare const self: ServiceWorkerGlobalScope;

self.addEventListener('install', (event: ExtendableEvent) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(MOBILE_CACHE_NAME);
      // Use { cache: 'reload' } so the install fetch bypasses the HTTP
      // cache and we always store the freshly-built shell.
      await Promise.all(
        APP_SHELL_URLS.map((url) =>
          cache.add(new Request(url, { cache: 'reload' })).catch(() => {
            // Ignore individual asset failures — the shell still installs.
          }),
        ),
      );
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener('activate', (event: ExtendableEvent) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      const stale = selectStaleCaches(names, MOBILE_CACHE_NAME);
      await Promise.all(stale.map((name) => caches.delete(name)));
      await self.clients.claim();
    })(),
  );
});

self.addEventListener('fetch', (event: FetchEvent) => {
  const request = event.request;
  const strategy = chooseStrategy(
    {
      method: request.method,
      url: request.url,
      mode: request.mode,
      destination: request.destination,
      headers: request.headers,
    },
    self.location.origin,
  );

  if (strategy === 'bypass') return;

  event.respondWith(handle(strategy, request));
});

self.addEventListener('push', (event: PushEvent) => {
  event.waitUntil(handlePush(event));
});

self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.waitUntil(handleNotificationClick(event));
});

self.addEventListener('sync', (event: SyncEvent) => {
  if (event.tag !== OUTBOX_SYNC_TAG) {
    return;
  }
  event.waitUntil(notifyClientsToFlushOutbox());
});

async function handle(strategy: string, request: Request): Promise<Response> {
  const cache = await caches.open(MOBILE_CACHE_NAME);

  if (strategy === 'cache-first') {
    const cached = await cache.match(request);
    if (cached) return cached;
    try {
      const fresh = await fetch(request);
      if (fresh.ok) cache.put(request, fresh.clone()).catch(() => undefined);
      return fresh;
    } catch (err) {
      // Last resort for app-shell assets when offline.
      const fallback = await cache.match(NAVIGATION_FALLBACK_URL);
      if (fallback) return fallback;
      throw err;
    }
  }

  if (strategy === 'stale-while-revalidate') {
    const cached = await cache.match(request);
    const network = fetch(request)
      .then((response) => {
        if (response.ok) cache.put(request, response.clone()).catch(() => undefined);
        return response;
      })
      .catch(() => undefined);
    if (cached) {
      // Don't await network; serve cached immediately.
      void network;
      return cached;
    }
    const fresh = await network;
    if (fresh) return fresh;
    return new Response(JSON.stringify({ error: 'offline' }), {
      status: 503,
      headers: { 'content-type': 'application/json' },
    });
  }

  if (strategy === 'navigation-fallback') {
    try {
      const fresh = await fetch(request);
      return fresh;
    } catch {
      const cached =
        (await cache.match(NAVIGATION_FALLBACK_URL)) ??
        (await cache.match('./'));
      if (cached) return cached;
      return new Response('Offline', { status: 503 });
    }
  }

  // Defensive default — should be unreachable because 'bypass' returned earlier.
  return fetch(request);
}

async function handlePush(event: PushEvent): Promise<void> {
  let rawPayload: unknown = null;
  if (event.data) {
    try {
      rawPayload = event.data.json();
    } catch {
      try {
        rawPayload = { body: event.data.text() };
      } catch {
        rawPayload = null;
      }
    }
  }

  const notification = normalizePushNotification(rawPayload);
  await self.registration.showNotification(notification.title, {
    body: notification.body,
    tag: notification.tag,
    data: { deepLink: notification.deepLink },
  });
}

async function handleNotificationClick(event: NotificationEvent): Promise<void> {
  event.notification.close();
  const target = resolveNotificationClickTarget(event.notification.data, './');
  const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
  if (target === './' && clients.length > 0) {
    await clients[0].focus();
    return;
  }
  await self.clients.openWindow(target);
}

async function notifyClientsToFlushOutbox(): Promise<void> {
  const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
  for (const client of clients) {
    client.postMessage({ type: 'ds-agent-outbox-flush' });
  }
}

export {};
