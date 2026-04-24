/**
 * E2E: visual surface survey over an existing Electron CDP endpoint.
 *
 * This fallback runner exists for locked-down automation environments where
 * Node child_process.spawn is blocked. PowerShell starts the backend and
 * Electron directly, then this script only connects to the already-running
 * Electron process through Chrome DevTools Protocol.
 */

import fs from 'node:fs';
import path from 'node:path';
import { chromium, type Page } from 'playwright';

async function ensureDir(target: string): Promise<void> {
  await fs.promises.mkdir(target, { recursive: true });
}

async function screenshot(page: Page, artifactsDir: string, name: string): Promise<void> {
  const target = path.join(artifactsDir, name);
  await ensureDir(path.dirname(target));
  await page.screenshot({ path: target, fullPage: true });
}

async function clickTestId(page: Page, testId: string): Promise<void> {
  const element = page.getByTestId(testId);
  await element.waitFor({ state: 'visible', timeout: 30_000 });
  await element.evaluate((node) => (node as HTMLElement).click());
}

async function firstPage(contexts: ReturnType<typeof chromium.connectOverCDP> extends Promise<infer B>
  ? B extends { contexts(): infer C }
    ? C extends Array<infer Context>
      ? Context
      : never
    : never
  : never): Promise<Page> {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    const pages = contexts.pages();
    const page = pages.find((candidate) => !candidate.url().startsWith('devtools://')) ?? pages[0];
    if (page) {
      await page.waitForLoadState('domcontentloaded').catch(() => {});
      return page;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error('No Electron renderer page was exposed over CDP.');
}

async function run(): Promise<void> {
  const port = process.env.DS_AGENT_E2E_CDP_PORT ?? '9335';
  const artifactsDir = process.env.DS_AGENT_E2E_ARTIFACTS_DIR
    ?? path.resolve(process.cwd(), '..', '.manual_verification', 'electron-e2e', 'direct-cdp');

  const browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
  try {
    const context = browser.contexts()[0];
    if (!context) {
      throw new Error('No browser context available from Electron CDP endpoint.');
    }
    const page = await firstPage(context);

    await page.getByTestId('open-settings').waitFor({ state: 'visible', timeout: 60_000 });
    await page.locator('textarea[aria-label="Chat message input"]').waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    await screenshot(page, artifactsDir, '01-chat-empty-state.png');

    await clickTestId(page, 'sidebar-tab-files');
    await page.locator('#file-explorer-title').waitFor({ state: 'visible', timeout: 30_000 });
    await page.locator('input[type="file"]').waitFor({ state: 'attached', timeout: 30_000 });
    await screenshot(page, artifactsDir, '02-files-upload-sidebar.png');

    await clickTestId(page, 'sidebar-tab-workflow');
    await page.getByTestId('work-object-panel').waitFor({ state: 'visible', timeout: 30_000 });
    await page.getByTestId('integration-settings').waitFor({ state: 'visible', timeout: 30_000 });
    await screenshot(page, artifactsDir, '03-workflow-operator-panels.png');

    await clickTestId(page, 'sidebar-tab-runtime');
    await page.getByTestId('certification-board').waitFor({ state: 'visible', timeout: 30_000 });
    await screenshot(page, artifactsDir, '04-runtime-console.png');

    await clickTestId(page, 'sidebar-tab-review');
    await page.getByTestId('decision-os-overview').waitFor({ state: 'visible', timeout: 30_000 });
    await screenshot(page, artifactsDir, '05-decision-os-review.png');

    await clickTestId(page, 'sidebar-tab-experiments');
    await page.getByTestId('metric-source-panel').waitFor({ state: 'visible', timeout: 30_000 });
    await screenshot(page, artifactsDir, '06-experiments-and-metrics.png');

    await page.getByTestId('open-settings').click();
    await page.locator('[role="dialog"][aria-labelledby="settings-title"]').waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    await screenshot(page, artifactsDir, '07-settings-dialog.png');

    await page.keyboard.press('Escape');
    await page.locator('[role="dialog"][aria-labelledby="settings-title"]').waitFor({
      state: 'hidden',
      timeout: 30_000,
    });
    await screenshot(page, artifactsDir, '08-settings-closed-return-state.png');

    console.log(`[e2e] PASS visual surface survey over CDP. Artifacts: ${artifactsDir}`);
  } finally {
    await browser.close();
  }
}

const keepAlive = setInterval(() => undefined, 1000);

run()
  .then(() => {
    clearInterval(keepAlive);
  })
  .catch((err) => {
    clearInterval(keepAlive);
    console.error('[e2e] FAIL:', err);
    process.exit(1);
  });
