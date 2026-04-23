"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const useAccessRole_1 = require("../../src/renderer/hooks/useAccessRole");
function run() {
    // sole-user mode → owner (default product behavior)
    strict_1.default.equal((0, useAccessRole_1.resolveAccessRole)(undefined, true), 'owner');
    // forceRole=viewer overrides sole-user (testing UI viewer state)
    strict_1.default.equal((0, useAccessRole_1.resolveAccessRole)('viewer', true), 'viewer');
    // explicit owner forceRole preserved
    strict_1.default.equal((0, useAccessRole_1.resolveAccessRole)('owner', false), 'owner');
    // non-sole-user defaults to owner today (future v2 will resolve from auth context)
    strict_1.default.equal((0, useAccessRole_1.resolveAccessRole)(undefined, false), 'owner');
    // ViewerRole literal type sanity
    const owner = 'owner';
    const viewer = 'viewer';
    strict_1.default.equal(owner === 'owner', true);
    strict_1.default.equal(viewer === 'viewer', true);
    console.log('[contract] PASS use-access-role (6 cases)');
}
run();
