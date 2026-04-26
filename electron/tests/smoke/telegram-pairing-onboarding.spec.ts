/**
 * Smoke: first-run onboarding Telegram pairing.
 *
 * Uses a fixture backend through DS_AGENT_BACKEND_COMMAND so the test covers
 * Electron startup, renderer WebSocket RPCs, the onboarding notify step, and
 * telegram.paired event handling without requiring a real BotFather token.
 */

import path from 'node:path';
import { type Locator, type Page } from 'playwright';
import { captureFailureArtifacts } from '../e2e/_shared/artifacts';
import { launchApp } from '../e2e/_shared/launcher';

const TELEGRAM_TOKEN = '123456:ABCDEFGHIJKLMNOPQRSTuvwx';

function fixtureBackendPath(): string {
  return path.resolve(
    __dirname,
    '..',
    '..',
    'smoke',
    'fixtures',
    'telegram-fake-backend.js',
  );
}

async function clickVisible(locator: Locator): Promise<void> {
  await locator.waitFor({ state: 'visible', timeout: 30_000 });
  await locator.evaluate((element) => {
    element.scrollIntoView({ block: 'center', inline: 'nearest' });
  });
  await locator.evaluate((element) => {
    (element as HTMLButtonElement).click();
  });
}

function currentContinueSection(page: Page): Locator {
  return page
    .getByRole('button', { name: /^Continue$/ })
    .last()
    .locator('xpath=ancestor::div[contains(@class,"rounded-2xl")][1]');
}

async function clickContinue(page: Page): Promise<void> {
  const button = page.getByRole('button', { name: /^Continue$/ }).last();
  await button.waitFor({ state: 'visible', timeout: 30_000 });
  await clickVisible(button);
}

async function waitForOnboarding(page: Page): Promise<void> {
  await page.getByRole('heading', { name: /^DS Agent$/ }).waitFor({
    state: 'visible',
    timeout: 60_000,
  });
  const localeSelector = page.locator('#locale-selector');
  if (await localeSelector.isVisible().catch(() => false)) {
    await localeSelector.selectOption('en');
  }
  await page.getByRole('heading', {
    name: /What do you want the agent to help with most often/i,
  }).waitFor({ state: 'visible', timeout: 60_000 });
}

async function completeSetupBeforeNotify(page: Page): Promise<void> {
  await clickVisible(page.getByRole('button', { name: /Build a prediction/i }).first());
  await clickContinue(page);

  await page.getByRole('heading', { name: /How will the first analysis start/i }).waitFor({
    state: 'visible',
    timeout: 30_000,
  });
  await clickVisible(currentContinueSection(page).getByRole('button').nth(0));
  await clickContinue(page);

  await clickContinue(page);
  await clickContinue(page);

  await page.getByRole('button', { name: /Local Test Model/i }).waitFor({
    state: 'visible',
    timeout: 60_000,
  });
  await clickVisible(page.getByRole('button', { name: /Local Test Model/i }).first());
  await clickContinue(page);
}

async function completeTelegramPairing(page: Page): Promise<void> {
  await page.getByRole('heading', { name: /Where should runtime updates go/i }).waitFor({
    state: 'visible',
    timeout: 30_000,
  });

  await clickVisible(page.getByRole('button', { name: /Use Telegram/i }).first());
  await page.getByRole('button', { name: /I already have a token/i }).waitFor({
    state: 'visible',
    timeout: 30_000,
  });
  await clickVisible(page.getByRole('button', { name: /I already have a token/i }).first());

  await page.getByLabel(/Bot token/i).fill(TELEGRAM_TOKEN);
  await clickVisible(page.getByRole('button', { name: /Start Pairing/i }).first());

  await page.getByText('/pair 428193', { exact: true }).waitFor({
    state: 'visible',
    timeout: 30_000,
  });
  await page.getByText('Connection confirmed', { exact: true }).waitFor({
    state: 'visible',
    timeout: 30_000,
  });

  const setup = page.getByLabel(/Telegram connection setup/i);
  await clickVisible(setup.getByRole('button', { name: /^Finish$/ }).first());
}

async function finishOnboarding(page: Page): Promise<void> {
  await page.getByRole('heading', { name: /Confirm the mission handoff/i }).waitFor({
    state: 'visible',
    timeout: 30_000,
  });
  await clickVisible(page.getByRole('button', { name: /Keep both off/i }).first());

  const finalizeResponse = page.waitForResponse(
    (response) =>
      response.url().includes('/api/onboarding/finalize')
      && response.request().method() === 'POST',
    { timeout: 60_000 },
  );
  await clickVisible(page.getByRole('button', { name: /^Start DS Agent$/ }).first());

  const response = await finalizeResponse;
  if (!response.ok()) {
    throw new Error(
      `Onboarding finalize failed with status ${response.status()}: ${await response.text()}`,
    );
  }
}

async function waitForMainSurface(page: Page): Promise<void> {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    const artifactsVisible = await page.getByTestId('area-nav-artifacts').isVisible().catch(() => false);
    const adminVisible = await page.getByTestId('area-nav-admin').isVisible().catch(() => false);
    if (artifactsVisible || adminVisible) {
      return;
    }
    await page.waitForTimeout(500);
  }
  throw new Error('Main surface did not appear after Telegram onboarding.');
}

async function assertTelegramConnected(page: Page): Promise<void> {
  await page.getByText('Telegram connected').waitFor({
    state: 'visible',
    timeout: 30_000,
  });
}

async function run(): Promise<void> {
  const { app, page, isolated } = await launchApp('telegram-onboarding', {
    skipBinaryCheck: true,
    extraEnv: {
      DS_AGENT_BACKEND_COMMAND: process.execPath,
      DS_AGENT_BACKEND_ARGS: fixtureBackendPath(),
      DS_AGENT_E2E_DISABLE_CHROMIUM_SANDBOX: '1',
    },
  });

  try {
    await waitForOnboarding(page);
    await completeSetupBeforeNotify(page);
    await completeTelegramPairing(page);
    await finishOnboarding(page);
    await waitForMainSurface(page);
    await assertTelegramConnected(page);

    const diagnosticHit = await page.locator('#diagnostic-title').count();
    if (diagnosticHit > 0) {
      throw new Error('Diagnostic window appeared during Telegram onboarding smoke.');
    }

    console.log('[smoke] PASS Telegram onboarding pairing flow reached connected main UI.');
  } catch (error) {
    await captureFailureArtifacts(page, isolated.artifacts, 'telegram-onboarding').catch(() => {});
    throw error;
  } finally {
    await app.close();
  }
}

run().catch((error) => {
  console.error('[smoke] FAIL:', error);
  process.exit(1);
});
