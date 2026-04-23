"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const pushAdapter_1 = require("../../src/mobile/push/pushAdapter");
const tests = [];
function test(name, fn) {
    tests.push({ name, fn });
}
function makeBufferFromString(value) {
    const buf = new ArrayBuffer(value.length);
    const view = new Uint8Array(buf);
    for (let i = 0; i < value.length; i += 1) {
        view[i] = value.charCodeAt(i);
    }
    return buf;
}
function makeMockSubscription(overrides = {}) {
    const endpoint = overrides.endpoint ?? 'https://push.example/abc';
    const p256dh = overrides.p256dh === undefined
        ? makeBufferFromString('p256dh-key-bytes')
        : overrides.p256dh;
    const auth = overrides.auth === undefined
        ? makeBufferFromString('auth-bytes')
        : overrides.auth;
    return {
        endpoint,
        getKey: (name) => (name === 'p256dh' ? p256dh : auth),
        unsubscribe: async () => overrides.unsubscribeResult ?? true,
    };
}
function makeRegistration(manager) {
    return {
        pushManager: {
            subscribe: manager.subscribe ?? (async () => makeMockSubscription()),
            getSubscription: manager.getSubscription ?? (async () => null),
        },
    };
}
// 1. base64url ↔ Uint8Array round trip
test('base64url decode/encode round-trip preserves bytes', () => {
    // Use a known-good aligned VAPID-style key (65-byte EC point P-256
    // uncompressed: 1 + 32 + 32). Encoded length 88 chars / 86 unpadded.
    // Construct from a deterministic byte pattern then round-trip.
    const bytes = new Uint8Array(65);
    for (let i = 0; i < bytes.length; i += 1) {
        bytes[i] = (i * 7 + 3) & 0xff;
    }
    const buf = new ArrayBuffer(bytes.length);
    new Uint8Array(buf).set(bytes);
    const encoded = (0, pushAdapter_1.arrayBufferToBase64Url)(buf);
    const decoded = (0, pushAdapter_1.base64UrlToUint8Array)(encoded);
    strict_1.default.equal(decoded.length, bytes.length);
    for (let i = 0; i < bytes.length; i += 1) {
        strict_1.default.equal(decoded[i], bytes[i]);
    }
});
test('base64UrlToUint8Array rejects empty input', () => {
    strict_1.default.throws(() => (0, pushAdapter_1.base64UrlToUint8Array)(''), /empty/);
    strict_1.default.throws(() => (0, pushAdapter_1.base64UrlToUint8Array)('   '), /empty/);
});
// 2. detectPushPermissionState
test('detectPushPermissionState returns unsupported when APIs missing', () => {
    strict_1.default.equal((0, pushAdapter_1.detectPushPermissionState)({}), 'unsupported');
    strict_1.default.equal((0, pushAdapter_1.detectPushPermissionState)({ Notification: { permission: 'granted' } }), 'unsupported', 'PushManager missing → unsupported');
});
test('detectPushPermissionState returns the browser permission when supported', () => {
    const sample = {
        Notification: { permission: 'granted' },
        PushManager: function MockPushManager() { return undefined; },
    };
    strict_1.default.equal((0, pushAdapter_1.detectPushPermissionState)(sample), 'granted');
    sample.Notification.permission = 'denied';
    strict_1.default.equal((0, pushAdapter_1.detectPushPermissionState)(sample), 'denied');
    sample.Notification.permission = 'default';
    strict_1.default.equal((0, pushAdapter_1.detectPushPermissionState)(sample), 'default');
});
// 3. subscriptionToPayload
test('subscriptionToPayload extracts endpoint + base64url keys', () => {
    const payload = (0, pushAdapter_1.subscriptionToPayload)(makeMockSubscription());
    strict_1.default.equal(payload.endpoint, 'https://push.example/abc');
    strict_1.default.ok(payload.p256dhKey.length > 0);
    strict_1.default.ok(payload.authKey.length > 0);
    // url-safe alphabet: no '+' or '/' or '='
    strict_1.default.equal(/[+/=]/.test(payload.p256dhKey), false);
    strict_1.default.equal(/[+/=]/.test(payload.authKey), false);
});
test('subscriptionToPayload throws when a key is missing', () => {
    strict_1.default.throws(() => (0, pushAdapter_1.subscriptionToPayload)(makeMockSubscription({ auth: null })), /missing/);
});
// 4. subscribeToWebPush
test('subscribeToWebPush forwards VAPID key as Uint8Array to pushManager', async () => {
    let receivedKey = null;
    let userVisible = null;
    const registration = makeRegistration({
        subscribe: async ({ userVisibleOnly, applicationServerKey }) => {
            userVisible = userVisibleOnly;
            receivedKey = applicationServerKey;
            return makeMockSubscription();
        },
    });
    const payload = await (0, pushAdapter_1.subscribeToWebPush)(registration, 'BNbN3MyTpA-fakekey_with-urlsafe123');
    strict_1.default.equal(userVisible, true);
    strict_1.default.ok(receivedKey, 'pushManager.subscribe must receive a key');
    strict_1.default.ok(receivedKey.length > 0);
    strict_1.default.equal(payload.endpoint, 'https://push.example/abc');
});
// 5. getCurrentSubscription / unsubscribeFromWebPush
test('getCurrentSubscription returns null when none registered', async () => {
    const registration = makeRegistration({ getSubscription: async () => null });
    const result = await (0, pushAdapter_1.getCurrentSubscription)(registration);
    strict_1.default.equal(result, null);
});
test('getCurrentSubscription serialises an active subscription', async () => {
    const registration = makeRegistration({
        getSubscription: async () => makeMockSubscription({ endpoint: 'https://x/y' }),
    });
    const result = await (0, pushAdapter_1.getCurrentSubscription)(registration);
    strict_1.default.equal(result?.endpoint, 'https://x/y');
});
test('unsubscribeFromWebPush returns false when nothing to remove', async () => {
    const registration = makeRegistration({ getSubscription: async () => null });
    strict_1.default.equal(await (0, pushAdapter_1.unsubscribeFromWebPush)(registration), false);
});
test('unsubscribeFromWebPush invokes browser unsubscribe and returns its result', async () => {
    let unsubscribeCalled = false;
    const registration = makeRegistration({
        getSubscription: async () => ({
            ...makeMockSubscription(),
            unsubscribe: async () => {
                unsubscribeCalled = true;
                return true;
            },
        }),
    });
    const result = await (0, pushAdapter_1.unsubscribeFromWebPush)(registration);
    strict_1.default.equal(unsubscribeCalled, true);
    strict_1.default.equal(result, true);
});
let passed = 0;
let failed = 0;
(async () => {
    for (const current of tests) {
        try {
            await current.fn();
            console.log(`  ok  ${current.name}`);
            passed += 1;
        }
        catch (error) {
            console.error(`  FAIL ${current.name}`);
            console.error(`    ${error.message}`);
            failed += 1;
        }
    }
    console.log(`\nmobilePushAdapter.spec - ${passed}/${passed + failed} passed${failed ? ` (${failed} failed)` : ''}`);
    if (failed > 0) {
        process.exit(1);
    }
})();
