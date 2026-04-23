"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.normalizeNavigationPath = normalizeNavigationPath;
exports.buildNavigationHash = buildNavigationHash;
exports.parseAreaSelection = parseAreaSelection;
exports.resolveNavigationState = resolveNavigationState;
const area_1 = require("../../domain/navigation/area");
const migrateLegacyRoute_1 = require("./migrateLegacyRoute");
function stripHashPrefix(hash) {
    const value = hash.startsWith('#') ? hash.slice(1) : hash;
    if (!value) {
        return area_1.DEFAULT_AREA_PATH;
    }
    return value.startsWith('/') ? value : `/${value}`;
}
function normalizeNavigationPath(path) {
    const raw = stripHashPrefix(path).replace(/\/{2,}/g, '/');
    const cleaned = raw.replace(/\/+$/, '');
    return cleaned || area_1.DEFAULT_AREA_PATH;
}
function buildNavigationHash(path) {
    return `#${normalizeNavigationPath(path)}`;
}
function parseAreaSelection(path) {
    const normalized = normalizeNavigationPath(path);
    const [areaCandidate = 'mission', ...rest] = normalized.slice(1).split('/');
    const areaId = (0, area_1.isAreaId)(areaCandidate) ? areaCandidate : 'mission';
    const descriptor = (0, area_1.getAreaDescriptor)(areaId);
    if (areaId === 'admin') {
        const sectionCandidate = rest[0] ?? '';
        const adminSectionId = (0, area_1.isAdminSectionId)(sectionCandidate)
            ? sectionCandidate
            : (0, area_1.getAdminSectionDescriptor)('models').id;
        return {
            areaId,
            path: normalized === '/admin' ? descriptor.defaultPath : normalized,
            adminSectionId,
            subPath: rest.slice(1).join('/'),
        };
    }
    return {
        areaId,
        path: normalized === `/${areaId}` ? descriptor.defaultPath : normalized,
        subPath: rest.join('/'),
    };
}
function resolveNavigationState(rawHash) {
    const normalized = normalizeNavigationPath(rawHash);
    const migrated = (0, migrateLegacyRoute_1.migrateLegacyRoute)(normalized);
    const selection = parseAreaSelection(migrated.newPath);
    return {
        path: selection.path,
        selection,
        migration: migrated,
    };
}
