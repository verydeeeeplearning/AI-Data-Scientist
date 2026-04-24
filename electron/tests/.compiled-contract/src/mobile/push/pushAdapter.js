"use strict";
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
Object.defineProperty(exports, "__esModule", { value: true });
exports.detectPushPermissionState = detectPushPermissionState;
exports.base64UrlToUint8Array = base64UrlToUint8Array;
exports.arrayBufferToBase64Url = arrayBufferToBase64Url;
exports.subscriptionToPayload = subscriptionToPayload;
exports.subscribeToWebPush = subscribeToWebPush;
exports.unsubscribeFromWebPush = unsubscribeFromWebPush;
exports.getCurrentSubscription = getCurrentSubscription;
const mobileError_1 = require("../errors/mobileError");
/**
 * Detect the current permission state without prompting the user.
 *
 * Returns `'unsupported'` whenever the browser lacks `Notification`,
 * `PushManager`, or both. Mobile UIs use that to render a
 * "this device can't receive push" hint instead of an opt-in button.
 */
function detectPushPermissionState(globalRef) {
    if (!globalRef.Notification
        || typeof globalRef.PushManager === 'undefined') {
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
function base64UrlToUint8Array(base64Url) {
    const trimmed = base64Url.trim();
    if (!trimmed) {
        throw (0, mobileError_1.createMobileError)('push_vapid_public_key_empty', 'VAPID public key is empty');
    }
    const padding = '='.repeat((4 - (trimmed.length % 4)) % 4);
    const base64 = (trimmed + padding).replace(/-/g, '+').replace(/_/g, '/');
    let raw = '';
    try {
        raw = globalThis.atob(base64);
    }
    catch (error) {
        const message = error instanceof Error ? error.message : 'Invalid VAPID public key';
        throw (0, mobileError_1.createMobileError)('push_invalid_public_key', message);
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
function arrayBufferToBase64Url(buffer) {
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
function subscriptionToPayload(subscription) {
    const p256dh = arrayBufferToBase64Url(subscription.getKey('p256dh'));
    const auth = arrayBufferToBase64Url(subscription.getKey('auth'));
    if (!p256dh || !auth) {
        throw (0, mobileError_1.createMobileError)('push_subscription_invalid', 'PushSubscription is missing p256dh or auth key');
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
async function subscribeToWebPush(registration, vapidPublicKey) {
    const applicationServerKey = base64UrlToUint8Array(vapidPublicKey);
    let subscription;
    try {
        subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey,
        });
    }
    catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to register subscription';
        throw (0, mobileError_1.createMobileError)('push_register_failed', message);
    }
    return subscriptionToPayload(subscription);
}
/**
 * Unsubscribe the current registration. Returns `true` if a subscription
 * was actually present and the browser confirmed removal.
 */
async function unsubscribeFromWebPush(registration) {
    let current;
    try {
        current = await registration.pushManager.getSubscription();
    }
    catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to load subscription';
        throw (0, mobileError_1.createMobileError)('push_unregister_failed', message);
    }
    if (!current) {
        return false;
    }
    try {
        return await current.unsubscribe();
    }
    catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to unregister subscription';
        throw (0, mobileError_1.createMobileError)('push_unregister_failed', message);
    }
}
/**
 * Return the current subscription as the JSON payload, or `null` if the
 * device has never subscribed (or has been revoked).
 */
async function getCurrentSubscription(registration) {
    let current;
    try {
        current = await registration.pushManager.getSubscription();
    }
    catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to load subscription';
        throw (0, mobileError_1.createMobileError)('push_register_failed', message);
    }
    if (!current) {
        return null;
    }
    return subscriptionToPayload(current);
}
