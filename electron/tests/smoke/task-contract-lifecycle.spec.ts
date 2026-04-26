/**
 * E2E: Mission Brief lifecycle flow for a seeded task contract.
 *
 * Covers edit, agree, start-work, review, and close transitions against the
 * packaged backend with a seeded contract that already has close prerequisites.
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
const SEEDED_SESSION_ID = 'seeded-task-contract-session';

function ensureDir(target: string): void {
  fs.mkdirSync(target, { recursive: true });
}

function buildIsolatedPaths(): {
  rootDir: string;
  workspaceDir: string;
  configDir: string;
  configPath: string;
} {
  const rootDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ds-agent-task-contract-lifecycle-'));
  const workspaceDir = path.join(rootDir, 'workspace');
  const configDir = path.join(rootDir, 'config');
  const configPath = path.join(configDir, 'config.yaml');

  [workspaceDir, configDir].forEach(ensureDir);

  return {
    rootDir,
    workspaceDir,
    configDir,
    configPath,
  };
}

function seedWorkspace(configPath: string, workspaceDir: string): void {
  const scriptPath = path.resolve(
    REPO_ROOT,
    'scripts',
    'seed_task_contract_lifecycle_e2e_workspace.py',
  );
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

  throw new Error(lastError ?? 'Failed to seed task-contract lifecycle E2E workspace.');
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

async function waitForClosedOrThrow(page: Page): Promise<void> {
  try {
    await waitForTextContains(page, 'mission-brief-status-badge', 'closed');
    return;
  } catch (error) {
    const actionError = await page.getByTestId('mission-brief-action-error').textContent().catch(
      () => null,
    );
    const actionNotice = await page
      .getByTestId('mission-brief-action-notice')
      .textContent()
      .catch(() => null);
    throw new Error(
      `close transition did not reach closed. actionError=${JSON.stringify(actionError)} `
        + `actionNotice=${JSON.stringify(actionNotice)} original=${String(error)}`,
    );
  }
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

  try {
    const page = await app.firstWindow({ timeout: 60_000 });
    await page.waitForLoadState('domcontentloaded');
    await page.getByTestId('open-settings').waitFor({ state: 'visible', timeout: 60_000 });

    await clickTestId(page, 'sidebar-tab-runtime');
    await openSeededSession(page);
    await clickTestId(page, 'sidebar-tab-workflow');

    await page.getByTestId('mission-brief-panel').waitFor({ state: 'visible', timeout: 30_000 });
    await page.getByTestId('mission-brief-action-edit').waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    await waitForTextContains(page, 'mission-brief-status-badge', 'draft');

    await clickTestId(page, 'mission-brief-action-edit');
    await page.getByTestId('contract-editor').waitFor({ state: 'visible', timeout: 30_000 });
    await page
      .getByTestId('contract-editor-business-goal')
      .fill('Prepare a retention-risk readout with explicit owner-ready next actions.');
    await page.getByTestId('contract-editor-decision-owner').fill('retention-lead@corp');
    await clickTestId(page, 'contract-editor-save');

    await waitForTextContains(
      page,
      'mission-brief-business-goal',
      'Prepare a retention-risk readout with explicit owner-ready next actions.',
    );
    await waitForTextContains(
      page,
      'mission-brief-decision-owner',
      'retention-lead@corp',
    );

    await clickTestId(page, 'mission-brief-action-agree');
    await waitForTextContains(page, 'mission-brief-status-badge', 'agreed');

    await clickTestId(page, 'mission-brief-action-start-work');
    await waitForTextContains(page, 'mission-brief-status-badge', 'in_progress');

    await clickTestId(page, 'mission-brief-action-send-review');
    await waitForTextContains(page, 'mission-brief-status-badge', 'review');

    await clickTestId(page, 'mission-brief-action-close');
    await page.getByTestId('mission-brief-close-dialog').waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    await page
      .getByTestId('mission-brief-close-note')
      .fill('Operator verified all closure criteria.');
    await clickTestId(page, 'mission-brief-close-confirm');
    await waitForClosedOrThrow(page);
    await page.getByText('DoD Summary').waitFor({ state: 'visible', timeout: 30_000 });

    console.log('[e2e] PASS task-contract lifecycle flow.');
  } finally {
    await app.close();
  }
}

run().catch((error) => {
  console.error('[e2e] FAIL:', error);
  process.exit(1);
});
