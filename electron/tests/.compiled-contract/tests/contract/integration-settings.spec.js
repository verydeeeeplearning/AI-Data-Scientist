"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
function run() {
    // Healthy connector
    const healthy = {
        system: 'slack',
        healthy: true,
        message: 'Client available.',
        latency_ms: 0.5,
    };
    strict_1.default.equal(healthy.system, 'slack');
    strict_1.default.equal(healthy.healthy, true);
    strict_1.default.equal(typeof healthy.latency_ms, 'number');
    // Unhealthy connector
    const unhealthy = {
        system: 'jira',
        healthy: false,
        message: 'No Jira client configured.',
        latency_ms: null,
    };
    strict_1.default.equal(unhealthy.healthy, false);
    strict_1.default.equal(unhealthy.latency_ms, null);
    // All-healthy check
    const connectors = [healthy, unhealthy];
    const allHealthy = connectors.every((c) => c.healthy);
    strict_1.default.equal(allHealthy, false);
    const allGood = [
        { ...healthy },
        { ...healthy, system: 'confluence' },
    ];
    strict_1.default.equal(allGood.every((c) => c.healthy), true);
    console.log('[contract] PASS integration-settings model');
}
run();
