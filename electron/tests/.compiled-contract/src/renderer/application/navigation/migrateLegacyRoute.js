"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.migrateLegacyRoute = migrateLegacyRoute;
const LEGACY_ROUTE_MAP = {
    '/files': '/artifacts/files',
    '/workflow': '/mission',
    '/workflow/runs': '/runs',
    '/review': '/governance/review',
    '/runtime': '/runs',
    '/experiments': '/artifacts/experiments',
    '/portfolio': '/artifacts/portfolio',
    '/learning': '/memory/learning',
    '/settings': '/admin/settings',
};
function migrateLegacyRoute(path) {
    const mapped = LEGACY_ROUTE_MAP[path];
    if (!mapped) {
        return { newPath: path, showMigrationToast: false };
    }
    return {
        newPath: mapped,
        migratedFrom: path,
        showMigrationToast: true,
    };
}
