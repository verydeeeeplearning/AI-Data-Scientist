"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const globalDropOverlay_1 = require("../../src/renderer/domain/workspace/globalDropOverlay");
function run() {
    // initial state
    {
        const state = (0, globalDropOverlay_1.createInitialDropOverlayState)();
        strict_1.default.deepEqual(state, { phase: 'idle', dragDepth: 0, lastError: null });
    }
    // drag enter increments depth and activates overlay
    {
        let state = (0, globalDropOverlay_1.createInitialDropOverlayState)();
        state = (0, globalDropOverlay_1.reduceDragEntered)(state);
        strict_1.default.equal(state.phase, 'active');
        strict_1.default.equal(state.dragDepth, 1);
    }
    // nested drag enter/leave keeps overlay active until depth returns to 0
    {
        let state = (0, globalDropOverlay_1.createInitialDropOverlayState)();
        state = (0, globalDropOverlay_1.reduceDragEntered)(state);
        state = (0, globalDropOverlay_1.reduceDragEntered)(state);
        state = (0, globalDropOverlay_1.reduceDragLeft)(state);
        strict_1.default.equal(state.phase, 'active');
        strict_1.default.equal(state.dragDepth, 1);
        state = (0, globalDropOverlay_1.reduceDragLeft)(state);
        strict_1.default.equal(state.phase, 'idle');
        strict_1.default.equal(state.dragDepth, 0);
    }
    // drag leave from idle does not go below zero
    {
        let state = (0, globalDropOverlay_1.createInitialDropOverlayState)();
        state = (0, globalDropOverlay_1.reduceDragLeft)(state);
        strict_1.default.equal(state.dragDepth, 0);
        strict_1.default.equal(state.phase, 'idle');
    }
    // drop completes immediately and clears prior errors
    {
        let state = {
            phase: 'active',
            dragDepth: 2,
            lastError: { kind: 'network', message: 'old' },
        };
        state = (0, globalDropOverlay_1.reduceDropCompleted)(state);
        strict_1.default.equal(state.phase, 'uploading');
        strict_1.default.equal(state.dragDepth, 0);
        strict_1.default.equal(state.lastError, null);
    }
    // success transitions to idle
    {
        let state = { phase: 'uploading', dragDepth: 0, lastError: null };
        state = (0, globalDropOverlay_1.reduceUploadSucceeded)(state);
        strict_1.default.equal(state.phase, 'idle');
        strict_1.default.equal(state.lastError, null);
    }
    // failure stores classified error
    {
        let state = { phase: 'uploading', dragDepth: 0, lastError: null };
        state = (0, globalDropOverlay_1.reduceUploadFailed)(state, { kind: 'network', message: 'fetch failed' });
        strict_1.default.equal(state.phase, 'idle');
        strict_1.default.equal(state.lastError?.kind, 'network');
        strict_1.default.equal(state.lastError?.message, 'fetch failed');
    }
    // isDataTransferFileLike: types contains "Files"
    {
        strict_1.default.equal((0, globalDropOverlay_1.isDataTransferFileLike)({ types: ['Files'] }), true);
        strict_1.default.equal((0, globalDropOverlay_1.isDataTransferFileLike)({ types: ['text/plain'] }), false);
        strict_1.default.equal((0, globalDropOverlay_1.isDataTransferFileLike)({ types: [] }), false);
        strict_1.default.equal((0, globalDropOverlay_1.isDataTransferFileLike)(null), false);
        strict_1.default.equal((0, globalDropOverlay_1.isDataTransferFileLike)(undefined), false);
        strict_1.default.equal((0, globalDropOverlay_1.isDataTransferFileLike)({}), false);
    }
    // isDataTransferFileLike: items API path
    {
        strict_1.default.equal((0, globalDropOverlay_1.isDataTransferFileLike)({
            types: [],
            items: [{ kind: 'file', type: 'text/csv' }],
        }), true);
        strict_1.default.equal((0, globalDropOverlay_1.isDataTransferFileLike)({
            types: ['text/uri-list'],
            items: [{ kind: 'string', type: 'text/plain' }],
        }), false);
    }
}
run();
console.log('globalDropOverlay contract — OK');
