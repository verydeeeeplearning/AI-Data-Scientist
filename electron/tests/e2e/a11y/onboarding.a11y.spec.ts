/**
 * a11y E2E: OnboardingWizard 6-step on first launch.
 *
 * Boots Electron without DS_AGENT_E2E_SKIP_ONBOARDING so the wizard renders
 * as the first surface (MainPanel never mounts here). Asserts WCAG 2.1 A+AA
 * with axe — focus trap, labels, color contrast, landmark roles all gated.
 */

import { failOnBlocking, runAxe, withApp } from './_helpers';

async function run(): Promise<void> {
  await withApp({ skipOnboarding: false }, async (page) => {
    const hero = page.locator('h1', { hasText: /DS Agent/i }).first();
    await hero.waitFor({ state: 'visible', timeout: 60_000 });

    const result = await runAxe(page);
    failOnBlocking('onboarding', result);
  });
}

run().catch((err) => {
  console.error('[a11y:onboarding] FAIL:', err);
  process.exit(1);
});
