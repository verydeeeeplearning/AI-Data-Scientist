"use strict";
/**
 * Shared auth snapshot for provider status, OAuth accounts, and masked keys.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.useAuthStore = void 0;
const zustand_1 = require("zustand");
exports.useAuthStore = (0, zustand_1.create)((set) => ({
    providerStatuses: {},
    maskedKeys: {},
    oauthStatuses: {},
    providerHealth: {},
    loading: false,
    lastUpdatedAt: null,
    lastFallbackEvent: null,
    setSnapshot: (snapshot) => set({
        ...snapshot,
        lastUpdatedAt: Date.now(),
    }),
    setFallbackEvent: (lastFallbackEvent) => set({ lastFallbackEvent }),
    setLoading: (loading) => set({ loading }),
    resetAuth: () => set({
        providerStatuses: {},
        maskedKeys: {},
        oauthStatuses: {},
        providerHealth: {},
        loading: false,
        lastUpdatedAt: null,
        lastFallbackEvent: null,
    }),
}));
