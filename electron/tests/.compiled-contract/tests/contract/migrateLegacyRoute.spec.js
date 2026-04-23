"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const migrateLegacyRoute_1 = require("../../src/renderer/application/navigation/migrateLegacyRoute");
function run() {
    {
        const result = (0, migrateLegacyRoute_1.migrateLegacyRoute)('/workflow');
        strict_1.default.equal(result.newPath, '/mission');
        strict_1.default.equal(result.migratedFrom, '/workflow');
        strict_1.default.equal(result.showMigrationToast, true);
    }
    {
        const result = (0, migrateLegacyRoute_1.migrateLegacyRoute)('/files');
        strict_1.default.equal(result.newPath, '/artifacts/files');
        strict_1.default.equal(result.showMigrationToast, true);
    }
    {
        const result = (0, migrateLegacyRoute_1.migrateLegacyRoute)('/settings');
        strict_1.default.equal(result.newPath, '/admin/settings');
    }
    {
        const result = (0, migrateLegacyRoute_1.migrateLegacyRoute)('/mission');
        strict_1.default.equal(result.newPath, '/mission');
        strict_1.default.equal(result.showMigrationToast, false);
    }
    console.log('[contract] PASS migrate-legacy-route (4 cases)');
}
run();
