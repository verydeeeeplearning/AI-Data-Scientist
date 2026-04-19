/**
 * a11y E2E: MissionHeader on MainPanel (Wave 1 W1-E baseline).
 *
 * Uses DS_AGENT_E2E_SKIP_ONBOARDING=1 so MainPanel mounts directly. The
 * MissionHeader currently ships the codex-w1e baseline (9 slots collapsed
 * + budget warning shell). Phase C is finalizing drawers/dropdowns; this
 * spec only gates baseline a11y of what exists today.
 */

import { failOnBlocking, runAxe, withApp, waitForMainSurface } from './_helpers';

async function run(): Promise<void> {
  await withApp({ skipOnboarding: true }, async (page) => {
    await waitForMainSurface(page);
    const result = await runAxe(page);
    failOnBlocking('mission', result);
  });
}

run().catch((err) => {
  console.error('[a11y:mission] FAIL:', err);
  process.exit(1);
});
