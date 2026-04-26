import assert from 'node:assert/strict';

import {
  applyTelegramPairedEvent,
  applyTelegramPairingStatus,
  buildTelegramBotDeepLink,
  buildTelegramStartCommand,
  canStartTelegramPairing,
  chooseTelegramBotOwnership,
  createTelegramConnectFlowState,
  getTelegramPairingSecondsRemaining,
  markTelegramPairingStarted,
  markTelegramTokenPersisted,
  resolveTelegramTokenFailureKey,
  touchTelegramTokenEntry,
  updateTelegramTokenEntry,
  validateTelegramBotToken,
} from '../../src/renderer/components/settings/telegram/telegramConnectFlowModel';

function run(): void {
  const initial = createTelegramConnectFlowState(100);
  assert.equal(initial.substep, 'ownership');
  assert.equal(initial.quickPolicy, 'critical');

  const tokenStep = chooseTelegramBotOwnership(initial, 'existing', 200);
  assert.equal(tokenStep.substep, 'token');
  assert.equal(tokenStep.ownershipChoice, 'existing');

  assert.equal(validateTelegramBotToken(''), 'required');
  assert.equal(validateTelegramBotToken('bad-token'), 'format');
  assert.equal(validateTelegramBotToken('123456:ABCDEFGHIJKLMNOPQRST'), null);
  assert.equal(
    resolveTelegramTokenFailureKey('unauthorized'),
    'settings.telegramConnect.token.rejected',
  );
  assert.equal(
    resolveTelegramTokenFailureKey('network_error'),
    'settings.telegramConnect.token.networkError',
  );
  assert.equal(
    resolveTelegramTokenFailureKey('api_error'),
    'settings.telegramConnect.token.unknownError',
  );

  const invalidTouched = touchTelegramTokenEntry(
    updateTelegramTokenEntry(tokenStep, 'bad-token', 300),
    400,
  );
  assert.equal(invalidTouched.tokenTouched, true);
  assert.equal(invalidTouched.tokenError, 'format');
  assert.equal(canStartTelegramPairing(invalidTouched), false);

  const validToken = updateTelegramTokenEntry(
    invalidTouched,
    '  123456:ABCDEFGHIJKLMNOPQRST  ',
    500,
  );
  assert.equal(canStartTelegramPairing(validToken), true);

  const pairing = markTelegramPairingStarted(
    validToken,
    {
      handleId: 'handle-1',
      code: '428193',
      state: 'pending',
      expiresAtMs: 70_000,
      botIdentity: { username: 'demo_bot' },
    },
    1_000,
  );
  assert.equal(pairing.substep, 'pairing');
  assert.equal(pairing.token, '123456:ABCDEFGHIJKLMNOPQRST');
  assert.equal(pairing.botUsername, 'demo_bot');
  assert.equal(pairing.pairingStatus, 'pending');
  assert.equal(getTelegramPairingSecondsRemaining(pairing, 10_000), 60);
  assert.equal(buildTelegramStartCommand(pairing.pairingCode), '/pair 428193');
  assert.equal(buildTelegramBotDeepLink(pairing.botUsername, pairing.pairingCode), 'https://t.me/demo_bot');

  const unrelatedEvent = applyTelegramPairedEvent(
    pairing,
    { handleId: 'other', chatId: 'chat-2', persistToken: true },
    1_200,
  );
  assert.equal(unrelatedEvent, pairing);

  const paired = applyTelegramPairedEvent(
    pairing,
    { handleId: 'handle-1', chatId: 'chat-1', persistToken: true },
    1_300,
  );
  assert.equal(paired.substep, 'policy');
  assert.equal(paired.pairingStatus, 'paired');
  assert.equal(paired.pairedChatId, 'chat-1');
  assert.equal(paired.persistTokenRequested, true);

  const persisted = markTelegramTokenPersisted(paired, 1_400);
  assert.equal(persisted.tokenPersisted, true);
  assert.equal(persisted.persistTokenRequested, false);

  const expired = applyTelegramPairingStatus(pairing, 'expired', 1_500);
  assert.equal(expired.substep, 'pairing');
  assert.equal(expired.pairingStatus, 'expired');

  const cancelled = applyTelegramPairingStatus(pairing, 'cancelled', 1_600);
  assert.equal(cancelled.substep, 'cancelled');
  assert.equal(cancelled.cancelled, true);

  console.log('[contract] PASS telegram-connect-flow (28 cases)');
}

run();
