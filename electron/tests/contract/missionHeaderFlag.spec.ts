import assert from 'node:assert/strict';

import {
  MISSION_HEADER_FLAG_STORAGE_KEY,
  loadMissionHeaderEnabled,
  parseMissionHeaderEnabled,
} from '../../src/renderer/stores/configStore';

interface StorageLike {
  length: number;
  clear: () => void;
  getItem: (key: string) => string | null;
  key: (index: number) => string | null;
  removeItem: (key: string) => void;
  setItem: (key: string, value: string) => void;
}

class MemoryStorage implements StorageLike {
  private readonly store = new Map<string, string>();

  get length(): number {
    return this.store.size;
  }

  clear(): void {
    this.store.clear();
  }

  getItem(key: string): string | null {
    return this.store.has(key) ? this.store.get(key) ?? null : null;
  }

  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null;
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }

  setItem(key: string, value: string): void {
    this.store.set(key, value);
  }
}

function run(): void {
  assert.equal(parseMissionHeaderEnabled(null), true);
  assert.equal(parseMissionHeaderEnabled('true'), true);
  assert.equal(parseMissionHeaderEnabled('false'), false);
  assert.equal(parseMissionHeaderEnabled('0'), false);
  assert.equal(parseMissionHeaderEnabled('off'), false);
  assert.equal(parseMissionHeaderEnabled('unexpected'), true);

  const storageHost = globalThis as { localStorage?: StorageLike };
  const previousLocalStorage = storageHost.localStorage;
  const storage = new MemoryStorage();
  storageHost.localStorage = storage;

  try {
    assert.equal(loadMissionHeaderEnabled(), true);

    storage.setItem(MISSION_HEADER_FLAG_STORAGE_KEY, 'false');
    assert.equal(loadMissionHeaderEnabled(), false);

    storage.setItem(MISSION_HEADER_FLAG_STORAGE_KEY, 'true');
    assert.equal(loadMissionHeaderEnabled(), true);
  } finally {
    if (previousLocalStorage === undefined) {
      delete storageHost.localStorage;
    } else {
      storageHost.localStorage = previousLocalStorage;
    }
  }

  console.log('[contract] PASS mission-header-flag (9 cases)');
}

run();
