/**
 * E2E: autonomy control plane operator flow with a seeded workspace.
 *
 * Covers Runtime overlay changes, session attach, Policy Studio contract edits,
 * and Action Matrix override persistence against the real packaged backend.
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
const SEEDED_SESSION_ID = 'seeded-autonomy-session';

function ensureDir(target: string): void {
  fs.mkdirSync(target, { recursive: true });
}

function buildIsolatedPaths(): {
  rootDir: string;
  workspaceDir: string;
  configDir: string;
  configPath: string;
  tempDir: string;
} {
  const rootDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ds-agent-autonomy-e2e-'));
  const workspaceDir = path.join(rootDir, 'workspace');
  const configDir = path.join(rootDir, 'config');
  const configPath = path.join(configDir, 'config.yaml');
  const tempDir = path.join(rootDir, 'tmp');

  [workspaceDir, configDir, tempDir].forEach(ensureDir);

  return {
    rootDir,
    workspaceDir,
    configDir,
    configPath,
    tempDir,
  };
}

function seedWorkspace(configPath: string, workspaceDir: string): void {
  const scriptPath = path.resolve(REPO_ROOT, 'scripts', 'seed_autonomy_e2e_workspace.py');
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
      [
        ...attempt.prefixArgs,
        scriptPath,
        '--config-path',
        configPath,
        '--workspace-dir',
        workspaceDir,
        '--session-id',
        SEEDED_SESSION_ID,
      ],
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

  throw new Error(lastError ?? 'Failed to seed autonomy E2E workspace.');
}

async function waitForTextContains(page: Page, testId: string, needle: string): Promise<void> {
  await page.waitForFunction(
    ({ currentTestId, currentNeedle }) => {
      const node = document.querySelector(`[data-testid="${currentTestId}"]`);
      return Boolean(node?.textContent?.includes(currentNeedle));
    },
    { currentTestId: testId, currentNeedle: needle },
    { timeout: 30_000 },
  );
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
      const value = Number.parseInt(raw, 10);
      return Number.isFinite(value) && value >= currentMinimum;
    },
    { currentTestId: testId, currentMinimum: minimum },
    { timeout: 30_000 },
  );
}

async function screenshot(page: Page, targetPath: string): Promise<void> {
  ensureDir(path.dirname(targetPath));
  await page.screenshot({ path: targetPath, fullPage: true });
}

async function clickTestId(page: Page, testId: string): Promise<void> {
  const element = page.getByTestId(testId);
  await element.waitFor({ state: 'visible', timeout: 30_000 });
  await element.evaluate((node) => (node as HTMLElement).click());
}

async function openSeededSession(page: Page): Promise<void> {
  const testId = `open-session-${SEEDED_SESSION_ID}`;
  const button = page.getByTestId(testId);
  await button.waitFor({ state: 'visible', timeout: 30_000 });
  await button.evaluate((node) => (node as HTMLButtonElement).click());
  await page.waitForFunction(
    ({ currentTestId }) => {
      const node = document.querySelector(`[data-testid="${currentTestId}"]`);
      return Boolean(node?.textContent?.includes('Opened'));
    },
    { currentTestId: testId },
    { timeout: 30_000 },
  );
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
      DS_AGENT_E2E_FORCE_LEGACY_IA: '1',
    },
    timeout: 60_000,
  });

  let page: Page | null = null;
  try {
    page = await app.firstWindow({ timeout: 60_000 });
    await page.waitForLoadState('domcontentloaded');
    await page.getByTestId('open-settings').waitFor({ state: 'visible', timeout: 60_000 });

    await clickTestId(page, 'sidebar-tab-runtime');
    await page.getByText('Runtime Console').waitFor({ state: 'visible', timeout: 30_000 });
    await page.getByTestId('certification-board').waitFor({ state: 'visible', timeout: 30_000 });

    await page.getByTestId('runtime-authority-overlay').selectOption('freeze');
    await waitForTextContains(page, 'runtime-effective-authority', 'freeze');
    await page.getByText('Freeze blocks write-side tool actions until the overlay is cleared.').waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    await screenshot(page, path.join(artifactsDir, 'runtime-console-freeze.png'));

    await openSeededSession(page);
    await page.getByTestId('open-settings').click();

    await page.getByTestId('policy-studio').waitFor({ state: 'visible', timeout: 30_000 });
    await page.getByTestId('policy-contract-card').waitFor({ state: 'visible', timeout: 30_000 });
    await page.getByTestId('policy-overlay-banner').waitFor({ state: 'visible', timeout: 30_000 });
    await page.getByTestId('policy-mission-select').waitFor({ state: 'visible', timeout: 30_000 });
    const missionValue = await page.getByTestId('policy-mission-select').inputValue();
    if (!missionValue.startsWith('weekly-kpi-triage')) {
      throw new Error(`Expected mission select to target weekly-kpi-triage, got ${missionValue}`);
    }

    await page.getByTestId('policy-quick-preset-executive-review').click();
    await page.waitForFunction(() => {
      const authority = document.querySelector('[data-testid="policy-authority-select"]') as HTMLSelectElement | null;
      const audience = document.querySelector('[data-testid="policy-audience-select"]') as HTMLSelectElement | null;
      return authority?.value === 'supervised' && audience?.value === 'executive';
    }, undefined, { timeout: 30_000 });
    await page.getByTestId('policy-apply-task-contract').waitFor({ state: 'visible', timeout: 30_000 });
    await page.getByTestId('policy-apply-task-contract').click();
    await waitForTextContains(page, 'policy-studio', 'Current authority: Supervised');
    await waitForTextContains(page, 'policy-studio', 'Current audience: Executive');

    await page.getByTestId('policy-matrix-jira_create-delegate').selectOption('auto');
    await page.waitForFunction(() => {
      const node = document.querySelector('[data-testid="policy-matrix-save"]') as HTMLButtonElement | null;
      return Boolean(node && !node.disabled);
    }, undefined, { timeout: 30_000 });
    await page.getByTestId('policy-matrix-save').click();
    await waitForNumericTestIdAtLeast(page, 'policy-matrix-stored-count', 1);

    const storedOverrideText =
      (await page.getByTestId('policy-matrix-stored-count').textContent())?.trim() ?? '';
    const storedOverrideCount = Number.parseInt(storedOverrideText, 10);
    if (!Number.isFinite(storedOverrideCount) || storedOverrideCount < 1) {
      throw new Error(
        `Expected stored override count >= 1 after save, got ${JSON.stringify(storedOverrideText)}`,
      );
    }

    await screenshot(page, path.join(artifactsDir, 'policy-studio-autonomy.png'));
    console.log(
      `[e2e] PASS autonomy control plane flow. Artifacts: ${artifactsDir}`,
    );
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
