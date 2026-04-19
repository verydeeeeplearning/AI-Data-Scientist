import assert from 'node:assert/strict';

import {
  prefersReducedMotion,
  subscribeReducedMotion,
  type MediaQueryProvider,
} from '../../src/renderer/application/a11y/reducedMotion';

class FakeMediaQueryList {
  matches: boolean;
  media: string;
  private listeners: Array<(e: { matches: boolean }) => void> = [];
  constructor(matches: boolean, media: string) {
    this.matches = matches;
    this.media = media;
  }
  addEventListener(_type: 'change', cb: (e: { matches: boolean }) => void): void {
    this.listeners.push(cb);
  }
  removeEventListener(_type: 'change', cb: (e: { matches: boolean }) => void): void {
    this.listeners = this.listeners.filter((fn) => fn !== cb);
  }
  triggerChange(matches: boolean): void {
    this.matches = matches;
    for (const cb of this.listeners) cb({ matches });
  }
}

function makeProvider(initial: boolean): { provider: MediaQueryProvider; mql: FakeMediaQueryList } {
  const mql = new FakeMediaQueryList(initial, '(prefers-reduced-motion: reduce)');
  const provider: MediaQueryProvider = {
    matchMedia(query: string) {
      return new FakeMediaQueryList(initial, query) as unknown as MediaQueryList;
    },
  };
  // Use a stable mql instance that we control:
  provider.matchMedia = (query: string) => {
    mql.media = query;
    return mql as unknown as MediaQueryList;
  };
  return { provider, mql };
}

function run(): void {
  // === prefersReducedMotion: returns true when matchMedia matches ===
  {
    const { provider } = makeProvider(true);
    assert.equal(prefersReducedMotion({ provider }), true);
  }

  // === prefersReducedMotion: returns false when matchMedia does not match ===
  {
    const { provider } = makeProvider(false);
    assert.equal(prefersReducedMotion({ provider }), false);
  }

  // === prefersReducedMotion: missing matchMedia returns false (graceful) ===
  {
    const provider: MediaQueryProvider = { matchMedia: undefined };
    assert.equal(prefersReducedMotion({ provider }), false);
  }

  // === subscribeReducedMotion fires callback on change ===
  {
    const { provider, mql } = makeProvider(false);
    const events: boolean[] = [];
    const unsubscribe = subscribeReducedMotion((v: boolean) => events.push(v), { provider });
    mql.triggerChange(true);
    mql.triggerChange(false);
    assert.deepEqual(events, [true, false]);
    unsubscribe();
  }

  // === subscribeReducedMotion: unsubscribe stops further callbacks ===
  {
    const { provider, mql } = makeProvider(false);
    const events: boolean[] = [];
    const unsubscribe = subscribeReducedMotion((v: boolean) => events.push(v), { provider });
    mql.triggerChange(true);
    unsubscribe();
    mql.triggerChange(false);
    assert.deepEqual(events, [true]);
  }

  // === subscribeReducedMotion: missing provider returns no-op unsubscribe ===
  {
    const provider: MediaQueryProvider = { matchMedia: undefined };
    const events: boolean[] = [];
    const unsubscribe = subscribeReducedMotion((v: boolean) => events.push(v), { provider });
    unsubscribe();
    assert.deepEqual(events, []);
  }

  // === subscribeReducedMotion: emits initial value if requested ===
  {
    const { provider } = makeProvider(true);
    const events: boolean[] = [];
    const unsubscribe = subscribeReducedMotion((v) => events.push(v), {
      provider,
      emitInitial: true,
    });
    assert.deepEqual(events, [true]);
    unsubscribe();
  }

  console.log('[contract] PASS reduced-motion (7 cases)');
}

run();
