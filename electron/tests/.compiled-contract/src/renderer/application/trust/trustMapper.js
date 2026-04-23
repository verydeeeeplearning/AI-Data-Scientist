"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.mapTrustPayload = mapTrustPayload;
exports.buildTrustBadgeHref = buildTrustBadgeHref;
const resolveGovernanceLanding_1 = require("../navigation/resolveGovernanceLanding");
const COLLECTION_KEYS = ['badges', 'strip', 'items', 'signals'];
const KNOWN_BADGE_KIND_MAP = Object.freeze({
    verifier: 'verifier',
    lineage: 'lineage',
    fallback: 'fallback-log',
    fallback_log: 'fallback-log',
    'fallback-log': 'fallback-log',
    approval: 'approval',
    approvals: 'approval',
    policy: 'policy',
    policies: 'policy',
    certification: 'certification',
    drift: 'drift',
});
const DERIVED_ROOTS = [
    { keys: ['verifier'], kind: 'verifier' },
    { keys: ['lineage'], kind: 'lineage' },
    { keys: ['fallback', 'fallbackLog', 'fallback_log'], kind: 'fallback-log' },
    { keys: ['approval'], kind: 'approval' },
    { keys: ['policy'], kind: 'policy' },
    { keys: ['certification'], kind: 'certification' },
    { keys: ['drift'], kind: 'drift' },
];
const DERIVED_STATUS_FIELDS = [
    { kind: 'verifier', fields: ['verifierStatus'] },
    { kind: 'lineage', fields: ['lineageStatus'] },
    { kind: 'fallback-log', fields: ['fallbackStatus', 'fallbackLogStatus'] },
    { kind: 'approval', fields: ['approvalStatus'] },
    { kind: 'policy', fields: ['policyStatus'] },
    { kind: 'certification', fields: ['certificationStatus'] },
    { kind: 'drift', fields: ['driftStatus'] },
];
const REVIEW_DETAIL_KINDS = new Set([
    'verifier',
    'lineage',
    'fallback-log',
    'drift',
]);
const DEFAULT_LABELS = Object.freeze({
    verifier: 'Verifier',
    lineage: 'Lineage',
    'fallback-log': 'Fallback',
    approval: 'Approval',
    policy: 'Policy',
    certification: 'Certification',
    drift: 'Drift',
    unknown: 'Trust',
});
function isRecord(value) {
    return typeof value === 'object' && value !== null;
}
function asString(value) {
    return typeof value === 'string' && value.trim().length > 0 ? value.trim() : null;
}
function normalizeKind(value, fallback = 'unknown') {
    const normalized = asString(value)?.toLowerCase().replace(/\s+/g, '_');
    if (!normalized) {
        return fallback;
    }
    return KNOWN_BADGE_KIND_MAP[normalized] ?? fallback;
}
function normalizeStatus(value) {
    const normalized = asString(value)?.toLowerCase().replace(/\s+/g, '-');
    switch (normalized) {
        case 'pass':
        case 'passed':
        case 'ok':
        case 'healthy':
        case 'verified':
        case 'ready':
            return 'pass';
        case 'warn':
        case 'warning':
        case 'caution':
        case 'degraded':
        case 'review':
            return 'warn';
        case 'fail':
        case 'failed':
        case 'error':
        case 'blocked':
        case 'rejected':
            return 'fail';
        case 'pending':
        case 'queued':
        case 'needs-review':
        case 'needs_review':
        case 'in-progress':
        case 'in_progress':
            return 'pending';
        default:
            return 'unknown';
    }
}
function pickFirstString(record, keys) {
    for (const key of keys) {
        const value = asString(record[key]);
        if (value) {
            return value;
        }
    }
    return null;
}
function normalizePath(value) {
    const trimmed = value.trim();
    if (trimmed.startsWith('/governance/')) {
        return trimmed;
    }
    if (trimmed.startsWith('governance/')) {
        return `/${trimmed}`;
    }
    if (trimmed.startsWith('/')) {
        return trimmed;
    }
    return `/governance/${trimmed}`;
}
function appendDetail(path, detailId) {
    const cleaned = detailId
        ?.split('/')
        .map((segment) => segment.trim())
        .filter(Boolean)
        .join('/');
    return cleaned ? `${path}/${cleaned}` : path;
}
function buildPathFromDetail(detailKind, detailId) {
    if (REVIEW_DETAIL_KINDS.has(detailKind)) {
        return {
            path: appendDetail(`/governance/${detailKind}`, detailId),
            sectionId: 'review',
        };
    }
    if (detailKind === 'approval') {
        return {
            path: appendDetail('/governance/approval', detailId),
            sectionId: 'approvals',
        };
    }
    if (detailKind === 'policy') {
        return {
            path: appendDetail((0, resolveGovernanceLanding_1.buildGovernanceSectionPath)('policy'), detailId),
            sectionId: 'policy',
        };
    }
    return {
        path: appendDetail((0, resolveGovernanceLanding_1.buildGovernanceSectionPath)('certification'), detailId),
        sectionId: 'certification',
    };
}
function inferDetailId(kind, record) {
    switch (kind) {
        case 'approval':
            return pickFirstString(record, ['approvalId', 'detailId', 'id']);
        case 'policy':
            return pickFirstString(record, ['policyId', 'detailId', 'id']);
        case 'certification':
            return pickFirstString(record, ['certificationId', 'detailId', 'id']);
        case 'verifier':
            return pickFirstString(record, ['verifierId', 'detailId', 'id']);
        case 'lineage':
            return pickFirstString(record, ['lineageId', 'detailId', 'id']);
        case 'fallback-log':
            return pickFirstString(record, ['fallbackId', 'fallbackLogId', 'detailId', 'id']);
        case 'drift':
            return pickFirstString(record, ['driftId', 'detailId', 'id']);
        default:
            return pickFirstString(record, ['detailId', 'id']);
    }
}
function resolveTarget(kind, record) {
    const rawTarget = isRecord(record.target)
        ? record.target
        : (isRecord(record.deepLink) ? record.deepLink : null);
    const pathCandidate = asString(record.path) ??
        asString(record.href) ??
        asString(record.subPath) ??
        asString(rawTarget?.path) ??
        asString(rawTarget?.href) ??
        asString(rawTarget?.subPath);
    if (pathCandidate) {
        const path = normalizePath(pathCandidate);
        return {
            path,
            sectionId: inferSectionFromPath(path),
            detailKind: inferDetailKindFromPath(path),
            detailId: inferDetailIdFromPath(path),
        };
    }
    if (kind === 'unknown') {
        const path = (0, resolveGovernanceLanding_1.buildGovernanceSectionPath)('review');
        return {
            path,
            sectionId: 'review',
            detailKind: null,
            detailId: null,
        };
    }
    const detailId = asString(rawTarget?.id) ?? inferDetailId(kind, record);
    const derived = buildPathFromDetail(kind, detailId);
    return {
        path: derived.path,
        sectionId: derived.sectionId,
        detailKind: kind,
        detailId,
    };
}
function inferSectionFromPath(path) {
    if (path.startsWith('/governance/approval') || path.startsWith('/governance/approvals')) {
        return 'approvals';
    }
    if (path.startsWith('/governance/policy') || path.startsWith('/governance/policies')) {
        return 'policy';
    }
    if (path.startsWith('/governance/certification')) {
        return 'certification';
    }
    return 'review';
}
function inferDetailKindFromPath(path) {
    const parts = path.split('/').filter(Boolean);
    if (parts.length < 2 || parts[0] !== 'governance') {
        return null;
    }
    const detail = normalizeKind(parts[1], 'unknown');
    return detail === 'unknown' ? null : detail;
}
function inferDetailIdFromPath(path) {
    const parts = path.split('/').filter(Boolean);
    if (parts.length <= 2) {
        return null;
    }
    return parts.slice(2).join('/');
}
function extractExplicitBadges(record) {
    for (const key of COLLECTION_KEYS) {
        if (Array.isArray(record[key])) {
            return record[key]
                .filter(isRecord)
                .map((item) => item);
        }
    }
    return [];
}
function extractDerivedBadges(record) {
    const badges = [];
    for (const root of DERIVED_ROOTS) {
        for (const key of root.keys) {
            if (isRecord(record[key])) {
                badges.push({ ...record[key], kindHint: root.kind });
                break;
            }
        }
    }
    for (const root of DERIVED_STATUS_FIELDS) {
        const status = pickFirstString(record, root.fields);
        if (!status) {
            continue;
        }
        const hasExistingKind = badges.some((badge) => normalizeKind(badge.kindHint) === root.kind);
        if (hasExistingKind) {
            continue;
        }
        const detailFieldName = root.kind === 'approval' ? 'approvalId' : `${root.kind}Id`;
        badges.push({
            kindHint: root.kind,
            status,
            detailId: record[detailFieldName],
            approvalId: record.approvalId,
            policyId: record.policyId,
            certificationId: record.certificationId,
            verifierId: record.verifierId,
            lineageId: record.lineageId,
            fallbackId: record.fallbackId,
            fallbackLogId: record.fallbackLogId,
            driftId: record.driftId,
        });
    }
    if (!badges.some((badge) => normalizeKind(badge.kindHint) === 'approval') &&
        (asString(record.approvalStatus) || asString(record.approvalId))) {
        badges.push({
            kindHint: 'approval',
            status: record.approvalStatus,
            approvalId: record.approvalId,
            detail: asString(record.approvalOutcome) ?? asString(record.approvalDetail),
        });
    }
    return badges;
}
function buildBadge(candidate, index) {
    const kind = normalizeKind(candidate.kind ?? candidate.kindHint ?? candidate.key ?? candidate.id ?? candidate.name);
    const target = resolveTarget(kind, candidate);
    const label = asString(candidate.label) ?? DEFAULT_LABELS[kind];
    const detail = asString(candidate.detail) ??
        asString(candidate.summary) ??
        asString(candidate.reason) ??
        asString(candidate.message) ??
        asString(candidate.value);
    const status = normalizeStatus(candidate.status ?? candidate.level ?? candidate.state ?? candidate.approvalStatus);
    const key = asString(candidate.key) ?? (kind === 'unknown' ? `trust-${index}` : kind);
    return {
        key,
        kind,
        label,
        status,
        detail,
        href: target.path,
        target,
    };
}
function mapTrustPayload(resultId, payload) {
    const record = isRecord(payload) ? payload : {};
    const resolvedResultId = asString(record.resultId) ?? resultId;
    const candidates = [
        ...extractExplicitBadges(record),
        ...extractDerivedBadges(record),
    ];
    const seen = new Set();
    const badges = candidates
        .map((candidate, index) => buildBadge(candidate, index))
        .filter((badge) => Boolean(badge))
        .filter((badge) => {
        if (seen.has(badge.key)) {
            return false;
        }
        seen.add(badge.key);
        return true;
    });
    return {
        resultId: resolvedResultId,
        badges,
        fetchedAt: Date.now(),
        updatedAt: asString(record.updatedAt),
    };
}
function buildTrustBadgeHref(badge) {
    return badge.href;
}
