"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.resolveAccessRole = resolveAccessRole;
exports.useAccessRole = useAccessRole;
const SOLE_USER_MODE = true;
function resolveAccessRole(forceRole, soleUserMode) {
    if (forceRole !== undefined) {
        return forceRole;
    }
    if (soleUserMode) {
        return 'owner';
    }
    return 'owner';
}
function useAccessRole(options = {}) {
    const role = resolveAccessRole(options.forceRole, SOLE_USER_MODE);
    return {
        role,
        isOwner: role === 'owner',
        isViewer: role === 'viewer',
    };
}
