"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const useCanMutate_1 = require("../../src/renderer/hooks/useCanMutate");
function run() {
    const ownerOutcome = (0, useCanMutate_1.resolveCanMutate)('owner');
    strict_1.default.equal(ownerOutcome.role, 'owner');
    strict_1.default.equal(ownerOutcome.canMutate, true);
    strict_1.default.equal(ownerOutcome.reason, undefined);
    const viewerOutcome = (0, useCanMutate_1.resolveCanMutate)('viewer');
    strict_1.default.equal(viewerOutcome.role, 'viewer');
    strict_1.default.equal(viewerOutcome.canMutate, false);
    strict_1.default.equal(viewerOutcome.reason, 'share.banner.readOnlyTooltip');
    // reason is a stable i18n key, not a translated literal — call sites bind
    // it to tooltips on disabled controls.
    strict_1.default.equal(typeof viewerOutcome.reason, 'string');
    strict_1.default.equal(viewerOutcome.reason.startsWith('share.'), true);
    console.log('[contract] PASS use-can-mutate (7 cases)');
}
run();
