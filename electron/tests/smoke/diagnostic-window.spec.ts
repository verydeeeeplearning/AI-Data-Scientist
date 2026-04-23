/**
 * Smoke: backend startup failure surfaces the diagnostic window (P0-03).
 *
 * Forces the backend launcher to point at a non-existent binary via the
 * `DS_AGENT_BACKEND_COMMAND` env override. The main process should classify
 * the failure as BINARY_NOT_FOUND and open the diagnostic window with a
 * reason-specific title rendered by `DiagnosticPanel`.
 *
 * Runner: plain Node (no @playwright/test dependency). Exits non-zero on
 * failure for CI usability.
 */

import path from 'node:path';
import { captureFailureArtifacts } from '../e2e/_shared/artifacts';
import { launchApp } from '../e2e/_shared/launcher';
import { REPO_ROOT } from '../e2e/_shared/paths';

const BAD_BINARY = path.join(REPO_ROOT, 'this-binary-does-not-exist');

async function run(): Promise<void> {
  const { app, page, isolated } = await launchApp('diagnostic-window', {
    skipBinaryCheck: true,
    extraEnv: { DS_AGENT_BACKEND_COMMAND: BAD_BINARY },
  });

  try {
    const titleText = await page.locator('h1').first().textContent({ timeout: 30_000 });
    const ok = !!titleText && /Backend binary was not found/i.test(titleText);

    if (!ok) {
      const html = await page.content();
      throw new Error(
        `Diagnostic title not rendered as expected. Got: ${JSON.stringify(titleText)}\n` +
          `--- HTML (first 2 KB) ---\n${html.slice(0, 2048)}`
      );
    }
    console.log(`[smoke] PASS — diagnostic title: ${titleText}`);
  } catch (err) {
    await captureFailureArtifacts(page, isolated.artifacts, 'diagnostic-window').catch(() => {});
    throw err;
  } finally {
    await app.close();
  }
}

run().catch((err) => {
  console.error('[smoke] FAIL:', err);
  process.exit(1);
});
