/**
 * a11y E2E: Artifacts files + workspace panels.
 *
 * Starts from the post-onboarding main surface, navigates to the artifacts
 * area, scans the files view that contains the sidebar upload/file/plot
 * surfaces, then switches to the workspace view and scans the center evidence
 * workspace panels.
 */

import { failOnBlocking, runAxe, withApp, waitForMainSurface } from './_helpers';

async function run(): Promise<void> {
  await withApp({ skipOnboarding: true }, async (page) => {
    await waitForMainSurface(page);

    await page.getByTestId('area-nav-artifacts').click();
    await page.waitForTimeout(700);
    failOnBlocking('artifact file panels', await runAxe(page));

    await page.getByRole('button', { name: 'Workspace' }).click();
    await page.waitForTimeout(700);
    failOnBlocking('workspace panels', await runAxe(page));
  });
}

run().catch((err) => {
  console.error('[a11y:workspace-panels] FAIL:', err);
  process.exit(1);
});
