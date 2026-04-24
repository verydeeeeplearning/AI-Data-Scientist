/**
 * Smoke: happy-path Electron startup with the packaged backend binary.
 *
 * Launches Electron, lets the main process spawn the real PyInstaller
 * backend, and asserts the renderer reaches the post-handshake UI
 * (OnboardingWizard's "DS Agent" hero shown on first launch). This
 * exercises the full chain: backend READY emit -> /health probe -> window
 * navigation -> WebSocket handshake -> first-paint of app UI.
 *
 * Runner: plain Node (no @playwright/test). Exits non-zero on failure.
 */

import { captureFailureArtifacts } from '../e2e/_shared/artifacts';
import { launchApp } from '../e2e/_shared/launcher';

async function run(): Promise<void> {
  const { app, page, isolated } = await launchApp('happy-path');
  try {
    // Fail fast if main process classified the backend as failed and routed
    // us to the diagnostic window instead of the main UI.
    const hero = page.locator('h1', { hasText: /DS Agent/i }).first();
    await hero.waitFor({ state: 'visible', timeout: 60_000 });

    const heroText = await hero.textContent();
    if (!heroText || !/DS Agent/i.test(heroText)) {
      const html = await page.content();
      throw new Error(
        `Hero not rendered. Got: ${JSON.stringify(heroText)}\n` +
          `--- HTML (first 2 KB) ---\n${html.slice(0, 2048)}`
      );
    }

    // Make sure we did not route to the diagnostic surface.
    const diagnosticHit = await page.locator('#diagnostic-title').count();
    if (diagnosticHit > 0) {
      throw new Error(
        `Diagnostic window appeared instead of main UI. ` +
          `Backend handshake likely failed.`
      );
    }

    console.log(`[smoke] PASS main UI hero rendered: ${heroText.trim()}`);
  } catch (err) {
    await captureFailureArtifacts(page, isolated.artifacts, 'happy-path').catch(() => {});
    throw err;
  } finally {
    await app.close();
  }
}

run().catch((err) => {
  console.error('[smoke] FAIL:', err);
  process.exit(1);
});
