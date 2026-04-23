"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.buildGovernanceSectionPath = buildGovernanceSectionPath;
exports.resolveGovernanceLanding = resolveGovernanceLanding;
const GOVERNANCE_SECTION_PATHS = Object.freeze({
    review: '/governance/review',
    certification: '/governance/certification',
    policy: '/governance/policy',
    approvals: '/governance/approvals',
});
function buildGovernanceSectionPath(sectionId) {
    return GOVERNANCE_SECTION_PATHS[sectionId];
}
function createLandingState(sectionId, detail = null) {
    return {
        sectionId,
        sectionPath: buildGovernanceSectionPath(sectionId),
        detail,
    };
}
function joinDetailId(segments) {
    const value = segments.join('/').trim();
    return value.length > 0 ? value : null;
}
function resolveGovernanceLanding(selection) {
    const [primary = 'review', ...rest] = selection.subPath?.split('/').filter(Boolean) ?? [];
    const detailId = joinDetailId(rest);
    switch (primary) {
        case 'review':
            return createLandingState('review');
        case 'verifier':
            return createLandingState('review', { kind: 'verifier', id: detailId });
        case 'lineage':
            return createLandingState('review', { kind: 'lineage', id: detailId });
        case 'fallback-log':
            return createLandingState('review', { kind: 'fallback-log', id: detailId });
        case 'drift':
            return createLandingState('review', { kind: 'drift', id: detailId });
        case 'certification':
            return createLandingState('certification', detailId ? { kind: 'certification', id: detailId } : null);
        case 'policy':
        case 'policies':
            return createLandingState('policy', detailId ? { kind: 'policy', id: detailId } : null);
        case 'approval':
        case 'approvals':
            return createLandingState('approvals', detailId ? { kind: 'approval', id: detailId } : null);
        default:
            return createLandingState('review');
    }
}
