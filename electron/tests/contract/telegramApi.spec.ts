import assert from 'node:assert/strict';

import {
  cancelTelegramPairing,
  disconnectTelegram,
  getTelegramStatus,
  normalizeTelegramPairingHandle,
  sendTelegramTestMessage,
  startTelegramPairing,
  testTelegramBot,
} from '../../src/renderer/infrastructure/api/telegramApi';
import type { RpcFn } from '../../src/renderer/components/settings/types';

interface RpcCall {
  method: string;
  params?: Record<string, unknown>;
  options?: { timeoutMs?: number };
}

function run(): void {
  const handle = normalizeTelegramPairingHandle({
    handle_id: 'handle-1',
    pairing_code: '428193',
    expires_at: 1_766_666_666,
    bot_username: 'demo_bot',
    bot_id: '123',
    first_name: 'Demo',
  });

  assert.equal(handle.handleId, 'handle-1');
  assert.equal(handle.code, '428193');
  assert.equal(handle.expiresAtMs, 1_766_666_666_000);
  assert.deepEqual(handle.botIdentity, {
    username: 'demo_bot',
    botId: 123,
    firstName: 'Demo',
  });
}

async function runAsync(): Promise<void> {
  const calls: RpcCall[] = [];
  const rpc: RpcFn = async (method, params, options) => {
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
              lastActiveAt: 1_766_666_666,
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

  const testResult = await testTelegramBot(rpc, '123456:ABCDEFGHIJKLMNOPQRST');
  assert.equal(testResult.ok, true);
  if (testResult.ok) {
    assert.equal(testResult.botIdentity.username, 'demo_bot');
    assert.equal(testResult.botIdentity.botId, 123);
  }

  const pairing = await startTelegramPairing(rpc, '123456:ABCDEFGHIJKLMNOPQRST');
  assert.equal(pairing.handleId, 'handle-2');
  assert.equal(pairing.expiresAtMs, 1_766_666_666_000);

  const status = await getTelegramStatus(rpc);
  assert.equal(status.enabled, true);
  assert.equal(status.status, 'running');
  assert.equal(status.botIdentity?.username, 'demo_bot');
  assert.equal(status.pairedChats.length, 2);
  assert.equal(status.pairedChats[0]?.chatId, 'chat-1');
  assert.equal(status.pairedChats[0]?.firstActiveAtMs, Date.parse('2026-04-26T00:00:00Z'));
  assert.equal(status.pairedChats[0]?.lastActiveAtMs, 1_766_666_666_000);
  assert.equal(status.pairedChats[1]?.chatId, 'chat-2');
  assert.equal(status.lastError, null);

  await cancelTelegramPairing(rpc, 'handle-2');
  await sendTelegramTestMessage(rpc, 'chat-1');
  await disconnectTelegram(rpc, 'chat-1');
  await disconnectTelegram(rpc);

  assert.deepEqual(calls.map((call) => call.method), [
    'telegram.test',
    'telegram.startPairing',
    'telegram.status',
    'telegram.cancelPairing',
    'telegram.sendTestMessage',
    'telegram.disconnect',
    'telegram.disconnect',
  ]);
  assert.deepEqual(calls[0]?.params, { token: '123456:ABCDEFGHIJKLMNOPQRST' });
  assert.deepEqual(calls[3]?.params, { handleId: 'handle-2' });
  assert.deepEqual(calls[4]?.params, { chatId: 'chat-1' });
  assert.deepEqual(calls[5]?.params, { chatId: 'chat-1' });
  assert.deepEqual(calls[6]?.params, {});
  assert.equal(calls.every((call) => call.options?.timeoutMs === 15_000), true);

  const failingRpc: RpcFn = async () => ({ ok: false, reason: 'unauthorized' });
  const failure = await testTelegramBot(failingRpc, 'bad-token');
  assert.deepEqual(failure, { ok: false, reason: 'unauthorized' });

  console.log('[contract] PASS telegram-api (34 cases)');
}

run();
void runAsync().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
