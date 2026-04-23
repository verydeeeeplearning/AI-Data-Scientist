"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const resolveNavigationState_1 = require("../../src/renderer/application/navigation/resolveNavigationState");
function run() {
    strict_1.default.equal((0, resolveNavigationState_1.normalizeNavigationPath)(''), '/mission');
    strict_1.default.equal((0, resolveNavigationState_1.normalizeNavigationPath)('#artifacts/files'), '/artifacts/files');
    strict_1.default.equal((0, resolveNavigationState_1.buildNavigationHash)('/runs'), '#/runs');
    {
        const selection = (0, resolveNavigationState_1.parseAreaSelection)('/admin');
        strict_1.default.equal(selection.areaId, 'admin');
        strict_1.default.equal(selection.path, '/admin/models');
        strict_1.default.equal(selection.adminSectionId, 'models');
    }
    {
        const selection = (0, resolveNavigationState_1.parseAreaSelection)('/memory/learning');
        strict_1.default.equal(selection.areaId, 'memory');
        strict_1.default.equal(selection.subPath, 'learning');
    }
    {
        const selection = (0, resolveNavigationState_1.parseAreaSelection)('/governance/approvals/appr-77');
        strict_1.default.equal(selection.areaId, 'governance');
        strict_1.default.equal(selection.path, '/governance/approvals/appr-77');
        strict_1.default.equal(selection.subPath, 'approvals/appr-77');
    }
    {
        const state = (0, resolveNavigationState_1.resolveNavigationState)('#/workflow');
        strict_1.default.equal(state.path, '/mission');
        strict_1.default.equal(state.selection.areaId, 'mission');
        strict_1.default.equal(state.migration.migratedFrom, '/workflow');
    }
    console.log('[contract] PASS resolve-navigation-state (7 cases)');
}
run();
