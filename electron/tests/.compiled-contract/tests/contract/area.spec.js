"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const area_1 = require("../../src/renderer/domain/navigation/area");
function run() {
    strict_1.default.equal(area_1.DEFAULT_AREA_PATH, '/mission');
    strict_1.default.equal(area_1.AREA_DESCRIPTORS.length, 6);
    strict_1.default.equal(area_1.ADMIN_SECTION_DESCRIPTORS.length, 4);
    strict_1.default.equal((0, area_1.isAreaId)('mission'), true);
    strict_1.default.equal((0, area_1.isAreaId)('unknown'), false);
    strict_1.default.equal((0, area_1.isAdminSectionId)('models'), true);
    strict_1.default.equal((0, area_1.isAdminSectionId)('review'), false);
    strict_1.default.equal((0, area_1.getAreaDescriptor)('artifacts').defaultPath, '/artifacts/files');
    strict_1.default.equal((0, area_1.getAreaDescriptor)('admin').shortcut, 'mod+,');
    strict_1.default.equal((0, area_1.getAdminSectionDescriptor)('connectors').defaultPath, '/admin/connectors');
    console.log('[contract] PASS area (8 cases)');
}
run();
