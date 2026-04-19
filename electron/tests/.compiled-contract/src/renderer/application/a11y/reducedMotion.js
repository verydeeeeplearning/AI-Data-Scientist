"use strict";
/**
 * `prefers-reduced-motion` utility (WCAG 2.3.3 Animation from Interactions).
 *
 * Pure DOM API — no React or 3rd-party lib (ADR-0008). Components in
 * higher layers wrap these in hooks (e.g. `useReducedMotion`).
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.prefersReducedMotion = prefersReducedMotion;
exports.subscribeReducedMotion = subscribeReducedMotion;
const QUERY = '(prefers-reduced-motion: reduce)';
function resolveProvider(options) {
    if (options.provider)
        return options.provider;
    if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
        return { matchMedia: window.matchMedia.bind(window) };
    }
    return { matchMedia: undefined };
}
function prefersReducedMotion(options = {}) {
    const provider = resolveProvider(options);
    if (!provider.matchMedia)
        return false;
    try {
        return provider.matchMedia(QUERY).matches;
    }
    catch {
        return false;
    }
}
function subscribeReducedMotion(listener, options = {}) {
    const provider = resolveProvider(options);
    if (!provider.matchMedia) {
        return () => {
            // no-op
        };
    }
    let mql;
    try {
        mql = provider.matchMedia(QUERY);
    }
    catch {
        return () => {
            // no-op
        };
    }
    if (options.emitInitial) {
        listener(mql.matches);
    }
    const handler = (event) => listener(event.matches);
    mql.addEventListener('change', handler);
    return () => {
        mql.removeEventListener('change', handler);
    };
}
