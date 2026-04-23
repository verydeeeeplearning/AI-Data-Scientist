"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.matchesShortcut = matchesShortcut;
function normalizeKey(value) {
    return value.trim().toLowerCase();
}
function parseShortcut(shortcut) {
    const parsed = {
        key: '',
        ctrlKey: false,
        metaKey: false,
        altKey: false,
        shiftKey: false,
    };
    for (const token of shortcut.split('+').map((item) => item.trim()).filter(Boolean)) {
        const normalized = normalizeKey(token);
        if (normalized === 'ctrl' || normalized === 'control') {
            parsed.ctrlKey = true;
            continue;
        }
        if (normalized === 'meta' || normalized === 'cmd' || normalized === 'command') {
            parsed.metaKey = true;
            continue;
        }
        if (normalized === 'alt' || normalized === 'option') {
            parsed.altKey = true;
            continue;
        }
        if (normalized === 'shift') {
            parsed.shiftKey = true;
            continue;
        }
        parsed.key = normalized;
    }
    return parsed;
}
function matchesShortcut(event, shortcut) {
    const parsed = parseShortcut(shortcut);
    if (!parsed.key) {
        return false;
    }
    return (parsed.key === normalizeKey(event.key)
        && parsed.ctrlKey === event.ctrlKey
        && parsed.metaKey === event.metaKey
        && parsed.altKey === event.altKey
        && parsed.shiftKey === event.shiftKey);
}
