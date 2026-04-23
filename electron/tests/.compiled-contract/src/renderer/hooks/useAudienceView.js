"use strict";
/**
 * useAudienceView — renderer-friendly facade over the workspace store
 * audience-view slice plus the domain-level profile lookup.
 *
 * Components consume this hook so they don't have to wire two imports
 * (zustand selector + `getAudienceViewProfile`) at every call site.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.getAudienceViewProfile = void 0;
exports.useAudienceView = useAudienceView;
exports.useAudienceViewTelemetry = useAudienceViewTelemetry;
const react_1 = require("react");
const audienceView_1 = require("../domain/workspace/audienceView");
Object.defineProperty(exports, "getAudienceViewProfile", { enumerable: true, get: function () { return audienceView_1.getAudienceViewProfile; } });
const cardApi_1 = require("../infrastructure/api/cardApi");
const workspaceStore_1 = require("../stores/workspaceStore");
function useAudienceView() {
    const view = (0, workspaceStore_1.useWorkspaceStore)((state) => state.audienceView);
    const setView = (0, workspaceStore_1.useWorkspaceStore)((state) => state.setAudienceView);
    const profile = (0, audienceView_1.getAudienceViewProfile)(view);
    return { view, profile, setView };
}
/**
 * Best-effort audience-switch beacon that records the active workspace lens
 * through the backend runtime-event log. Used by the workspace shell after
 * the user changes audience.
 */
function useAudienceViewTelemetry(view, options = {}) {
    const previousView = (0, react_1.useRef)(null);
    (0, react_1.useEffect)(() => {
        const fromAudience = previousView.current;
        previousView.current = view;
        if (fromAudience === null || fromAudience === view) {
            return;
        }
        void (0, cardApi_1.reportAudienceSwitch)({
            fromAudience,
            toAudience: view,
            sessionId: options.sessionId ?? null,
        }).catch((error) => {
            console.warn('[useAudienceViewTelemetry] audience switch beacon failed:', error);
        });
    }, [options.sessionId, view]);
}
