import assert from 'node:assert/strict';

import {
  createInitialDropOverlayState,
  reduceDragEntered,
  reduceDragLeft,
  reduceDropCompleted,
  reduceUploadFailed,
  reduceUploadSucceeded,
  isDataTransferFileLike,
  type DropOverlayState,
} from '../../src/renderer/domain/workspace/globalDropOverlay';

function run(): void {
  // initial state
  {
    const state = createInitialDropOverlayState();
    assert.deepEqual(state, { phase: 'idle', dragDepth: 0, lastError: null });
  }

  // drag enter increments depth and activates overlay
  {
    let state = createInitialDropOverlayState();
    state = reduceDragEntered(state);
    assert.equal(state.phase, 'active');
    assert.equal(state.dragDepth, 1);
  }

  // nested drag enter/leave keeps overlay active until depth returns to 0
  {
    let state = createInitialDropOverlayState();
    state = reduceDragEntered(state);
    state = reduceDragEntered(state);
    state = reduceDragLeft(state);
    assert.equal(state.phase, 'active');
    assert.equal(state.dragDepth, 1);
    state = reduceDragLeft(state);
    assert.equal(state.phase, 'idle');
    assert.equal(state.dragDepth, 0);
  }

  // drag leave from idle does not go below zero
  {
    let state = createInitialDropOverlayState();
    state = reduceDragLeft(state);
    assert.equal(state.dragDepth, 0);
    assert.equal(state.phase, 'idle');
  }

  // drop completes immediately and clears prior errors
  {
    let state: DropOverlayState = {
      phase: 'active',
      dragDepth: 2,
      lastError: { kind: 'network', message: 'old' },
    };
    state = reduceDropCompleted(state);
    assert.equal(state.phase, 'uploading');
    assert.equal(state.dragDepth, 0);
    assert.equal(state.lastError, null);
  }

  // success transitions to idle
  {
    let state: DropOverlayState = { phase: 'uploading', dragDepth: 0, lastError: null };
    state = reduceUploadSucceeded(state);
    assert.equal(state.phase, 'idle');
    assert.equal(state.lastError, null);
  }

  // failure stores classified error
  {
    let state: DropOverlayState = { phase: 'uploading', dragDepth: 0, lastError: null };
    state = reduceUploadFailed(state, { kind: 'network', message: 'fetch failed' });
    assert.equal(state.phase, 'idle');
    assert.equal(state.lastError?.kind, 'network');
    assert.equal(state.lastError?.message, 'fetch failed');
  }

  // isDataTransferFileLike: types contains "Files"
  {
    assert.equal(isDataTransferFileLike({ types: ['Files'] }), true);
    assert.equal(isDataTransferFileLike({ types: ['text/plain'] }), false);
    assert.equal(isDataTransferFileLike({ types: [] }), false);
    assert.equal(isDataTransferFileLike(null), false);
    assert.equal(isDataTransferFileLike(undefined), false);
    assert.equal(isDataTransferFileLike({}), false);
  }

  // isDataTransferFileLike: items API path
  {
    assert.equal(
      isDataTransferFileLike({
        types: [],
        items: [{ kind: 'file', type: 'text/csv' }],
      }),
      true,
    );
    assert.equal(
      isDataTransferFileLike({
        types: ['text/uri-list'],
        items: [{ kind: 'string', type: 'text/plain' }],
      }),
      false,
    );
  }
}

run();
console.log('globalDropOverlay contract — OK');
