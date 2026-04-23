import assert from 'node:assert/strict';

import {
  arrayBufferToBase64Url,
  base64UrlToUint8Array,
  detectPushPermissionState,
  getCurrentSubscription,
  subscribeToWebPush,
  subscriptionToPayload,
  unsubscribeFromWebPush,
  type MockPushManager,
  type MockPushSubscription,
  type PushCapableRegistration,
} from '../../src/mobile/push/pushAdapter';

interface TestCase {
  name: string;
  fn: () => void | Promise<void>;
}

const tests: TestCase[] = [];
function test(name: string, fn: () => void | Promise<void>): void {
  tests.push({ name, fn });
}

function makeBufferFromString(value: string): ArrayBuffer {
  const buf = new ArrayBuffer(value.length);
  const view = new Uint8Array(buf);
  for (let i = 0; i < value.length; i += 1) {
    view[i] = value.charCodeAt(i);
  }
  return buf;
}

function makeMockSubscription(overrides: Partial<{
  endpoint: string;
  p256dh: ArrayBuffer | null;
  auth: ArrayBuffer | null;
  unsubscribeResult: boolean;
}> = {}): MockPushSubscription {
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

function makeRegistration(
  manager: Partial<MockPushManager>,
): PushCapableRegistration {
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
  const encoded = arrayBufferToBase64Url(buf);
  const decoded = base64UrlToUint8Array(encoded);
  assert.equal(decoded.length, bytes.length);
  for (let i = 0; i < bytes.length; i += 1) {
    assert.equal(decoded[i], bytes[i]);
  }
});

test('base64UrlToUint8Array rejects empty input', () => {
  assert.throws(() => base64UrlToUint8Array(''), /empty/);
  assert.throws(() => base64UrlToUint8Array('   '), /empty/);
});

// 2. detectPushPermissionState
test('detectPushPermissionState returns unsupported when APIs missing', () => {
  assert.equal(detectPushPermissionState({}), 'unsupported');
  assert.equal(
    detectPushPermissionState({ Notification: { permission: 'granted' } }),
    'unsupported',
    'PushManager missing → unsupported',
  );
});

test('detectPushPermissionState returns the browser permission when supported', () => {
  const sample: { Notification: { permission: NotificationPermission }; PushManager: unknown } = {
    Notification: { permission: 'granted' },
    PushManager: function MockPushManager() { return undefined; },
  };
  assert.equal(detectPushPermissionState(sample), 'granted');
  sample.Notification.permission = 'denied';
  assert.equal(detectPushPermissionState(sample), 'denied');
  sample.Notification.permission = 'default';
  assert.equal(detectPushPermissionState(sample), 'default');
});

// 3. subscriptionToPayload
test('subscriptionToPayload extracts endpoint + base64url keys', () => {
  const payload = subscriptionToPayload(makeMockSubscription());
  assert.equal(payload.endpoint, 'https://push.example/abc');
  assert.ok(payload.p256dhKey.length > 0);
  assert.ok(payload.authKey.length > 0);
  // url-safe alphabet: no '+' or '/' or '='
  assert.equal(/[+/=]/.test(payload.p256dhKey), false);
  assert.equal(/[+/=]/.test(payload.authKey), false);
});

test('subscriptionToPayload throws when a key is missing', () => {
  assert.throws(
    () => subscriptionToPayload(makeMockSubscription({ auth: null })),
    /missing/,
  );
});

// 4. subscribeToWebPush
test('subscribeToWebPush forwards VAPID key as Uint8Array to pushManager', async () => {
  let receivedKey: Uint8Array | null = null;
  let userVisible: boolean | null = null;
  const registration = makeRegistration({
    subscribe: async ({ userVisibleOnly, applicationServerKey }) => {
      userVisible = userVisibleOnly;
      receivedKey = applicationServerKey;
      return makeMockSubscription();
    },
  });
  const payload = await subscribeToWebPush(
    registration,
    'BNbN3MyTpA-fakekey_with-urlsafe123',
  );
  assert.equal(userVisible, true);
  assert.ok(receivedKey, 'pushManager.subscribe must receive a key');
  assert.ok((receivedKey as Uint8Array).length > 0);
  assert.equal(payload.endpoint, 'https://push.example/abc');
});

// 5. getCurrentSubscription / unsubscribeFromWebPush
test('getCurrentSubscription returns null when none registered', async () => {
  const registration = makeRegistration({ getSubscription: async () => null });
  const result = await getCurrentSubscription(registration);
  assert.equal(result, null);
});

test('getCurrentSubscription serialises an active subscription', async () => {
  const registration = makeRegistration({
    getSubscription: async () => makeMockSubscription({ endpoint: 'https://x/y' }),
  });
  const result = await getCurrentSubscription(registration);
  assert.equal(result?.endpoint, 'https://x/y');
});

test('unsubscribeFromWebPush returns false when nothing to remove', async () => {
  const registration = makeRegistration({ getSubscription: async () => null });
  assert.equal(await unsubscribeFromWebPush(registration), false);
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
  const result = await unsubscribeFromWebPush(registration);
  assert.equal(unsubscribeCalled, true);
  assert.equal(result, true);
});

let passed = 0;
let failed = 0;

(async () => {
  for (const current of tests) {
    try {
      await current.fn();
      console.log(`  ok  ${current.name}`);
      passed += 1;
    } catch (error) {
      console.error(`  FAIL ${current.name}`);
      console.error(`    ${(error as Error).message}`);
      failed += 1;
    }
  }
  console.log(
    `\nmobilePushAdapter.spec - ${passed}/${passed + failed} passed${failed ? ` (${failed} failed)` : ''}`,
  );
  if (failed > 0) {
    process.exit(1);
  }
})();
