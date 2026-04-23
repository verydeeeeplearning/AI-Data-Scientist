"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const runtime_1 = require("../../src/mobile/runtime");
function run() {
    const defaults = runtime_1.__test.parseMobileBootstrapParams('');
    strict_1.default.equal(defaults.port, 18790);
    strict_1.default.equal(defaults.token, undefined);
    const parsed = runtime_1.__test.parseMobileBootstrapParams('?port=19001&token=abc123');
    strict_1.default.equal(parsed.port, 19001);
    strict_1.default.equal(parsed.token, 'abc123');
    const invalidPort = runtime_1.__test.parseMobileBootstrapParams('?port=oops');
    strict_1.default.equal(invalidPort.port, 18790);
    const connected = runtime_1.__test.describeMobileConnection('connected', 'unknown');
    strict_1.default.equal(connected.tone, 'success');
    strict_1.default.equal(connected.labelKey, 'status.connected');
    const reconnecting = runtime_1.__test.describeMobileConnection('connecting', 'reconnecting');
    strict_1.default.equal(reconnecting.detailKey, 'connection.detail.reconnecting');
    const crashed = runtime_1.__test.describeMobileConnection('disconnected', 'backend_crashed');
    strict_1.default.equal(crashed.tone, 'danger');
    strict_1.default.equal(crashed.detailKey, 'connection.detail.backend');
    console.log('[contract] PASS mobile-bootstrap (9 cases)');
}
run();
