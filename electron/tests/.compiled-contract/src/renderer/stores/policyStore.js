"use strict";
/**
 * Policy state for autonomous runtime configuration surfaced in Electron.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.usePolicyStore = void 0;
const zustand_1 = require("zustand");
exports.usePolicyStore = (0, zustand_1.create)((set) => ({
    snapshot: null,
    lastUpdatedAt: null,
    setSnapshot: (snapshot) => set({ snapshot }),
    markUpdated: () => set({ lastUpdatedAt: Date.now() }),
    resetPolicy: () => set({
        snapshot: null,
        lastUpdatedAt: null,
    }),
}));
