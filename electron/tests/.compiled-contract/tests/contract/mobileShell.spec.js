"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const router_1 = require("../../src/mobile/router");
function run() {
    // Tab registry is exactly 5 entries, ordered.
    // Approvals is inserted between artifacts and settings so it lives in the
    // action zone of the bottom nav, not adjacent to settings overflow.
    strict_1.default.equal(router_1.MOBILE_TABS.length, 5);
    strict_1.default.deepEqual([...router_1.MOBILE_TABS], ['mission', 'runs', 'artifacts', 'approvals', 'settings']);
    // All 5 documented tabs are present.
    const valid = new Set([
        'mission',
        'runs',
        'artifacts',
        'approvals',
        'settings',
    ]);
    for (const tab of router_1.MOBILE_TABS) {
        strict_1.default.ok(valid.has(tab), `unexpected tab: ${tab}`);
    }
    console.log('[contract] PASS mobile-shell-routing (5 cases)');
}
run();
