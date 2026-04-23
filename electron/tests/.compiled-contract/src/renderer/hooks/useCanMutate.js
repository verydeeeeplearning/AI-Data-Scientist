"use strict";
/**
 * Shared mutation gate for renderer call sites.
 *
 * Wraps {@link useAccessRole} so each mutation surface can ask
 * "is this resource read-only for me right now?" without duplicating role
 * resolution. Returns ``{ canMutate, reason }`` where ``reason`` is a stable
 * i18n key suitable for tooltips on disabled controls.
 *
 * The hook intentionally returns a viewer-friendly *disable* signal — pages
 * keep mutation controls visible (so the read-only state is legible) and
 * surface the explanation through ``aria-disabled`` + tooltips.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.resolveCanMutate = resolveCanMutate;
exports.useCanMutate = useCanMutate;
const useAccessRole_1 = require("./useAccessRole");
const VIEWER_REASON_KEY = 'share.banner.readOnlyTooltip';
function resolveCanMutate(role) {
    if (role === 'owner') {
        return { role, canMutate: true };
    }
    return { role, canMutate: false, reason: VIEWER_REASON_KEY };
}
function useCanMutate(options = {}) {
    const { role } = (0, useAccessRole_1.useAccessRole)({ forceRole: options.forceRole });
    return resolveCanMutate(role);
}
