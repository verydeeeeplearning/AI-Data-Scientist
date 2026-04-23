"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.RISK_TIER_OPTIONS = exports.RISK_TIER_VALUES = void 0;
exports.coerceRiskTierValue = coerceRiskTierValue;
exports.normalizeRiskTierMatrix = normalizeRiskTierMatrix;
exports.countRiskTierCellDiff = countRiskTierCellDiff;
exports.countRiskTierRowDiff = countRiskTierRowDiff;
exports.formatRiskTierLabel = formatRiskTierLabel;
exports.resolveRiskTierSavedBy = resolveRiskTierSavedBy;
exports.formatRiskTierSnapshotLabel = formatRiskTierSnapshotLabel;
exports.RISK_TIER_VALUES = ['T0', 'T1', 'T2', 'T3'];
exports.RISK_TIER_OPTIONS = [
    { value: 'T0', label: 'T0' },
    { value: 'T1', label: 'T1' },
    { value: 'T2', label: 'T2' },
    { value: 'T3', label: 'T3' },
];
const RISK_TIER_ALIASES = {
    auto: 'T0',
    critical: 'T3',
    dual: 'T3',
    guarded: 'T1',
    approve: 'T2',
    ask: 'T1',
    routine: 'T0',
    sensitive: 'T2',
    t0: 'T0',
    t1: 'T1',
    t2: 'T2',
    t3: 'T3',
};
function isRiskTier(value) {
    return typeof value === 'string'
        && exports.RISK_TIER_VALUES.includes(value.trim().toUpperCase());
}
function normalizeRiskTierCode(value) {
    const normalized = value.trim().toLowerCase();
    return RISK_TIER_ALIASES[normalized] ?? null;
}
function coerceRiskTierValue(value, fallback = 'T0') {
    if (value === null || value === undefined) {
        return fallback;
    }
    const normalized = normalizeRiskTierCode(value);
    if (normalized !== null) {
        return normalized;
    }
    const upper = value.trim().toUpperCase();
    return isRiskTier(upper) ? upper : fallback;
}
function normalizeRiskTierMatrix(raw) {
    if (!raw || typeof raw !== 'object') {
        return {};
    }
    const result = {};
    for (const [actionName, row] of Object.entries(raw)) {
        const actionKey = actionName.trim();
        if (!actionKey || !row || typeof row !== 'object') {
            continue;
        }
        const cells = {};
        for (const [authority, tier] of Object.entries(row)) {
            const authorityKey = authority.trim();
            const tierValue = typeof tier === 'string' ? tier.trim() : '';
            if (!authorityKey || !tierValue) {
                continue;
            }
            cells[authorityKey] = tierValue;
        }
        if (Object.keys(cells).length > 0) {
            result[actionKey] = cells;
        }
    }
    return result;
}
function countRiskTierCellDiff(current, draft) {
    const actionNames = new Set([
        ...Object.keys(current ?? {}),
        ...Object.keys(draft ?? {}),
    ]);
    let changed = 0;
    for (const actionName of actionNames) {
        const currentRow = current?.[actionName] ?? {};
        const draftRow = draft?.[actionName] ?? {};
        const authorityNames = new Set([
            ...Object.keys(currentRow),
            ...Object.keys(draftRow),
        ]);
        for (const authorityName of authorityNames) {
            if ((currentRow[authorityName] ?? null) !== (draftRow[authorityName] ?? null)) {
                changed += 1;
            }
        }
    }
    return changed;
}
function countRiskTierRowDiff(current, draft) {
    const actionNames = new Set([
        ...Object.keys(current ?? {}),
        ...Object.keys(draft ?? {}),
    ]);
    let changed = 0;
    for (const actionName of actionNames) {
        const currentRow = current?.[actionName] ?? {};
        const draftRow = draft?.[actionName] ?? {};
        const authorityNames = new Set([
            ...Object.keys(currentRow),
            ...Object.keys(draftRow),
        ]);
        let rowChanged = false;
        for (const authorityName of authorityNames) {
            if ((currentRow[authorityName] ?? null) !== (draftRow[authorityName] ?? null)) {
                rowChanged = true;
                break;
            }
        }
        if (rowChanged) {
            changed += 1;
        }
    }
    return changed;
}
function formatRiskTierLabel(value) {
    if (value === null || value === undefined || value.trim() === '') {
        return 'Unset';
    }
    const normalized = normalizeRiskTierCode(value);
    if (normalized !== null) {
        return normalized;
    }
    return value.trim();
}
function resolveRiskTierSavedBy(organization) {
    const members = organization?.members ?? [];
    if (members.length === 0) {
        return null;
    }
    const rolePriority = {
        admin: 0,
        editor: 1,
        viewer: 2,
    };
    const sorted = [...members].filter((member) => {
        const userId = member.userId?.trim() ?? '';
        return userId.length > 0;
    }).sort((left, right) => {
        const leftRole = rolePriority[(left.role ?? '').trim().toLowerCase()] ?? 99;
        const rightRole = rolePriority[(right.role ?? '').trim().toLowerCase()] ?? 99;
        if (leftRole !== rightRole) {
            return leftRole - rightRole;
        }
        const leftId = left.userId?.trim() ?? '';
        const rightId = right.userId?.trim() ?? '';
        return leftId.localeCompare(rightId);
    });
    return sorted[0]?.userId?.trim() || null;
}
function formatRiskTierSnapshotLabel(snapshot) {
    if (!snapshot) {
        return null;
    }
    const savedAt = Number.isFinite(snapshot.savedAt) ? snapshot.savedAt : 0;
    if (savedAt <= 0) {
        return null;
    }
    const iso = new Date(savedAt * 1000).toISOString();
    if (snapshot.savedBy && snapshot.savedBy.trim()) {
        return `Last saved: ${iso} by ${snapshot.savedBy.trim()}`;
    }
    return `Last saved: ${iso}`;
}
