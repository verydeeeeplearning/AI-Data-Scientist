/**
 * Shared helpers for E2E a11y specs (Phase B / ADR-0010).
 *
 * Each spec launches Electron with the packaged backend binary, navigates to a
 * specific surface, and runs an axe scan with WCAG 2.1 A + AA tags. Critical /
 * serious violations fail the spec. Minor / moderate findings are recorded for
 * later triage in PLAN_01 §12 but do not block the gate.
 *
 * Runner: plain Node (no @playwright/test). Mirrors tests/smoke/*.spec.ts.
 */

import { _electron as electron, type ElectronApplication, type Page } from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import path from 'node:path';
import fs from 'node:fs';

const ELECTRON_DIR = process.cwd();
const REPO_ROOT = path.resolve(ELECTRON_DIR, '..');
const ELECTRON_MAIN = path.resolve(ELECTRON_DIR, 'dist', 'main', 'index.js');
const BACKEND_BIN = path.resolve(
  REPO_ROOT,
  'dist',
  'ds-agent-backend',
  process.platform === 'win32' ? 'ds-agent-api.exe' : 'ds-agent-api'
);

const SCAN_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const BLOCKING_IMPACTS = new Set<string>(['critical', 'serious']);

export interface AxeViolation {
  readonly id: string;
  readonly impact: string | null | undefined;
  readonly description: string;
  readonly help: string;
  readonly helpUrl: string;
  readonly nodes: ReadonlyArray<{ readonly target: ReadonlyArray<string>; readonly html: string }>;
}

export interface LaunchOptions {
  readonly skipOnboarding: boolean;
}

export async function launchElectron(opts: LaunchOptions): Promise<ElectronApplication> {
  if (!fs.existsSync(BACKEND_BIN)) {
    throw new Error(
      `Backend binary not found at ${BACKEND_BIN}. ` +
        `Run "python scripts/build_backend.py" first.`
    );
  }

  const env: Record<string, string> = {
    ...process.env,
    DS_AGENT_BACKEND_COMMAND: BACKEND_BIN,
    DS_AGENT_SENTRY_DSN: '',
    DS_AGENT_E2E_USE_BUILT_RENDERER: '1',
  };
  if (opts.skipOnboarding) {
    env.DS_AGENT_E2E_SKIP_ONBOARDING = '1';
  }

  return electron.launch({
    args: [ELECTRON_MAIN],
    cwd: REPO_ROOT,
    env,
    timeout: 60_000,
  });
}

export async function waitForFirstWindow(app: ElectronApplication): Promise<Page> {
  const page = await app.firstWindow({ timeout: 60_000 });
  await page.waitForLoadState('domcontentloaded');
  return page;
}

export async function waitForMainSurface(page: Page): Promise<void> {
  await page
    .locator('nav, aside, [role="navigation"]')
    .first()
    .waitFor({ state: 'visible', timeout: 60_000 })
    .catch(() => {});
  await page.waitForTimeout(500);
}

export async function runAxe(page: Page): Promise<{
  readonly violations: ReadonlyArray<AxeViolation>;
  readonly blocking: ReadonlyArray<AxeViolation>;
  readonly informational: ReadonlyArray<AxeViolation>;
}> {
  const result = await new AxeBuilder({ page })
    .setLegacyMode(true)
    .withTags([...SCAN_TAGS])
    .analyze();
  const violations = result.violations as unknown as ReadonlyArray<AxeViolation>;
  const blocking = violations.filter((v) => BLOCKING_IMPACTS.has(String(v.impact ?? '')));
  const informational = violations.filter((v) => !BLOCKING_IMPACTS.has(String(v.impact ?? '')));
  return { violations, blocking, informational };
}

export function reportViolations(label: string, violations: ReadonlyArray<AxeViolation>): string {
  if (violations.length === 0) {
    return `${label}: 0 violations`;
  }
  const lines = violations.map((v) => {
    const nodeDetails = v.nodes
      .slice(0, 3)
      .map((n) => `        target: ${n.target.join(' >> ')}\n        html: ${n.html.slice(0, 200)}`)
      .join('\n');
    return `  - [${v.impact ?? 'unknown'}] ${v.id}: ${v.help}\n      help: ${v.helpUrl}\n${nodeDetails}`;
  });
  return `${label}: ${violations.length} violations\n${lines.join('\n')}`;
}

export async function withApp<T>(
  opts: LaunchOptions,
  body: (page: Page, app: ElectronApplication) => Promise<T>
): Promise<T> {
  const app = await launchElectron(opts);
  try {
    const page = await waitForFirstWindow(app);
    return await body(page, app);
  } finally {
    await app.close();
  }
}

export function failOnBlocking(label: string, violations: { readonly blocking: ReadonlyArray<AxeViolation>; readonly informational: ReadonlyArray<AxeViolation> }): void {
  if (violations.informational.length > 0) {
    console.log('[a11y] ' + reportViolations(label + ' (informational, non-blocking)', violations.informational));
  }
  if (violations.blocking.length > 0) {
    console.error('[a11y] ' + reportViolations(label + ' (BLOCKING)', violations.blocking));
    throw new Error(`${label}: ${violations.blocking.length} critical/serious axe violation(s)`);
  }
  console.log(`[a11y] PASS — ${label}: 0 critical/serious violations`);
}
