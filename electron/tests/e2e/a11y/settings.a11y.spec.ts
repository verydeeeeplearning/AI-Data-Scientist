/**
 * a11y E2E: SettingsPanel modal + LocaleSelector.
 *
 * Opens the modal via Ctrl+, after MainPanel mounts. Modal must satisfy WCAG
 * 2.1 A+AA — focus trap (already validated by contract test), labels, color
 * contrast, ESC handling. axe scan runs while the modal is open.
 */

import { failOnBlocking, runAxe, withApp, waitForMainSurface } from './_helpers';

async function run(): Promise<void> {
  await withApp({ skipOnboarding: true }, async (page) => {
    await waitForMainSurface(page);
    await page.keyboard.press('Control+,');
    await page.waitForTimeout(750);
    const result = await runAxe(page);
    failOnBlocking('settings', result);
  });
}

run().catch((err) => {
  console.error('[a11y:settings] FAIL:', err);
  process.exit(1);
});
