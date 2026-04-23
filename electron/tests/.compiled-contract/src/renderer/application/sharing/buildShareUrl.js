"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.buildShareUrl = buildShareUrl;
const RESOURCE_PATH_SEGMENT = {
    run: 'runs',
    artifact: 'artifacts',
    session: 'sessions',
    mission: 'missions',
};
function buildShareUrl(input) {
    const trimmed = input.resourceId.trim();
    if (trimmed.length === 0) {
        throw new Error('buildShareUrl: resourceId is required');
    }
    const segment = RESOURCE_PATH_SEGMENT[input.resourceType];
    const path = `/${segment}/${encodeURIComponent(trimmed)}`;
    const url = input.baseUrl ? `${input.baseUrl.replace(/\/+$/, '')}${path}` : path;
    return {
        resourceType: input.resourceType,
        resourceId: trimmed,
        url,
    };
}
