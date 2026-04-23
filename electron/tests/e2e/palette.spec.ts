import assert from 'node:assert/strict';

import { withApp, waitForMainSurface } from './a11y/_helpers';

async function waitForLiveRegionText(page: any): Promise<string> {
  await page.waitForFunction(() => {
    const region = document.getElementById('ds-a11y-live-region');
    return Boolean(region && region.textContent && region.textContent.trim().length > 0);
  });

  return (await page.locator('#ds-a11y-live-region').textContent()) ?? '';
}

async function openPalette(page: any): Promise<any> {
  const dialog = page.getByRole('dialog');

  await page.keyboard.press('Control+K');
  try {
    await dialog.waitFor({ state: 'visible', timeout: 5_000 });
    return dialog;
  } catch {
    await page.evaluate(() => {
      const eventInit = {
        key: 'k',
        code: 'KeyK',
        ctrlKey: true,
        bubbles: true,
        cancelable: true,
      };
      const keyboardEvent = new KeyboardEvent('keydown', eventInit);
      document.activeElement?.dispatchEvent(keyboardEvent);
      document.dispatchEvent(new KeyboardEvent('keydown', eventInit));
      window.dispatchEvent(new KeyboardEvent('keydown', eventInit));
    });
    try {
      await dialog.waitFor({ state: 'visible', timeout: 5_000 });
    } catch {
      await page.evaluate(() => {
        window.dispatchEvent(new CustomEvent('ds-agent:open-command-palette'));
      });
      await dialog.waitFor({ state: 'visible', timeout: 30_000 });
    }
    return dialog;
  }
}

async function run(): Promise<void> {
  await withApp({ skipOnboarding: true }, async (page) => {
    await waitForMainSurface(page);
    await page.evaluate(() => {
      window.localStorage.setItem('ds-agent-feature-ia-v2', 'true');
    });
    await page.reload({ waitUntil: 'domcontentloaded' });
    await waitForMainSurface(page);

    const focusTarget = page.locator('textarea').first();
    await focusTarget.waitFor({ state: 'visible', timeout: 30_000 });
    await focusTarget.click();

    const dialog = await openPalette(page);

    const input = dialog.locator('input').first();
    await input.waitFor({ state: 'visible', timeout: 30_000 });
    await input.fill('/model openai/gpt-4.1');
    await input.press('Enter');

    const modelAnnouncement = (await waitForLiveRegionText(page)).toLowerCase();
    assert.ok(
      modelAnnouncement.includes('/model openai/gpt-4.1') || modelAnnouncement.includes('openai/gpt-4.1'),
      `expected aria-live announcement to preserve typed slash arguments, got: ${modelAnnouncement}`,
    );

    await dialog.waitFor({ state: 'hidden', timeout: 30_000 });
    assert.equal(
      await focusTarget.evaluate((element: HTMLElement) => document.activeElement === element),
      true,
    );

    await openPalette(page);

    const reopenedInput = dialog.locator('input').first();
    await reopenedInput.fill('/clear');
    await reopenedInput.press('Enter');

    const cliOnlyAnnouncement = (await waitForLiveRegionText(page)).toLowerCase();
    assert.ok(
      cliOnlyAnnouncement.includes('/clear') || cliOnlyAnnouncement.includes('cli only'),
      `expected aria-live announcement to explain CLI-only slash unavailability, got: ${cliOnlyAnnouncement}`,
    );

    await dialog.waitFor({ state: 'visible', timeout: 30_000 });
    assert.equal(
      await reopenedInput.evaluate((element: HTMLElement) => document.activeElement === element),
      true,
    );

    await reopenedInput.press('Escape');
    await dialog.waitFor({ state: 'hidden', timeout: 30_000 });
    assert.equal(
      await focusTarget.evaluate((element: HTMLElement) => document.activeElement === element),
      true,
    );
  });
}

run().catch((error) => {
  console.error('[e2e:palette] FAIL:', error);
  process.exit(1);
});
