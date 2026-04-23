import assert from 'node:assert/strict';

import {
  NEW_EXECUTION_TIMELINE_FLAG_STORAGE_KEY,
  loadNewExecutionTimelineEnabled,
  parseNewExecutionTimelineEnabled,
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
  assert.equal(parseNewExecutionTimelineEnabled(null), true, 'default to ON when unset');
  assert.equal(parseNewExecutionTimelineEnabled('true'), true);
  assert.equal(parseNewExecutionTimelineEnabled('TRUE'), true);
  assert.equal(parseNewExecutionTimelineEnabled('false'), false);
  assert.equal(parseNewExecutionTimelineEnabled('0'), false);
  assert.equal(parseNewExecutionTimelineEnabled('off'), false);
  assert.equal(parseNewExecutionTimelineEnabled('whatever'), true, 'unknown value falls back to ON');

  const storageHost = globalThis as { localStorage?: StorageLike };
  const previousLocalStorage = storageHost.localStorage;
  const storage = new MemoryStorage();
  storageHost.localStorage = storage;

  try {
    assert.equal(loadNewExecutionTimelineEnabled(), true, 'fresh storage defaults to ON');

    storage.setItem(NEW_EXECUTION_TIMELINE_FLAG_STORAGE_KEY, 'false');
    assert.equal(loadNewExecutionTimelineEnabled(), false, 'rollback path: explicit false');

    storage.setItem(NEW_EXECUTION_TIMELINE_FLAG_STORAGE_KEY, 'true');
    assert.equal(loadNewExecutionTimelineEnabled(), true, 're-enable after rollback');
  } finally {
    if (previousLocalStorage === undefined) {
      delete storageHost.localStorage;
    } else {
      storageHost.localStorage = previousLocalStorage;
    }
  }

  console.log('[contract] PASS execution-timeline-feature-flag (10 cases)');
}

run();
