"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DENSITY_STORAGE_KEY = void 0;
exports.loadStoredDensity = loadStoredDensity;
exports.persistDensity = persistDensity;
exports.applyDensityToDocument = applyDensityToDocument;
const density_1 = require("../../domain/layout/density");
const applyDensityScale_1 = require("../../application/layout/applyDensityScale");
exports.DENSITY_STORAGE_KEY = 'ds-agent-density:v1';
function loadStoredDensity() {
    if (typeof window === 'undefined') {
        return density_1.DEFAULT_DENSITY_MODE;
    }
    try {
        const raw = window.localStorage.getItem(exports.DENSITY_STORAGE_KEY);
        if (raw && (0, density_1.isDensityMode)(raw)) {
            return raw;
        }
    }
    catch {
        // Storage unavailable (private mode, etc.) — fall through to default.
    }
    return density_1.DEFAULT_DENSITY_MODE;
}
function persistDensity(mode) {
    if (typeof window === 'undefined') {
        return;
    }
    try {
        window.localStorage.setItem(exports.DENSITY_STORAGE_KEY, mode);
    }
    catch {
        // Quota or permission denied — silently drop; runtime still applies.
    }
}
function applyDensityToDocument(mode) {
    if (typeof document === 'undefined') {
        return;
    }
    document.documentElement.setAttribute('data-density', mode);
    const overrides = (0, applyDensityScale_1.applyDensityScale)(mode);
    for (const [variable, value] of Object.entries(overrides)) {
        document.documentElement.style.setProperty(variable, value);
    }
}
