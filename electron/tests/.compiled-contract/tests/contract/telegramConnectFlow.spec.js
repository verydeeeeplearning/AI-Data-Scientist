"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const telegramConnectFlowModel_1 = require("../../src/renderer/components/settings/telegram/telegramConnectFlowModel");
function run() {
    const initial = (0, telegramConnectFlowModel_1.createTelegramConnectFlowState)(100);
    strict_1.default.equal(initial.substep, 'ownership');
    strict_1.default.equal(initial.quickPolicy, 'critical');
    const tokenStep = (0, telegramConnectFlowModel_1.chooseTelegramBotOwnership)(initial, 'existing', 200);
    strict_1.default.equal(tokenStep.substep, 'token');
    strict_1.default.equal(tokenStep.ownershipChoice, 'existing');
    strict_1.default.equal((0, telegramConnectFlowModel_1.validateTelegramBotToken)(''), 'required');
    strict_1.default.equal((0, telegramConnectFlowModel_1.validateTelegramBotToken)('bad-token'), 'format');
    strict_1.default.equal((0, telegramConnectFlowModel_1.validateTelegramBotToken)('123456:ABCDEFGHIJKLMNOPQRST'), null);
    strict_1.default.equal((0, telegramConnectFlowModel_1.resolveTelegramTokenFailureKey)('unauthorized'), 'settings.telegramConnect.token.rejected');
    strict_1.default.equal((0, telegramConnectFlowModel_1.resolveTelegramTokenFailureKey)('network_error'), 'settings.telegramConnect.token.networkError');
    strict_1.default.equal((0, telegramConnectFlowModel_1.resolveTelegramTokenFailureKey)('api_error'), 'settings.telegramConnect.token.unknownError');
    const invalidTouched = (0, telegramConnectFlowModel_1.touchTelegramTokenEntry)((0, telegramConnectFlowModel_1.updateTelegramTokenEntry)(tokenStep, 'bad-token', 300), 400);
    strict_1.default.equal(invalidTouched.tokenTouched, true);
    strict_1.default.equal(invalidTouched.tokenError, 'format');
    strict_1.default.equal((0, telegramConnectFlowModel_1.canStartTelegramPairing)(invalidTouched), false);
    const validToken = (0, telegramConnectFlowModel_1.updateTelegramTokenEntry)(invalidTouched, '  123456:ABCDEFGHIJKLMNOPQRST  ', 500);
    strict_1.default.equal((0, telegramConnectFlowModel_1.canStartTelegramPairing)(validToken), true);
    const pairing = (0, telegramConnectFlowModel_1.markTelegramPairingStarted)(validToken, {
        handleId: 'handle-1',
        code: '428193',
        state: 'pending',
        expiresAtMs: 70000,
        botIdentity: { username: 'demo_bot' },
    }, 1000);
    strict_1.default.equal(pairing.substep, 'pairing');
    strict_1.default.equal(pairing.token, '123456:ABCDEFGHIJKLMNOPQRST');
    strict_1.default.equal(pairing.botUsername, 'demo_bot');
    strict_1.default.equal(pairing.pairingStatus, 'pending');
    strict_1.default.equal((0, telegramConnectFlowModel_1.getTelegramPairingSecondsRemaining)(pairing, 10000), 60);
    strict_1.default.equal((0, telegramConnectFlowModel_1.buildTelegramStartCommand)(pairing.pairingCode), '/pair 428193');
    strict_1.default.equal((0, telegramConnectFlowModel_1.buildTelegramBotDeepLink)(pairing.botUsername, pairing.pairingCode), 'https://t.me/demo_bot');
    const unrelatedEvent = (0, telegramConnectFlowModel_1.applyTelegramPairedEvent)(pairing, { handleId: 'other', chatId: 'chat-2', persistToken: true }, 1200);
    strict_1.default.equal(unrelatedEvent, pairing);
    const paired = (0, telegramConnectFlowModel_1.applyTelegramPairedEvent)(pairing, { handleId: 'handle-1', chatId: 'chat-1', persistToken: true }, 1300);
    strict_1.default.equal(paired.substep, 'policy');
    strict_1.default.equal(paired.pairingStatus, 'paired');
    strict_1.default.equal(paired.pairedChatId, 'chat-1');
    strict_1.default.equal(paired.persistTokenRequested, true);
    const persisted = (0, telegramConnectFlowModel_1.markTelegramTokenPersisted)(paired, 1400);
    strict_1.default.equal(persisted.tokenPersisted, true);
    strict_1.default.equal(persisted.persistTokenRequested, false);
    const expired = (0, telegramConnectFlowModel_1.applyTelegramPairingStatus)(pairing, 'expired', 1500);
    strict_1.default.equal(expired.substep, 'pairing');
    strict_1.default.equal(expired.pairingStatus, 'expired');
    const cancelled = (0, telegramConnectFlowModel_1.applyTelegramPairingStatus)(pairing, 'cancelled', 1600);
    strict_1.default.equal(cancelled.substep, 'cancelled');
    strict_1.default.equal(cancelled.cancelled, true);
    console.log('[contract] PASS telegram-connect-flow (28 cases)');
}
run();
