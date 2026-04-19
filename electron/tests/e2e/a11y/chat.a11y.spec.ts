/**
 * a11y E2E: ChatPanel + ChatMessage rendering.
 *
 * MainPanel mount with skipOnboarding. Chat surface is the central panel
 * that carries the largest interactive footprint (textarea, send button,
 * tool activity timeline). axe gate covers WCAG 2.1 A + AA.
 */

import { failOnBlocking, runAxe, withApp, waitForMainSurface } from './_helpers';

async function run(): Promise<void> {
  await withApp({ skipOnboarding: true }, async (page) => {
    await waitForMainSurface(page);
    await page.locator('textarea').first().waitFor({ state: 'visible', timeout: 30_000 }).catch(() => {});
    const result = await runAxe(page);
    failOnBlocking('chat', result);
  });
}

run().catch((err) => {
  console.error('[a11y:chat] FAIL:', err);
  process.exit(1);
});
