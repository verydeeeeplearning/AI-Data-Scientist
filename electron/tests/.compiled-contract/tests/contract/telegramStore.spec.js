"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const telegramStore_1 = require("../../src/renderer/stores/telegramStore");
async function run() {
    const calls = [];
    const rpc = async (method, params) => {
        calls.push({ method, params });
        switch (method) {
            case 'telegram.test':
                return {
                    ok: false,
                    reason: 'unauthorized',
                };
            case 'telegram.startPairing':
                return {
                    handleId: 'handle-1',
                    code: '428193',
                    expiresAt: 1766666666,
                    botUsername: 'demo_bot',
                    botId: 123,
                    firstName: 'Demo',
                };
            case 'telegram.pairingStatus':
                return { state: 'paired' };
            case 'telegram.status':
                return {
                    enabled: true,
                    status: 'running',
                    botUsername: 'demo_bot',
                    paired: [{ chatId: 'chat-1' }],
                    lastError: null,
                };
            case 'telegram.sendTestMessage':
            case 'telegram.disconnect':
            case 'telegram.cancelPairing':
                return { ok: true };
            case 'telegram.reconnect':
                return { ok: true };
            default:
                throw new Error(`unexpected method ${method}`);
        }
    };
    telegramStore_1.useTelegramStore.getState().resetTelegram();
    const testResult = await telegramStore_1.useTelegramStore
        .getState()
        .testToken(rpc, 'bad-token');
    strict_1.default.deepEqual(testResult, { ok: false, reason: 'unauthorized' });
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().error, 'unauthorized');
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().loading, false);
    const handle = await telegramStore_1.useTelegramStore
        .getState()
        .startPairing(rpc, '123456:ABCDEFGHIJKLMNOPQRST');
    strict_1.default.equal(handle.handleId, 'handle-1');
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().enabled, true);
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().status, 'starting');
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().botIdentity?.username, 'demo_bot');
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().pairing?.code, '428193');
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().pairing?.state, 'pending');
    telegramStore_1.useTelegramStore.getState().applyPairedEvent({
        handleId: 'handle-1',
        chatId: 'chat-1',
    });
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().pairing?.state, 'paired');
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().pairing?.chatId, 'chat-1');
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().pairedChat?.chatId, 'chat-1');
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().status, 'starting');
    const pairingStatus = await telegramStore_1.useTelegramStore.getState().refreshPairingStatus(rpc);
    strict_1.default.equal(pairingStatus, 'paired');
    strict_1.default.deepEqual(calls.at(-1), {
        method: 'telegram.pairingStatus',
        params: { handleId: 'handle-1' },
    });
    const status = await telegramStore_1.useTelegramStore.getState().refreshStatus(rpc);
    strict_1.default.equal(status.status, 'running');
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().status, 'running');
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().pairedChat?.chatId, 'chat-1');
    await telegramStore_1.useTelegramStore.getState().sendTestMessage(rpc);
    strict_1.default.deepEqual(calls.at(-1), {
        method: 'telegram.sendTestMessage',
        params: { chatId: 'chat-1' },
    });
    await telegramStore_1.useTelegramStore.getState().cancelPairing(rpc);
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().pairing?.state, 'cancelled');
    strict_1.default.deepEqual(calls.at(-1), {
        method: 'telegram.cancelPairing',
        params: { handleId: 'handle-1' },
    });
    await telegramStore_1.useTelegramStore.getState().reconnect(rpc);
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().status, 'running');
    strict_1.default.deepEqual(calls.slice(-2).map((call) => call.method), [
        'telegram.reconnect',
        'telegram.status',
    ]);
    await telegramStore_1.useTelegramStore.getState().disconnect(rpc, 'chat-1');
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().pairedChat, null);
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().enabled, false);
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().status, 'disabled');
    telegramStore_1.useTelegramStore.getState().applyStatusEvent({
        enabled: true,
        status: 'error',
        botUsername: 'demo_bot',
        lastError: 'network_error',
    });
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().status, 'error');
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().lastError, 'network_error');
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().error, 'network_error');
    telegramStore_1.useTelegramStore.getState().resetTelegram();
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().enabled, false);
    strict_1.default.equal(telegramStore_1.useTelegramStore.getState().pairing, null);
    console.log('[contract] PASS telegram-store (31 cases)');
}
void run().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
