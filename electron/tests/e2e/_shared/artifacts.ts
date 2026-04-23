import fs from 'node:fs';
import path from 'node:path';
import type { Page } from 'playwright';

export async function captureFailureArtifacts(
  page: Page,
  artifactsDir: string,
  label: string
): Promise<void> {
  try {
    const ts = Date.now();
    await page.screenshot({ path: path.join(artifactsDir, `failure-${ts}.png`), fullPage: true });
    fs.writeFileSync(path.join(artifactsDir, `failure-${ts}.html`), await page.content(), 'utf8');
    fs.writeFileSync(path.join(artifactsDir, 'page-url.txt'), page.url(), 'utf8');
    console.error(`[artifacts] ${label} — saved to ${artifactsDir}`);
  } catch (err) {
    console.error('[artifacts] capture failed:', err);
  }
}
