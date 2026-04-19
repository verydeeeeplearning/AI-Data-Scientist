"use strict";
/**
 * Focus management utilities (WCAG 2.4.3 Focus Order, 2.4.7 Focus Visible).
 *
 * Pure DOM API — no React or 3rd-party lib (ADR-0008). Components in
 * higher layers wrap these in hooks (e.g. `useFocusTrap`).
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.isFocusable = isFocusable;
exports.findFocusableElements = findFocusableElements;
exports.captureFocus = captureFocus;
exports.restoreFocus = restoreFocus;
exports.createFocusTrap = createFocusTrap;
const FOCUSABLE_TAGS = new Set(['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA']);
function isFocusable(el) {
    const e = el;
    if (!e || typeof e.tagName !== 'string')
        return false;
    if (e.hasAttribute('disabled'))
        return false;
    const tabindex = e.getAttribute('tabindex');
    if (tabindex !== null) {
        const value = Number(tabindex);
        if (Number.isFinite(value) && value < 0)
            return false;
    }
    if (FOCUSABLE_TAGS.has(e.tagName)) {
        return true;
    }
    if (e.tagName === 'A' && e.getAttribute('href') !== null) {
        return true;
    }
    // Element with explicit non-negative tabindex is focusable
    if (tabindex !== null) {
        const value = Number(tabindex);
        if (Number.isFinite(value) && value >= 0)
            return true;
    }
    return false;
}
function findFocusableElements(container) {
    const c = container;
    const all = Array.from(c.querySelectorAll('*'));
    return all.filter((el) => isFocusable(el));
}
function captureFocus(options = {}) {
    const doc = options.document ?? (typeof document !== 'undefined' ? document : null);
    if (!doc)
        return { previous: null };
    const active = doc.activeElement;
    if (active && typeof active.focus === 'function') {
        return { previous: active };
    }
    return { previous: null };
}
function restoreFocus(token) {
    if (!token || !token.previous)
        return;
    try {
        token.previous.focus();
    }
    catch {
        // Element may have been removed from the DOM; swallow silently.
    }
}
function createFocusTrap(container, options = {}) {
    const doc = options.document ?? (typeof document !== 'undefined' ? document : null);
    let priorToken = { previous: null };
    let active = false;
    function getFocusables() {
        return findFocusableElements(container);
    }
    return {
        activate() {
            if (active)
                return;
            active = true;
            priorToken = captureFocus({ document: doc ?? undefined });
            const focusables = getFocusables();
            if (focusables.length > 0) {
                focusables[0].focus();
            }
            else {
                container.focus();
            }
        },
        deactivate() {
            if (!active)
                return;
            active = false;
            restoreFocus(priorToken);
            priorToken = { previous: null };
        },
        cycle(direction) {
            const focusables = getFocusables();
            if (focusables.length === 0)
                return null;
            const current = doc ? doc.activeElement : null;
            const idx = focusables.findIndex((el) => el === current);
            let next;
            if (direction === 'forward') {
                next = idx === -1 || idx === focusables.length - 1 ? focusables[0] : focusables[idx + 1];
            }
            else {
                next = idx <= 0 ? focusables[focusables.length - 1] : focusables[idx - 1];
            }
            next.focus();
            return next;
        },
    };
}
