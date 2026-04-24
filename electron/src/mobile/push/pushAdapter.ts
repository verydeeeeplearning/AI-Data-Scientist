/**
 * Mobile web push adapter (Wave 4 PLAN_06b).
 *
 * Pure, testable functions over the browser PushManager surface.  This
 * module owns ZERO React state.  All side effects flow through the
 * `ServiceWorkerRegistration` argument so the unit tests can swap in a
 * mock without spinning up a service worker.
 *
 * The actual service worker lives under `electron/src/mobile/sw/` and is
 * owned by a separate agent — this module only knows how to talk to a
 * registration that already exists.
 */

import { createMobileError } from '../errors/mobileError';

export type PushPermissionState = 'granted' | 'denied' | 'default' | 'unsupported';

export interface PushSubscriptionPayload {
  readonly endpoint: string;
  readonly p256dhKey: string;
  readonly authKey: string;
}

export interface MockPushManager {
  subscribe: (options: {
    userVisibleOnly: boolean;
    applicationServerKey: Uint8Array;
  }) => Promise<MockPushSubscription>;
  getSubscription: () => Promise<MockPushSubscription | null>;
}

export interface MockPushSubscription {
  endpoint: string;
  getKey: (name: 'p256dh' | 'auth') => ArrayBuffer | null;
  unsubscribe: () => Promise<boolean>;
  toJSON?: () => unknown;
}

/**
 * Minimal shape of a `ServiceWorkerRegistration` we depend on. Defining
 * it locally keeps the contract spec free of `lib.dom.d.ts` quirks.
 */
export interface PushCapableRegistration {
  pushManager: MockPushManager;
}

/**
 * Detect the current permission state without prompting the user.
 *
 * Returns `'unsupported'` whenever the browser lacks `Notification`,
 * `PushManager`, or both. Mobile UIs use that to render a
 * "this device can't receive push" hint instead of an opt-in button.
 */
export function detectPushPermissionState(
  globalRef: {
    Notification?: { permission: NotificationPermission };
    PushManager?: unknown;
  },
): PushPermissionState {
  if (
    !globalRef.Notification
    || typeof globalRef.PushManager === 'undefined'
  ) {
    return 'unsupported';
  }
  const value = globalRef.Notification.permission;
  if (value === 'granted' || value === 'denied' || value === 'default') {
    return value;
  }
  return 'default';
}

/**
 * Convert a base64url-encoded VAPID public key into the `Uint8Array`
 * shape `PushManager.subscribe` requires. Padding is reapplied so the
 * decoder doesn't choke on the URL-safe variant.
 */
export function base64UrlToUint8Array(base64Url: string): Uint8Array {
  const trimmed = base64Url.trim();
  if (!trimmed) {
    throw createMobileError('push_vapid_public_key_empty', 'VAPID public key is empty');
  }
  const padding = '='.repeat((4 - (trimmed.length % 4)) % 4);
  const base64 = (trimmed + padding).replace(/-/g, '+').replace(/_/g, '/');
  let raw = '';
  try {
    raw = globalThis.atob(base64);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Invalid VAPID public key';
    throw createMobileError('push_invalid_public_key', message);
  }
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) {
    out[i] = raw.charCodeAt(i);
  }
  return out;
}

/**
 * ArrayBuffer → base64url string (no padding) — matches how the W3C Push
 * API exposes the `p256dh` and `auth` keys via `PushSubscription.getKey`.
 */
export function arrayBufferToBase64Url(buffer: ArrayBuffer | null): string {
  if (!buffer) {
    return '';
  }
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  const base64 = globalThis.btoa(binary);
  return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

/**
 * Translate a browser `PushSubscription` into the JSON shape the backend
 * stores. Throws if either P-256 key is missing — that means the browser
 * gave us a half-formed subscription and we should surface it loudly.
 */
export function subscriptionToPayload(
  subscription: MockPushSubscription,
): PushSubscriptionPayload {
  const p256dh = arrayBufferToBase64Url(subscription.getKey('p256dh'));
  const auth = arrayBufferToBase64Url(subscription.getKey('auth'));
  if (!p256dh || !auth) {
    throw createMobileError(
      'push_subscription_invalid',
      'PushSubscription is missing p256dh or auth key',
    );
  }
  return {
    endpoint: subscription.endpoint,
    p256dhKey: p256dh,
    authKey: auth,
  };
}

/**
 * Subscribe with a freshly-fetched VAPID public key.
 *
 * Pure relative to `registration` and the public-key string — easy to
 * test against a mock PushManager.
 */
export async function subscribeToWebPush(
  registration: PushCapableRegistration,
  vapidPublicKey: string,
): Promise<PushSubscriptionPayload> {
  const applicationServerKey = base64UrlToUint8Array(vapidPublicKey);
  let subscription: MockPushSubscription;
  try {
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to register subscription';
    throw createMobileError('push_register_failed', message);
  }
  return subscriptionToPayload(subscription);
}

/**
 * Unsubscribe the current registration. Returns `true` if a subscription
 * was actually present and the browser confirmed removal.
 */
export async function unsubscribeFromWebPush(
  registration: PushCapableRegistration,
): Promise<boolean> {
  let current: MockPushSubscription | null;
  try {
    current = await registration.pushManager.getSubscription();
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to load subscription';
    throw createMobileError('push_unregister_failed', message);
  }
  if (!current) {
    return false;
  }
  try {
    return await current.unsubscribe();
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to unregister subscription';
    throw createMobileError('push_unregister_failed', message);
  }
}

/**
 * Return the current subscription as the JSON payload, or `null` if the
 * device has never subscribed (or has been revoked).
 */
export async function getCurrentSubscription(
  registration: PushCapableRegistration,
): Promise<PushSubscriptionPayload | null> {
  let current: MockPushSubscription | null;
  try {
    current = await registration.pushManager.getSubscription();
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to load subscription';
    throw createMobileError('push_register_failed', message);
  }
  if (!current) {
    return null;
  }
  return subscriptionToPayload(current);
}
