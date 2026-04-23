/**
 * a11y E2E: Governance + runs area panels.
 *
 * Starts from the post-onboarding main surface, navigates through the current
 * IA v2 area sidebar, and runs axe against the visible governance and runtime
 * panel areas. This expands coverage beyond the rail-only sidebar scan.
 */

import { failOnBlocking, runAxe, withApp, waitForMainSurface } from './_helpers';

async function run(): Promise<void> {
  await withApp({ skipOnboarding: true }, async (page) => {
    await waitForMainSurface(page);

    await page.getByTestId('area-nav-governance').click();
    await page.waitForTimeout(600);
    failOnBlocking('governance panels', await runAxe(page));

    await page.getByTestId('area-nav-runs').click();
    await page.waitForTimeout(600);
    failOnBlocking('runtime panels', await runAxe(page));
  });
}

run().catch((err) => {
  console.error('[a11y:runtime-panels] FAIL:', err);
  process.exit(1);
});
