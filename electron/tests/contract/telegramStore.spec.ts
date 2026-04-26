import assert from 'node:assert/strict';

import { useTelegramStore } from '../../src/renderer/stores/telegramStore';
import type { RpcFn } from '../../src/renderer/components/settings/types';

interface RpcCall {
  method: string;
  params?: Record<string, unknown>;
}

async function run(): Promise<void> {
  const calls: RpcCall[] = [];
  const rpc: RpcFn = async (method, params) => {
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
          expiresAt: 1_766_666_666,
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

  useTelegramStore.getState().resetTelegram();

  const testResult = await useTelegramStore
    .getState()
    .testToken(rpc, 'bad-token');
  assert.deepEqual(testResult, { ok: false, reason: 'unauthorized' });
  assert.equal(useTelegramStore.getState().error, 'unauthorized');
  assert.equal(useTelegramStore.getState().loading, false);

  const handle = await useTelegramStore
    .getState()
    .startPairing(rpc, '123456:ABCDEFGHIJKLMNOPQRST');
  assert.equal(handle.handleId, 'handle-1');
  assert.equal(useTelegramStore.getState().enabled, true);
  assert.equal(useTelegramStore.getState().status, 'starting');
  assert.equal(useTelegramStore.getState().botIdentity?.username, 'demo_bot');
  assert.equal(useTelegramStore.getState().pairing?.code, '428193');
  assert.equal(useTelegramStore.getState().pairing?.state, 'pending');

  useTelegramStore.getState().applyPairedEvent({
    handleId: 'handle-1',
    chatId: 'chat-1',
  });

  assert.equal(useTelegramStore.getState().pairing?.state, 'paired');
  assert.equal(useTelegramStore.getState().pairing?.chatId, 'chat-1');
  assert.equal(useTelegramStore.getState().pairedChat?.chatId, 'chat-1');
  assert.equal(useTelegramStore.getState().status, 'starting');

  const pairingStatus = await useTelegramStore.getState().refreshPairingStatus(rpc);
  assert.equal(pairingStatus, 'paired');
  assert.deepEqual(calls.at(-1), {
    method: 'telegram.pairingStatus',
    params: { handleId: 'handle-1' },
  });

  const status = await useTelegramStore.getState().refreshStatus(rpc);
  assert.equal(status.status, 'running');
  assert.equal(useTelegramStore.getState().status, 'running');
  assert.equal(useTelegramStore.getState().pairedChat?.chatId, 'chat-1');

  await useTelegramStore.getState().sendTestMessage(rpc);
  assert.deepEqual(calls.at(-1), {
    method: 'telegram.sendTestMessage',
    params: { chatId: 'chat-1' },
  });

  await useTelegramStore.getState().cancelPairing(rpc);
  assert.equal(useTelegramStore.getState().pairing?.state, 'cancelled');
  assert.deepEqual(calls.at(-1), {
    method: 'telegram.cancelPairing',
    params: { handleId: 'handle-1' },
  });

  await useTelegramStore.getState().reconnect(rpc);
  assert.equal(useTelegramStore.getState().status, 'running');
  assert.deepEqual(calls.slice(-2).map((call) => call.method), [
    'telegram.reconnect',
    'telegram.status',
  ]);

  await useTelegramStore.getState().disconnect(rpc, 'chat-1');
  assert.equal(useTelegramStore.getState().pairedChat, null);
  assert.equal(useTelegramStore.getState().enabled, false);
  assert.equal(useTelegramStore.getState().status, 'disabled');

  useTelegramStore.getState().applyStatusEvent({
    enabled: true,
    status: 'error',
    botUsername: 'demo_bot',
    lastError: 'network_error',
  });
  assert.equal(useTelegramStore.getState().status, 'error');
  assert.equal(useTelegramStore.getState().lastError, 'network_error');
  assert.equal(useTelegramStore.getState().error, 'network_error');

  useTelegramStore.getState().resetTelegram();
  assert.equal(useTelegramStore.getState().enabled, false);
  assert.equal(useTelegramStore.getState().pairing, null);

  console.log('[contract] PASS telegram-store (31 cases)');
}

void run().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
