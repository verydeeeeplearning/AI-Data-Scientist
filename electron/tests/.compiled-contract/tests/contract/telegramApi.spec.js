"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const telegramApi_1 = require("../../src/renderer/infrastructure/api/telegramApi");
function run() {
    const handle = (0, telegramApi_1.normalizeTelegramPairingHandle)({
        handle_id: 'handle-1',
        pairing_code: '428193',
        expires_at: 1766666666,
        bot_username: 'demo_bot',
        bot_id: '123',
        first_name: 'Demo',
    });
    strict_1.default.equal(handle.handleId, 'handle-1');
    strict_1.default.equal(handle.code, '428193');
    strict_1.default.equal(handle.expiresAtMs, 1766666666000);
    strict_1.default.deepEqual(handle.botIdentity, {
        username: 'demo_bot',
        botId: 123,
        firstName: 'Demo',
    });
}
async function runAsync() {
    const calls = [];
    const rpc = async (method, params, options) => {
        calls.push({ method, params, options });
        switch (method) {
            case 'telegram.test':
                return {
                    ok: true,
                    username: 'demo_bot',
                    botId: 123,
                    firstName: 'Demo',
                };
            case 'telegram.startPairing':
                return {
                    handleId: 'handle-2',
                    code: '111222',
                    expiresAt: '1766666666',
                    botUsername: 'demo_bot',
                };
            case 'telegram.status':
                return {
                    enabled: 'true',
                    status: 'running',
                    bot_username: 'demo_bot',
                    paired: [
                        {
                            chat_id: 'chat-1',
                            first_active_at: '2026-04-26T00:00:00Z',
                            lastActiveAt: 1766666666,
                        },
                        'chat-2',
                        { chat_id: '' },
                    ],
                    last_error: '',
                };
            case 'telegram.cancelPairing':
            case 'telegram.sendTestMessage':
            case 'telegram.disconnect':
                return { ok: true };
            default:
                throw new Error(`unexpected method ${method}`);
        }
    };
    const testResult = await (0, telegramApi_1.testTelegramBot)(rpc, '123456:ABCDEFGHIJKLMNOPQRST');
    strict_1.default.equal(testResult.ok, true);
    if (testResult.ok) {
        strict_1.default.equal(testResult.botIdentity.username, 'demo_bot');
        strict_1.default.equal(testResult.botIdentity.botId, 123);
    }
    const pairing = await (0, telegramApi_1.startTelegramPairing)(rpc, '123456:ABCDEFGHIJKLMNOPQRST');
    strict_1.default.equal(pairing.handleId, 'handle-2');
    strict_1.default.equal(pairing.expiresAtMs, 1766666666000);
    const status = await (0, telegramApi_1.getTelegramStatus)(rpc);
    strict_1.default.equal(status.enabled, true);
    strict_1.default.equal(status.status, 'running');
    strict_1.default.equal(status.botIdentity?.username, 'demo_bot');
    strict_1.default.equal(status.pairedChats.length, 2);
    strict_1.default.equal(status.pairedChats[0]?.chatId, 'chat-1');
    strict_1.default.equal(status.pairedChats[0]?.firstActiveAtMs, Date.parse('2026-04-26T00:00:00Z'));
    strict_1.default.equal(status.pairedChats[0]?.lastActiveAtMs, 1766666666000);
    strict_1.default.equal(status.pairedChats[1]?.chatId, 'chat-2');
    strict_1.default.equal(status.lastError, null);
    await (0, telegramApi_1.cancelTelegramPairing)(rpc, 'handle-2');
    await (0, telegramApi_1.sendTelegramTestMessage)(rpc, 'chat-1');
    await (0, telegramApi_1.disconnectTelegram)(rpc, 'chat-1');
    await (0, telegramApi_1.disconnectTelegram)(rpc);
    strict_1.default.deepEqual(calls.map((call) => call.method), [
        'telegram.test',
        'telegram.startPairing',
        'telegram.status',
        'telegram.cancelPairing',
        'telegram.sendTestMessage',
        'telegram.disconnect',
        'telegram.disconnect',
    ]);
    strict_1.default.deepEqual(calls[0]?.params, { token: '123456:ABCDEFGHIJKLMNOPQRST' });
    strict_1.default.deepEqual(calls[3]?.params, { handleId: 'handle-2' });
    strict_1.default.deepEqual(calls[4]?.params, { chatId: 'chat-1' });
    strict_1.default.deepEqual(calls[5]?.params, { chatId: 'chat-1' });
    strict_1.default.deepEqual(calls[6]?.params, {});
    strict_1.default.equal(calls.every((call) => call.options?.timeoutMs === 15000), true);
    const failingRpc = async () => ({ ok: false, reason: 'unauthorized' });
    const failure = await (0, telegramApi_1.testTelegramBot)(failingRpc, 'bad-token');
    strict_1.default.deepEqual(failure, { ok: false, reason: 'unauthorized' });
    console.log('[contract] PASS telegram-api (34 cases)');
}
run();
void runAsync().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
