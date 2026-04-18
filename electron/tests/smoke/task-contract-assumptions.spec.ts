/**
 * E2E: verify an open task-contract assumption from MissionBrief.
 *
 * Uses the packaged backend and a seeded workspace so the renderer exercises
 * the real HTTP/IPC path when an operator marks an assumption as verified.
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
} {
  const rootDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ds-agent-task-contract-e2e-'));
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

  throw new Error(lastError ?? 'Failed to seed task-contract E2E workspace.');
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
      DS_AGENT_E2E_USE_BUILT_RENDERER: '1',
      DS_AGENT_E2E_SKIP_ONBOARDING: '1',
    },
    timeout: 60_000,
  });

  try {
    const page = await app.firstWindow({ timeout: 60_000 });
    await page.waitForLoadState('domcontentloaded');
    await page.getByTestId('open-settings').waitFor({ state: 'visible', timeout: 60_000 });

    await page.getByTestId('sidebar-tab-runtime').click();
    await page.getByTestId(`open-session-${SEEDED_SESSION_ID}`).waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    await page.getByTestId(`open-session-${SEEDED_SESSION_ID}`).click();

    await page.getByTestId('sidebar-tab-workflow').click();
    await page.getByTestId('mission-brief-panel').waitFor({ state: 'visible', timeout: 30_000 });
    await waitForTextContains(
      page,
      'mission-brief-open-assumptions-count',
      '1 open assumptions',
    );

    await page.getByTestId('mission-brief-open-assumptions').click();
    await page.getByTestId('assumption-drawer').waitFor({ state: 'visible', timeout: 30_000 });

    const noteField = page.locator('[data-testid^="assumption-note-"]').first();
    const verifyButton = page.locator('[data-testid^="assumption-verify-"]').first();

    await noteField.fill('Verified against the weekly KPI operator playbook.');
    await verifyButton.click();

    await waitForTextContains(
      page,
      'mission-brief-open-assumptions-count',
      '0 open assumptions',
    );
    await page.getByTestId('assumption-empty-state').waitFor({ state: 'visible', timeout: 30_000 });
    await page.getByText(/marked as verified/i).waitFor({ state: 'visible', timeout: 30_000 });

    console.log('[e2e] PASS task-contract assumption verification flow.');
  } finally {
    await app.close();
  }
}

run().catch((error) => {
  console.error('[e2e] FAIL:', error);
  process.exit(1);
});
