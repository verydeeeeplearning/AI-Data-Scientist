/**
 * E2E: Decision OS full review flow against the packaged backend.
 *
 * Covers overview loading, shared-skill review artifacts, run diff,
 * promotion request, and post-deploy status retrieval from the real
 * Electron renderer + packaged backend stack.
 */

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { _electron as electron, type Page } from 'playwright';

const ELECTRON_DIR = process.cwd();
const REPO_ROOT = path.resolve(ELECTRON_DIR, '..');
const ELECTRON_MAIN = path.resolve(ELECTRON_DIR, 'dist', 'main', 'index.js');
const BACKEND_BIN = path.resolve(
  REPO_ROOT,
  'dist',
  'ds-agent-backend',
  process.platform === 'win32' ? 'ds-agent-api.exe' : 'ds-agent-api',
);

function ensureDir(target: string): void {
  fs.mkdirSync(target, { recursive: true });
}

function buildIsolatedPaths(): {
  rootDir: string;
  workspaceDir: string;
  configDir: string;
  configPath: string;
} {
  const rootDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ds-agent-decision-os-e2e-'));
  const workspaceDir = path.join(rootDir, 'workspace');
  const configDir = path.join(rootDir, 'config');
  const configPath = path.join(configDir, 'config.yaml');

  [workspaceDir, configDir].forEach(ensureDir);
  return { rootDir, workspaceDir, configDir, configPath };
}

function seedWorkspace(configPath: string, workspaceDir: string): void {
  const scriptPath = path.resolve(REPO_ROOT, 'scripts', 'seed_decision_os_e2e_workspace.py');
  const attempts: Array<{ command: string; prefixArgs: string[] }> =
    process.platform === 'win32'
      ? [
          { command: 'py', prefixArgs: ['-3'] },
          { command: 'python', prefixArgs: [] },
        ]
      : [{ command: 'python', prefixArgs: [] }];

  let lastError: string | null = null;
  for (const attempt of attempts) {
    const result = spawnSync(
      attempt.command,
      [...attempt.prefixArgs, scriptPath, '--config-path', configPath, '--workspace-dir', workspaceDir],
      {
        cwd: REPO_ROOT,
        encoding: 'utf8',
      },
    );
    if (result.error) {
      lastError = result.error.message;
      continue;
    }
    if (result.status === 0) {
      return;
    }
    lastError = `seed failed (${attempt.command}): ${result.stderr || result.stdout}`;
  }

  throw new Error(lastError ?? 'Failed to seed Decision OS E2E workspace.');
}

async function screenshot(page: Page, targetPath: string): Promise<void> {
  ensureDir(path.dirname(targetPath));
  await page.screenshot({ path: targetPath, fullPage: true });
}

async function waitForNumericTestIdAtLeast(
  page: Page,
  testId: string,
  minimum: number,
): Promise<void> {
  await page.waitForFunction(
    ({ currentTestId, currentMinimum }) => {
      const node = document.querySelector(`[data-testid="${currentTestId}"]`);
      const raw = node?.textContent?.trim() ?? '';
      const match = raw.match(/-?\d+/);
      const value = match ? Number.parseInt(match[0], 10) : Number.NaN;
      return Number.isFinite(value) && value >= currentMinimum;
    },
    { currentTestId: testId, currentMinimum: minimum },
    { timeout: 30_000 },
  );
}

async function clickTestId(page: Page, testId: string): Promise<void> {
  const element = page.getByTestId(testId);
  await element.waitFor({ state: 'visible', timeout: 30_000 });
  await element.evaluate((node) => (node as HTMLElement).click());
}

