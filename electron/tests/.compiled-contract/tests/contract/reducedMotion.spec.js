"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const reducedMotion_1 = require("../../src/renderer/application/a11y/reducedMotion");
class FakeMediaQueryList {
    constructor(matches, media) {
        this.listeners = [];
        this.matches = matches;
        this.media = media;
    }
    addEventListener(_type, cb) {
        this.listeners.push(cb);
    }
    removeEventListener(_type, cb) {
        this.listeners = this.listeners.filter((fn) => fn !== cb);
    }
    triggerChange(matches) {
        this.matches = matches;
        for (const cb of this.listeners)
            cb({ matches });
    }
}
function makeProvider(initial) {
    const mql = new FakeMediaQueryList(initial, '(prefers-reduced-motion: reduce)');
    const provider = {
        matchMedia(query) {
            return new FakeMediaQueryList(initial, query);
        },
    };
    // Use a stable mql instance that we control:
    provider.matchMedia = (query) => {
        mql.media = query;
        return mql;
    };
    return { provider, mql };
}
function run() {
    // === prefersReducedMotion: returns true when matchMedia matches ===
    {
        const { provider } = makeProvider(true);
        strict_1.default.equal((0, reducedMotion_1.prefersReducedMotion)({ provider }), true);
    }
    // === prefersReducedMotion: returns false when matchMedia does not match ===
    {
        const { provider } = makeProvider(false);
        strict_1.default.equal((0, reducedMotion_1.prefersReducedMotion)({ provider }), false);
    }
    // === prefersReducedMotion: missing matchMedia returns false (graceful) ===
    {
        const provider = { matchMedia: undefined };
        strict_1.default.equal((0, reducedMotion_1.prefersReducedMotion)({ provider }), false);
    }
    // === subscribeReducedMotion fires callback on change ===
    {
        const { provider, mql } = makeProvider(false);
        const events = [];
        const unsubscribe = (0, reducedMotion_1.subscribeReducedMotion)((v) => events.push(v), { provider });
        mql.triggerChange(true);
        mql.triggerChange(false);
        strict_1.default.deepEqual(events, [true, false]);
        unsubscribe();
    }
    // === subscribeReducedMotion: unsubscribe stops further callbacks ===
    {
        const { provider, mql } = makeProvider(false);
        const events = [];
        const unsubscribe = (0, reducedMotion_1.subscribeReducedMotion)((v) => events.push(v), { provider });
        mql.triggerChange(true);
        unsubscribe();
        mql.triggerChange(false);
        strict_1.default.deepEqual(events, [true]);
    }
    // === subscribeReducedMotion: missing provider returns no-op unsubscribe ===
    {
        const provider = { matchMedia: undefined };
        const events = [];
        const unsubscribe = (0, reducedMotion_1.subscribeReducedMotion)((v) => events.push(v), { provider });
        unsubscribe();
        strict_1.default.deepEqual(events, []);
    }
    // === subscribeReducedMotion: emits initial value if requested ===
    {
        const { provider } = makeProvider(true);
        const events = [];
        const unsubscribe = (0, reducedMotion_1.subscribeReducedMotion)((v) => events.push(v), {
            provider,
            emitInitial: true,
        });
        strict_1.default.deepEqual(events, [true]);
        unsubscribe();
    }
    console.log('[contract] PASS reduced-motion (7 cases)');
}
run();
