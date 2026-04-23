/**
 * Smoke: deep-link protocol delivery across the live Electron app.
 *
 * Uses the packaged backend and built renderer, then exercises the same
 * main-process hooks that OS protocol activation uses:
 * - Windows / Linux-style `second-instance` argv delivery
 * - macOS-style `open-url` delivery
 *
 * This verifies the live bridge up to the renderer event boundary:
 * main process -> IPC -> preload -> renderer subscriber.
 *
 * Renderer route handling remains covered by the existing deep-link
 * contract specs (`deepLinkParse.spec.ts` + `handleDeepLink.spec.ts`).
 *
 * Runner: plain Node (no @playwright/test). Exits non-zero on failure.
 */

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { _electron as electron, type ElectronApplication, type Page } from 'playwright';

const ELECTRON_DIR = process.cwd();
const REPO_ROOT = path.resolve(ELECTRON_DIR, '..');
const ELECTRON_MAIN = path.resolve(ELECTRON_DIR, 'dist', 'main', 'index.js');
const BACKEND_BIN = path.resolve(
  REPO_ROOT,
  'dist',
  'ds-agent-backend',
  process.platform === 'win32' ? 'ds-agent-api.exe' : 'ds-agent-api',
);

async function waitForRendererReady(page: Page): Promise<void> {
  await page.waitForFunction(() => window.location.hash.length > 0, undefined, {
    timeout: 60_000,
  });
  await page.waitForTimeout(500);
}

async function installDeepLinkSpy(page: Page): Promise<void> {
  await page.evaluate(() => {
    const globalWindow = window as typeof window & {
      electronAPI?: {
        deepLink?: {
          onDeepLink: (handler: (uri: string) => void) => (() => void) | undefined;
        };
      };
      __deepLinkSmokeEvents?: string[];
      __deepLinkSmokeUnsubscribe?: (() => void) | null;
    };
    if (globalWindow.__deepLinkSmokeEvents) {
      return;
    }
    globalWindow.__deepLinkSmokeEvents = [];
    globalWindow.__deepLinkSmokeUnsubscribe =
      globalWindow.electronAPI?.deepLink?.onDeepLink((uri: string) => {
        globalWindow.__deepLinkSmokeEvents?.push(uri);
      }) ?? null;
  });
}

async function waitForReceivedDeepLinks(page: Page, expectedUris: string[]): Promise<void> {
  await page.waitForFunction(
    (uris) => {
      const globalWindow = window as typeof window & {
        __deepLinkSmokeEvents?: string[];
      };
      return JSON.stringify(globalWindow.__deepLinkSmokeEvents ?? []) === JSON.stringify(uris);
    },
    expectedUris,
    { timeout: 30_000 },
  );
}

async function readReceivedDeepLinks(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const globalWindow = window as typeof window & {
      __deepLinkSmokeEvents?: string[];
    };
    return [...(globalWindow.__deepLinkSmokeEvents ?? [])];
  });
}

async function emitSecondInstance(app: ElectronApplication, argv: string[]): Promise<void> {
  await app.evaluate(({ app }: any, args: string[]) => {
    app.emit('second-instance', {}, args);
  }, argv);
}

async function emitOpenUrl(
  app: ElectronApplication,
  url: string,
): Promise<boolean> {
  return app.evaluate(({ app }: any, rawUrl: string) => {
    let prevented = false;
    app.emit(
      'open-url',
      {
        preventDefault: () => {
          prevented = true;
        },
      },
      rawUrl,
    );
    return prevented;
  }, url);
}

async function run(): Promise<void> {
  if (!fs.existsSync(BACKEND_BIN)) {
    throw new Error(
      `Backend binary not found at ${BACKEND_BIN}. ` +
        `Run "python scripts/build_backend.py" first.`,
    );
  }

  const app = await electron.launch({
    args: [ELECTRON_MAIN],
    cwd: REPO_ROOT,
    env: {
      ...process.env,
      DS_AGENT_BACKEND_COMMAND: BACKEND_BIN,
      DS_AGENT_SENTRY_DSN: '',
      DS_AGENT_E2E_USE_BUILT_RENDERER: '1',
      DS_AGENT_E2E_SKIP_ONBOARDING: '1',
    },
    timeout: 60_000,
  });

  try {
    const page = await app.firstWindow({ timeout: 60_000 });
    await page.waitForLoadState('domcontentloaded');
    await waitForRendererReady(page);
    await installDeepLinkSpy(page);

    const initialHash = await page.evaluate(() => window.location.hash);
    assert.match(initialHash, /^#\//, `expected initial hash navigation, got ${initialHash}`);

    await emitSecondInstance(app, [
      'C:\\Program Files\\DS Agent\\DS Agent.exe',
      '--from-protocol-test',
      'ds-agent://workspace/ws-legacy/run/old-run',
      'ds-agent://workspace/ws-win/run/run-42?action=compare',
    ]);
    await waitForReceivedDeepLinks(page, ['ds-agent://workspace/ws-win/run/run-42?action=compare']);

    await emitSecondInstance(app, [
      'C:\\Program Files\\DS Agent\\DS Agent.exe',
      '--from-protocol-test',
      'https://example.com/not-a-deep-link',
    ]);
    await page.waitForTimeout(500);
    assert.deepEqual(
      await readReceivedDeepLinks(page),
      ['ds-agent://workspace/ws-win/run/run-42?action=compare'],
    );

    const preventedForDeepLink = await emitOpenUrl(
      app,
      'ds-agent://workspace/ws-mac/artifact/art-7?action=promote',
    );
    assert.equal(preventedForDeepLink, true);
    await waitForReceivedDeepLinks(page, [
      'ds-agent://workspace/ws-win/run/run-42?action=compare',
      'ds-agent://workspace/ws-mac/artifact/art-7?action=promote',
    ]);

    const preventedForNonDeepLink = await emitOpenUrl(app, 'https://example.com/ignore-me');
    assert.equal(preventedForNonDeepLink, true);
    await page.waitForTimeout(500);
    assert.deepEqual(
      await readReceivedDeepLinks(page),
      [
        'ds-agent://workspace/ws-win/run/run-42?action=compare',
        'ds-agent://workspace/ws-mac/artifact/art-7?action=promote',
      ],
    );

    console.log(
      '[smoke] PASS deep-link protocol delivery (second-instance argv + open-url bridge)',
    );
  } finally {
    await app.close();
  }
}

run().catch((error) => {
  console.error('[smoke] FAIL:', error);
  process.exit(1);
});
