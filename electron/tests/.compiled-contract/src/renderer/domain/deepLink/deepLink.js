"use strict";
// Cross-surface deep link contract (W4-C / PLAN_03).
//
// Wire format: ds-agent://workspace/<workspaceId>/<resourceType>/<resourceId>(?action=<action>)
//
// Parsing is pure, runs in renderer / Electron main / CLI / Telegram identically.
// External input MUST flow through `parseDeepLink` so traversal / scheme spoofing
// / oversized URIs are rejected before any side effect.
Object.defineProperty(exports, "__esModule", { value: true });
exports.DEEP_LINK_RESOURCE_TYPES = exports.DEEP_LINK_MAX_LENGTH = exports.DEEP_LINK_HOST = exports.DEEP_LINK_SCHEME = void 0;
exports.parseDeepLink = parseDeepLink;
exports.buildDeepLinkUri = buildDeepLinkUri;
exports.DEEP_LINK_SCHEME = 'ds-agent:';
exports.DEEP_LINK_HOST = 'workspace';
exports.DEEP_LINK_MAX_LENGTH = 2048;
exports.DEEP_LINK_RESOURCE_TYPES = [
    'run',
    'artifact',
    'checkpoint',
    'verifier_result',
];
const ID_PATTERN = /^[A-Za-z0-9_:.-]{1,128}$/;
const ACTION_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;
function isResourceType(value) {
    return exports.DEEP_LINK_RESOURCE_TYPES.includes(value);
}
function containsTraversal(segment) {
    return segment.includes('..') || segment.includes('//') || segment.includes('\\');
}
function parseDeepLink(rawInput) {
    if (typeof rawInput !== 'string' || rawInput.length === 0) {
        return { ok: false, error: 'invalid_scheme' };
    }
    if (rawInput.length > exports.DEEP_LINK_MAX_LENGTH) {
        return { ok: false, error: 'too_long' };
    }
    let url;
    try {
        url = new URL(rawInput);
    }
    catch {
        return { ok: false, error: 'invalid_scheme' };
    }
    if (url.protocol !== exports.DEEP_LINK_SCHEME) {
        return { ok: false, error: 'invalid_scheme' };
    }
    // For ds-agent://workspace/<id>/...  the host parses as 'workspace'.
    if (url.hostname !== exports.DEEP_LINK_HOST) {
        return { ok: false, error: 'invalid_host' };
    }
    const segments = url.pathname.split('/').filter((segment) => segment.length > 0);
    if (segments.length === 0) {
        return { ok: false, error: 'missing_workspace' };
    }
    const workspaceId = decodeSegment(segments[0]);
    if (workspaceId === null || !ID_PATTERN.test(workspaceId)) {
        return { ok: false, error: 'invalid_workspace' };
    }
    if (segments.length < 2) {
        return { ok: false, error: 'unknown_resource_type' };
    }
    const resourceType = segments[1];
    if (!isResourceType(resourceType)) {
        return { ok: false, error: 'unknown_resource_type' };
    }
    if (segments.length < 3) {
        return { ok: false, error: 'missing_resource_id' };
    }
    // Reject extra path segments — they make path-traversal disguise easier.
    if (segments.length > 3) {
        return { ok: false, error: 'path_traversal' };
    }
    const rawResourceId = segments[2];
    if (containsTraversal(rawResourceId)) {
        return { ok: false, error: 'path_traversal' };
    }
    const resourceId = decodeSegment(rawResourceId);
    if (resourceId === null || !ID_PATTERN.test(resourceId)) {
        return { ok: false, error: 'invalid_resource_id' };
    }
    let action = null;
    const rawAction = url.searchParams.get('action');
    if (rawAction !== null) {
        if (!ACTION_PATTERN.test(rawAction)) {
            return { ok: false, error: 'invalid_action' };
        }
        action = rawAction;
    }
    return {
        ok: true,
        value: { workspaceId, resourceType, resourceId, action },
    };
}
function decodeSegment(segment) {
    try {
        const decoded = decodeURIComponent(segment);
        return decoded.length > 0 ? decoded : null;
    }
    catch {
        return null;
    }
}
function buildDeepLinkUri(link) {
    const base = `${exports.DEEP_LINK_SCHEME}//${exports.DEEP_LINK_HOST}`
        + `/${encodeURIComponent(link.workspaceId)}`
        + `/${link.resourceType}`
        + `/${encodeURIComponent(link.resourceId)}`;
    if (link.action) {
        const params = new URLSearchParams({ action: link.action });
        return `${base}?${params.toString()}`;
    }
    return base;
}