async function run(): Promise<void> {
  if (!fs.existsSync(BACKEND_BIN)) {
    throw new Error(
      `Backend binary not found at ${BACKEND_BIN}. ` +
        `Run "python scripts/build_backend.py" first.`,
    );
  }

  const paths = buildIsolatedPaths();
  seedWorkspace(paths.configPath, paths.workspaceDir);
  const artifactsDir = path.join(paths.rootDir, 'artifacts');

  const app = await electron.launch({
    args: [ELECTRON_MAIN],
    cwd: REPO_ROOT,
    env: {
      ...process.env,
      DS_AGENT_CONFIG_PATH: paths.configPath,
      DS_AGENT_BACKEND_COMMAND: BACKEND_BIN,
      DS_AGENT_SENTRY_DSN: '',
      DS_AGENT_ERROR_REPORTING_ENABLED: '0',
      DS_AGENT_TELEMETRY_ENABLED: '0',
      DS_AGENT_E2E_USER_DATA_DIR: path.join(paths.rootDir, 'userData'),
      DS_AGENT_E2E_USE_BUILT_RENDERER: '1',
      DS_AGENT_E2E_SKIP_ONBOARDING: '1',
    },
    timeout: 60_000,
  });

  let page: Page | null = null;
  try {
    page = await app.firstWindow({ timeout: 60_000 });
    await page.waitForLoadState('domcontentloaded');
    await page.getByTestId('area-nav-runs').waitFor({ state: 'visible', timeout: 60_000 });

    await clickTestId(page, 'area-nav-governance');
    await page.getByTestId('decision-os-overview').waitFor({ state: 'visible', timeout: 30_000 });
    await waitForNumericTestIdAtLeast(page, 'decision-os-overview-run-count', 2);
    await waitForNumericTestIdAtLeast(page, 'decision-os-overview-model-count', 2);
    await waitForNumericTestIdAtLeast(page, 'decision-os-overview-monitor-count', 1);
    await screenshot(page, path.join(artifactsDir, 'review-overview.png'));

    await page.getByTestId('decision-os-artifact-run').selectOption('run-candidate');
    await page
      .getByTestId('decision-os-artifact-retrain-vs-rollback')
      .waitFor({ state: 'visible', timeout: 30_000 });
    await clickTestId(page, 'decision-os-artifact-toggle-retrain-vs-rollback');
    await page
      .getByTestId('decision-os-artifact-narrative-retrain-vs-rollback')
      .waitFor({ state: 'visible', timeout: 30_000 });

    await page.getByTestId('decision-os-run-diff-base').selectOption('run-champion');
    await page.getByTestId('decision-os-run-diff-candidate').selectOption('run-candidate');
    await clickTestId(page, 'decision-os-run-diff-compare');
    await page
      .getByTestId('decision-os-run-diff-result')
      .waitFor({ state: 'visible', timeout: 30_000 });
    await page
      .getByTestId('decision-os-run-diff-result')
      .getByText(/monitor feature freshness after promotion/)
      .first()
      .waitFor({
        state: 'visible',
        timeout: 30_000,
      });
    await screenshot(page, path.join(artifactsDir, 'review-run-diff.png'));

    await clickTestId(page, 'decision-os-run-diff-open-promotion');
    await page
      .getByTestId('decision-os-promotion-gate-modal')
      .waitFor({ state: 'visible', timeout: 30_000 });
    await page.getByTestId('decision-os-promotion-stage').selectOption('staging');
    await page.getByTestId('decision-os-promotion-approvers').fill('DS, Lead, MLOps');
    await clickTestId(page, 'decision-os-promotion-submit');
    await page
      .getByTestId('decision-os-promotion-result')
      .waitFor({ state: 'visible', timeout: 30_000 });
    await page
      .getByTestId('decision-os-promotion-result')
      .getByText('run-candidate')
      .waitFor({ state: 'visible', timeout: 30_000 });
    await screenshot(page, path.join(artifactsDir, 'review-promotion-gate.png'));
    await clickTestId(page, 'decision-os-promotion-close');
    await waitForNumericTestIdAtLeast(page, 'decision-os-overview-decision-count', 1);

    await page.getByTestId('decision-os-post-deploy-model').selectOption('m_churn_lightgbm');
    await page.getByTestId('decision-os-post-deploy-window').fill('7d');
    await clickTestId(page, 'decision-os-post-deploy-load');
    await page
      .getByTestId('decision-os-post-deploy-result')
      .waitFor({ state: 'visible', timeout: 30_000 });
    await page.getByTestId('decision-os-post-deploy-alerts').waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    await page.getByText('Drift threshold exceeded').waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    await screenshot(page, path.join(artifactsDir, 'review-post-deploy-status.png'));

    console.log(`[e2e] PASS decision-os review flow. Artifacts: ${artifactsDir}`);
  } catch (error) {
    if (page) {
      await screenshot(page, path.join(artifactsDir, 'failure.png'));
      const html = await page.content();
      fs.writeFileSync(path.join(artifactsDir, 'failure.html'), html, 'utf8');
    }
    throw error;
  } finally {
    await app.close();
  }
}

run().catch((error) => {
  console.error('[e2e] FAIL:', error);
  process.exit(1);
});
