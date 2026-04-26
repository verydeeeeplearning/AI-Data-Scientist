"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const pushPayload_1 = require("../../src/mobile/sw/pushPayload");
function run() {
    const normalized = (0, pushPayload_1.normalizePushNotification)({
        title: 'Approve run',
        body: 'A queued action needs review',
        data: {
            deepLink: 'ds-agent://run/r-1',
            category: 'approval',
        },
    });
    strict_1.default.equal(normalized.title, 'Approve run');
    strict_1.default.equal(normalized.body, 'A queued action needs review');
    strict_1.default.equal(normalized.deepLink, 'ds-agent://run/r-1');
    strict_1.default.equal(normalized.tag, 'ds-agent-approval');
    const fallback = (0, pushPayload_1.normalizePushNotification)(null);
    strict_1.default.equal(fallback.title, 'DS Agent');
    strict_1.default.match(fallback.body, /DS Agent/);
    strict_1.default.equal(fallback.deepLink, null);
    strict_1.default.equal(fallback.tag, 'ds-agent-notification');
    strict_1.default.equal((0, pushPayload_1.resolveNotificationClickTarget)({ deepLink: 'ds-agent://workspace/ws-1' }), 'ds-agent://workspace/ws-1');
    strict_1.default.equal((0, pushPayload_1.resolveNotificationClickTarget)({}, './'), './');
    console.log('[contract] PASS mobile-push-notification (4 cases)');
}
run();
