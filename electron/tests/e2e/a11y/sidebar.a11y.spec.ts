/**
 * a11y E2E: Sidebar (expanded + collapsed states).
 *
 * Skips onboarding to reach MainPanel. Runs axe on the default expanded
 * sidebar, then toggles collapse via Ctrl+\ and re-scans the rail variant.
 * Both states must clear WCAG 2.1 A + AA.
 */

import { failOnBlocking, runAxe, withApp, waitForMainSurface } from './_helpers';

async function run(): Promise<void> {
  await withApp({ skipOnboarding: true }, async (page) => {
    await waitForMainSurface(page);
    failOnBlocking('sidebar (expanded)', await runAxe(page));

    await page.keyboard.press('Control+\\');
    await page.waitForTimeout(750);
    failOnBlocking('sidebar (collapsed)', await runAxe(page));
  });
}

run().catch((err) => {
  console.error('[a11y:sidebar] FAIL:', err);
  process.exit(1);
});
