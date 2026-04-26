/**
 * E2E: visual surface survey.
 *
 * Launches the real Electron app with the packaged backend and captures the
 * primary operator surfaces for manual review. This is intentionally a visual
 * evidence test, not a pixel-perfect regression test: assertions keep the app
 * honest enough to guarantee each screenshot is of the intended surface.
 */

import fs from 'node:fs';
import path from 'node:path';
import { captureFailureArtifacts } from '../e2e/_shared/artifacts';
import { launchApp } from '../e2e/_shared/launcher';

async function ensureDir(target: string): Promise<void> {
  await fs.promises.mkdir(target, { recursive: true });
}

async function screenshot(
  page: Awaited<ReturnType<typeof launchApp>>['page'],
  artifactsDir: string,
  name: string,
): Promise<void> {
  const target = path.join(artifactsDir, name);
  await ensureDir(path.dirname(target));
  await page.screenshot({ path: target, fullPage: true });
}

async function clickTestId(
  page: Awaited<ReturnType<typeof launchApp>>['page'],
  testId: string,
): Promise<void> {
  const element = page.getByTestId(testId);
  await element.waitFor({ state: 'visible', timeout: 30_000 });
  await element.evaluate((node) => (node as HTMLElement).click());
}

async function run(): Promise<void> {
  const { app, page, isolated } = await launchApp('visual-surface-survey', {
    extraEnv: {
      DS_AGENT_E2E_SKIP_ONBOARDING: '1',
    },
  });
  const artifactsDir = process.env.DS_AGENT_E2E_ARTIFACTS_DIR || isolated.artifacts;

  try {
    await page.getByTestId('open-settings').waitFor({ state: 'visible', timeout: 60_000 });
    await page.locator('textarea[aria-label="Chat message input"]').waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    await screenshot(page, artifactsDir, '01-chat-empty-state.png');

    await clickTestId(page, 'sidebar-tab-files');
    await page.locator('#file-explorer-title').waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    await page.locator('input[type="file"]').waitFor({
      state: 'attached',
      timeout: 30_000,
    });
    await screenshot(page, artifactsDir, '02-files-upload-sidebar.png');

    await clickTestId(page, 'sidebar-tab-workflow');
    await page.getByTestId('work-object-panel').waitFor({ state: 'visible', timeout: 30_000 });
    await page.getByTestId('integration-settings').waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    await screenshot(page, artifactsDir, '03-workflow-operator-panels.png');

    await clickTestId(page, 'sidebar-tab-runtime');
    await page.getByTestId('certification-board').waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    await screenshot(page, artifactsDir, '04-runtime-console.png');

    await clickTestId(page, 'sidebar-tab-review');
    await page.getByTestId('decision-os-overview').waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    await screenshot(page, artifactsDir, '05-decision-os-review.png');

    await clickTestId(page, 'sidebar-tab-experiments');
    await page.getByTestId('metric-source-panel').waitFor({
      state: 'visible',
      timeout: 30_000,
    });
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

    console.log(`[e2e] PASS visual surface survey. Artifacts: ${artifactsDir}`);
  } catch (err) {
    await captureFailureArtifacts(page, artifactsDir, 'visual-surface-survey').catch(() => {});
    throw err;
  } finally {
    await app.close();
  }
}

run().catch((err) => {
  console.error('[e2e] FAIL:', err);
  process.exit(1);
});
