import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import Module from 'node:module';

type ModuleLoader = (request: string, ...args: unknown[]) => unknown;

async function run(): Promise<void> {
  const userDataDir = await fs.mkdtemp(path.join(os.tmpdir(), 'ds-agent-vault-'));
  const moduleWithLoader = Module as unknown as {
    _load: ModuleLoader;
  };
  const originalLoad = moduleWithLoader._load;

  moduleWithLoader._load = ((request: string, ...args: unknown[]) => {
    if (request === 'electron') {
      return {
        app: {
          getPath: (name: string) => {
            assert.equal(name, 'userData');
            return userDataDir;
          },
        },
        safeStorage: {
          isEncryptionAvailable: () => true,
          encryptString: (value: string) => Buffer.from(`enc:${value}`, 'utf-8'),
          decryptString: (value: Buffer) => value.toString('utf-8').replace(/^enc:/, ''),
        },
      };
    }
    return originalLoad(request, ...args);
  }) as ModuleLoader;

  try {
    const vault = await import('../../src/main/secret-vault');
    const telegramToken = '123456:ABCDEFGHIJKLMNOPQRSTUVWX';

    await vault.setConfigSecret('channels.telegram.bot_token', telegramToken);
    await vault.setConfigSecret('oauth.gemini_client_secret', 'gemini-secret');

    const env = await vault.buildDesktopSecretEnv();
    assert.equal(env.DS_AGENT_TELEGRAM_BOT_TOKEN, telegramToken);
    assert.equal(env.DS_AGENT_GEMINI_CLIENT_SECRET, 'gemini-secret');

    assert.equal(await vault.clearConfigSecret('channels.telegram.bot_token'), true);
    assert.equal(await vault.clearConfigSecret('channels.telegram.bot_token'), false);

    const afterClear = await vault.buildDesktopSecretEnv();
    assert.equal(afterClear.DS_AGENT_TELEGRAM_BOT_TOKEN, undefined);
    assert.equal(afterClear.DS_AGENT_GEMINI_CLIENT_SECRET, 'gemini-secret');

    await assert.rejects(
      () => vault.setConfigSecret('channels.telegram.unknown', 'secret'),
      /Unsupported config secret/,
    );
    await assert.rejects(
      () => vault.clearConfigSecret('channels.telegram.unknown'),
      /Unsupported config secret/,
    );
  } finally {
    moduleWithLoader._load = originalLoad;
    await fs.rm(userDataDir, { recursive: true, force: true });
  }

  console.log('[contract] PASS secret-vault-config-secret (9 cases)');
}

void run().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
