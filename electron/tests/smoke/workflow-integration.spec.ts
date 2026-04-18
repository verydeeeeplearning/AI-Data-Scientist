/**
 * E2E: workflow integration smoke test with a seeded workspace.
 *
 * Covers the full WorkObject lifecycle panel (advance phase, close),
 * IntegrationSettings health check, and timeline verification against
 * the packaged backend with seeded Slack/Jira integration events.
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
const SEEDED_SESSION_ID = 'seeded-workflow-session';
const SEEDED_WORK_OBJECT_ID = 'WO-2026-951001';

function ensureDir(target: string): void {
  fs.mkdirSync(target, { recursive: true });
}

function buildIsolatedPaths(): {
  rootDir: string;
  workspaceDir: string;
  configDir: string;
  configPath: string;
} {
  const rootDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ds-agent-workflow-e2e-'));
  const workspaceDir = path.join(rootDir, 'workspace');
  const configDir = path.join(rootDir, 'config');
  const configPath = path.join(configDir, 'config.yaml');

  [workspaceDir, configDir].forEach(ensureDir);

  return { rootDir, workspaceDir, configDir, configPath };
}

function seedWorkspace(configPath: string, workspaceDir: string): void {
  const scriptPath = path.resolve(
    REPO_ROOT,
    'scripts',
    'seed_workflow_e2e_workspace.py',
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
        '--work-object-id',
        SEEDED_WORK_OBJECT_ID,
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

  throw new Error(lastError ?? 'Failed to seed workflow E2E workspace.');
}

async function waitForTextContains(
  page: Page,
  testId: string,
  needle: string,
): Promise<void> {
  await page.waitForFunction(
    ({ currentTestId, currentNeedle }) => {
      const node = document.querySelector(`[data-testid="${currentTestId}"]`);
      return Boolean(node?.textContent?.includes(currentNeedle));
    },
    { currentTestId: testId, currentNeedle: needle },
    { timeout: 30_000 },
  );
}

async function screenshot(page: Page, targetPath: string): Promise<void> {
  ensureDir(path.dirname(targetPath));
  await page.screenshot({ path: targetPath, fullPage: true });
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
      DS_AGENT_E2E_USE_BUILT_RENDERER: '1',
      DS_AGENT_E2E_SKIP_ONBOARDING: '1',
    },
    timeout: 60_000,
  });

  let page: Page | null = null;
  try {
    page = await app.firstWindow({ timeout: 60_000 });
    await page.waitForLoadState('domcontentloaded');
    await page.getByTestId('open-settings').waitFor({ state: 'visible', timeout: 60_000 });

    // ── Step 1: Attach to the seeded session ────────────────────────────
    await page.getByTestId('sidebar-tab-runtime').click();
    await page.getByTestId(`open-session-${SEEDED_SESSION_ID}`).waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    await page.getByTestId(`open-session-${SEEDED_SESSION_ID}`).click();

    // ── Step 2: Navigate to Workflow tab ────────────────────────────────
    await page.getByTestId('sidebar-tab-workflow').click();
    await page.getByTestId('work-object-panel').waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    await screenshot(page, path.join(artifactsDir, 'workflow-panel-loaded.png'));

    // ── Step 3: Verify seeded work object is visible ────────────────────
    const woItem = page.locator(`[data-testid="work-object-item-${SEEDED_WORK_OBJECT_ID}"]`);
    await woItem.waitFor({ state: 'visible', timeout: 30_000 });
    await woItem.click();

    // Work object detail should appear with intake phase
    await page.getByTestId('work-object-detail').waitFor({
      state: 'visible',
      timeout: 30_000,
    });

    // ── Step 4: Verify timeline shows seeded integration events ─────────
    await page.getByTestId('work-object-timeline').waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    await waitForTextContains(page, 'work-object-timeline', 'slack');
    await waitForTextContains(page, 'work-object-timeline', 'jira');
    await screenshot(page, path.join(artifactsDir, 'work-object-timeline.png'));

    // ── Step 5: Advance work object phase (intake → executing) ──────────
    const advanceBtn = page.getByTestId('work-object-advance-btn');
    await advanceBtn.waitFor({ state: 'visible', timeout: 30_000 });
    await advanceBtn.click();
    // After advance the detail should refresh — wait for the Advance button
    // to change (next target is "review") or for a notice to appear.
    await page.waitForFunction(
      () => {
        const btn = document.querySelector('[data-testid="work-object-advance-btn"]');
        const notice = document.querySelector('[data-testid="work-object-actions"]');
        return (
          (btn?.textContent?.toLowerCase().includes('review')) ||
          (notice?.textContent?.toLowerCase().includes('advanced'))
        );
      },
      undefined,
      { timeout: 30_000 },
    );
    await screenshot(page, path.join(artifactsDir, 'after-advance-phase.png'));

    // ── Step 6: Close the work object ───────────────────────────────────
    const closeBtn = page.getByTestId('work-object-close-btn');
    await closeBtn.waitFor({ state: 'visible', timeout: 30_000 });
    await closeBtn.click();

    const reasonInput = page.getByTestId('work-object-close-reason');
    await reasonInput.waitFor({ state: 'visible', timeout: 30_000 });
    await reasonInput.fill('E2E test closure — all criteria verified.');

    const confirmBtn = page.getByTestId('work-object-close-confirm');
    await confirmBtn.click();

    // Wait for the close notice or the phase badge to reflect closed state
    await page.waitForFunction(
      () => {
        const panel = document.querySelector('[data-testid="work-object-detail"]');
        const text = panel?.textContent?.toLowerCase() ?? '';
        return text.includes('closed') || text.includes('work object closed');
      },
      undefined,
      { timeout: 30_000 },
    );
    await screenshot(page, path.join(artifactsDir, 'after-close.png'));

    // ── Step 7: Integration health check ────────────────────────────────
    await page.getByTestId('integration-settings').waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    const healthBtn = page.getByTestId('integration-health-check-btn');
    await healthBtn.waitFor({ state: 'visible', timeout: 30_000 });
    await healthBtn.click();

    // Wait for at least one connector card to appear
    await page.waitForFunction(
      () => {
        const cards = document.querySelectorAll('[data-testid^="connector-"]');
        return cards.length >= 5;
      },
      undefined,
      { timeout: 30_000 },
    );
    await screenshot(page, path.join(artifactsDir, 'integration-health.png'));

    console.log(
      `[e2e] PASS workflow integration flow. Artifacts: ${artifactsDir}`,
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
