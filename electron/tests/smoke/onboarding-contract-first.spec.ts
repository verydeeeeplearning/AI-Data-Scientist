/**
 * Smoke: first-run onboarding lands in contract-first Mission Brief.
 *
 * Launches Electron with onboarding enabled and backend auto-draft enabled,
 * completes one realistic onboarding path, and asserts the post-onboarding UI
 * lands on a main surface with an active draft task contract. This smoke uses
 * the source backend by default so it validates current onboarding wiring even
 * when a local PyInstaller bundle is stale; opt into the packaged backend with
 * DS_AGENT_SMOKE_USE_PACKAGED_BACKEND=1.
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
const USE_PACKAGED_BACKEND = process.env.DS_AGENT_SMOKE_USE_PACKAGED_BACKEND === '1';

interface OnboardingFinalizeResponse {
  sessionId: string;
  createdSession: boolean;
  goalSeeded: boolean;
  taskId?: string | null;
  mission?: {
    goal?: {
      title?: string | null;
    } | null;
  } | null;
}

interface ActiveTaskContractPayload {
  contract: {
    contract: {
      task_id: string;
      status: string;
      business_goal: string;
    };
  } | null;
}

function ensureDir(target: string): void {
  fs.mkdirSync(target, { recursive: true });
}

function buildIsolatedPaths(): {
  rootDir: string;
  workspaceDir: string;
  configDir: string;
  configPath: string;
} {
  const rootDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ds-agent-onboarding-contract-'));
  const workspaceDir = path.join(rootDir, 'workspace');
  const configDir = path.join(rootDir, 'config');
  const configPath = path.join(configDir, 'config.yaml');

  [workspaceDir, configDir].forEach(ensureDir);
  return { rootDir, workspaceDir, configDir, configPath };
}

function seedConfig(configPath: string, workspaceDir: string): void {
  fs.writeFileSync(
    configPath,
    JSON.stringify(
      {
        provider: {
          default_model: 'anthropic/claude-sonnet-4-6',
        },
        agent: {
          workspace_dir: workspaceDir,
        },
      },
      null,
      2,
    ),
    'utf8',
  );
}

function resolvePythonExecutable(): string {
  const attempts =
    process.platform === 'win32'
      ? [
          { command: 'python', args: ['-c', 'import sys; print(sys.executable)'] },
          { command: 'py', args: ['-3', '-c', 'import sys; print(sys.executable)'] },
        ]
      : [
          { command: 'python3', args: ['-c', 'import sys; print(sys.executable)'] },
          { command: 'python', args: ['-c', 'import sys; print(sys.executable)'] },
        ];

  for (const attempt of attempts) {
    const result = spawnSync(attempt.command, attempt.args, {
      cwd: REPO_ROOT,
      encoding: 'utf8',
    });
    if (result.status === 0) {
      const executable = result.stdout.trim();
      if (executable.length > 0 && fs.existsSync(executable)) {
        return executable;
      }
    }
  }

  throw new Error('Unable to resolve a Python executable for the source-backend smoke test.');
}

function buildBackendEnv(): Record<string, string> {
  if (USE_PACKAGED_BACKEND) {
    if (!fs.existsSync(BACKEND_BIN)) {
      throw new Error(
        `Backend binary not found at ${BACKEND_BIN}. ` +
          `Run "python scripts/build_backend.py" first.`,
      );
    }
    return {
      DS_AGENT_BACKEND_COMMAND: BACKEND_BIN,
    };
  }

  const sourcePath = path.resolve(REPO_ROOT, 'src');
  const pythonPath = process.env.PYTHONPATH
    ? `${sourcePath}${path.delimiter}${process.env.PYTHONPATH}`
    : sourcePath;
  return {
    DS_AGENT_BACKEND_COMMAND: resolvePythonExecutable(),
    DS_AGENT_BACKEND_ARGS: '-m ds_agent.api.app',
    PYTHONPATH: pythonPath,
  };
}

async function ensureOnboardingSurface(page: Page): Promise<void> {
  const continueButton = page.getByRole('button', { name: /^Continue$/ }).last();
  const deadline = Date.now() + 60_000;

  while (Date.now() < deadline) {
    const onboardingVisible = await continueButton.isVisible().catch(() => false);
    if (onboardingVisible) {
      return;
    }

    const mainSurfaceVisible = await isMainSurfaceVisible(page);
    if (mainSurfaceVisible) {
      await page.evaluate(() => {
        localStorage.removeItem('ds-agent-onboarded-v2');
        localStorage.removeItem('ds-agent-onboarded');
        window.location.reload();
      });
      await continueButton.waitFor({
        state: 'visible',
        timeout: 60_000,
      });
      return;
    }

    await page.waitForTimeout(500);
  }

  const bodyText = ((await page.locator('body').textContent().catch(() => '')) ?? '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 400);
  throw new Error(`Onboarding surface never appeared. body=${bodyText}`);
}

async function isMainSurfaceVisible(page: Page): Promise<boolean> {
  const modernSurfaceVisible = await page.getByTestId('area-nav-mission').isVisible().catch(() => false);
  if (modernSurfaceVisible) {
    return true;
  }
  return page.getByTestId('open-settings').isVisible().catch(() => false);
}

function currentStepSection(page: Page) {
  return page
    .getByRole('button', { name: /^Continue$/ })
    .last()
    .locator('xpath=ancestor::div[contains(@class,"rounded-2xl")][1]');
}

async function clickVisibleContinue(page: Page): Promise<void> {
  const continueButton = page.getByRole('button', { name: /^Continue$/ }).last();
  await continueButton.evaluate((element) => {
    element.scrollIntoView({ block: 'center', inline: 'nearest' });
  });
  await continueButton.evaluate((element) => {
    (element as HTMLButtonElement).click();
  });
}

async function selectModel(page: Page): Promise<void> {
  const section = currentStepSection(page);
  const deadline = Date.now() + 60_000;

  while (Date.now() < deadline) {
    const buttons = section.getByRole('button');
    const buttonCount = await buttons.count();

    for (let index = 0; index < buttonCount; index += 1) {
      const button = buttons.nth(index);
      const label = (await button.textContent().catch(() => ''))?.trim() ?? '';
      if (!label || label === 'Continue' || label === 'Back to mode') {
        continue;
      }
      await button.evaluate((element) => {
        element.scrollIntoView({ block: 'center', inline: 'nearest' });
      });
      await button.evaluate((element) => {
        (element as HTMLButtonElement).click();
      });
      return;
    }

    await page.waitForTimeout(500);
  }

  throw new Error('No stable onboarding model candidate was visible.');
}

async function satisfyModelAuthIfNeeded(page: Page): Promise<void> {
  const passwordInput = page.locator('input[type="password"]').first();
  if (await passwordInput.isVisible().catch(() => false)) {
    await passwordInput.fill('sk-onboarding-smoke-test');
  }
}

function confirmStepCard(page: Page) {
  return page.locator('div.mx-auto.max-w-4xl.rounded-2xl.border.border-ds-border.bg-ds-surface.p-8');
}

async function clickConfirmPrivacyChoice(page: Page): Promise<void> {
  const buttons = confirmStepCard(page).getByRole('button');
  await buttons.nth(0).evaluate((element) => {
    (element as HTMLButtonElement).click();
  });
}

async function clickConfirmStart(page: Page): Promise<void> {
  await page.waitForFunction(() => {
    const card = document.querySelector(
      'div.mx-auto.max-w-4xl.rounded-2xl.border.border-ds-border.bg-ds-surface.p-8',
    );
    if (!(card instanceof HTMLElement)) {
      return false;
    }
    const buttons = Array.from(card.querySelectorAll('button'));
    const startButton = buttons[buttons.length - 1];
    return startButton instanceof HTMLButtonElement && !startButton.disabled;
  });
  const buttons = confirmStepCard(page).getByRole('button');
  const count = await buttons.count();
  await buttons.nth(count - 1).evaluate((element) => {
    (element as HTMLButtonElement).click();
  });
}

async function waitForMainSurface(page: Page): Promise<'legacy' | 'ia_v2'> {
  const deadline = Date.now() + 60_000;

  while (Date.now() < deadline) {
    const iaV2Visible = await page.getByTestId('area-nav-mission').isVisible().catch(() => false);
    if (iaV2Visible) {
      return 'ia_v2';
    }

    const legacyVisible = await page.getByTestId('open-settings').isVisible().catch(() => false);
    if (legacyVisible) {
      return 'legacy';
    }

    await page.waitForTimeout(500);
  }

  throw new Error('Main surface did not appear after onboarding handoff.');
}

async function fetchActiveTaskContract(
  page: Page,
  sessionId: string,
): Promise<ActiveTaskContractPayload> {
  return page.evaluate(async (currentSessionId) => {
    const params = new URLSearchParams(window.location.search);
    const rawPort = params.get('port');
    const port = rawPort ? Number.parseInt(rawPort, 10) : 18790;
    const baseUrl = `http://127.0.0.1:${Number.isFinite(port) ? port : 18790}`;
    const response = await fetch(
      `${baseUrl}/api/task-contracts/active?sessionId=${encodeURIComponent(currentSessionId)}`,
    );
    if (!response.ok) {
      throw new Error(`Active task contract lookup failed with status ${response.status}`);
    }
    return (await response.json()) as ActiveTaskContractPayload;
  }, sessionId);
}

async function waitForActiveDraftContract(
  page: Page,
  sessionId: string,
  taskId: string,
): Promise<NonNullable<ActiveTaskContractPayload['contract']>> {
  const deadline = Date.now() + 30_000;
  let lastObserved = 'no contract payload observed';

  while (Date.now() < deadline) {
    const payload = await fetchActiveTaskContract(page, sessionId).catch((error) => {
      lastObserved = error instanceof Error ? error.message : String(error);
      return null;
    });

    const contract = payload?.contract;
    if (contract?.contract.task_id === taskId && contract.contract.status === 'draft') {
      return contract;
    }

    if (contract) {
      lastObserved = JSON.stringify(contract.contract);
    }
    await page.waitForTimeout(500);
  }

  throw new Error(`Active task contract never converged to draft for ${taskId}. last=${lastObserved}`);
}

async function run(): Promise<void> {
  const paths = buildIsolatedPaths();
  seedConfig(paths.configPath, paths.workspaceDir);
  const backendEnv = buildBackendEnv();
  const app = await electron.launch({
    args: [ELECTRON_MAIN],
    cwd: REPO_ROOT,
    env: {
      ...process.env,
      ...backendEnv,
      DS_AGENT_CONFIG_PATH: paths.configPath,
      DS_AGENT_SENTRY_DSN: '',
      DS_AGENT_ERROR_REPORTING_ENABLED: '0',
      DS_AGENT_TELEMETRY_ENABLED: '0',
      DS_AGENT_E2E_USE_BUILT_RENDERER: '1',
      ONBOARDING_AUTO_DRAFT_CONTRACT_V1: 'true',
    },
    timeout: 60_000,
  });

  try {
    const page = await app.firstWindow({ timeout: 60_000 });
    await page.waitForLoadState('domcontentloaded');

    await ensureOnboardingSurface(page);

    await currentStepSection(page).getByRole('button').nth(2).click();
    await clickVisibleContinue(page);

    await currentStepSection(page).getByRole('button').nth(2).click();
    await clickVisibleContinue(page);

    await clickVisibleContinue(page);
    await clickVisibleContinue(page);

    await selectModel(page);
    await satisfyModelAuthIfNeeded(page);
    await clickVisibleContinue(page);

    await clickConfirmPrivacyChoice(page);
    const finalizeResponsePromise = page.waitForResponse(
      (response) =>
        response.url().includes('/api/onboarding/finalize')
        && response.request().method() === 'POST',
      { timeout: 60_000 },
    );
    await clickConfirmStart(page);

    const finalizeHttpResponse = await finalizeResponsePromise;
    if (!finalizeHttpResponse.ok()) {
      throw new Error(
        `Onboarding finalize failed with status ${finalizeHttpResponse.status()}: ${await finalizeHttpResponse.text()}`,
      );
    }
    const finalizeResponse = (await finalizeHttpResponse.json()) as OnboardingFinalizeResponse;
    if (!finalizeResponse.sessionId || finalizeResponse.sessionId.trim().length === 0) {
      throw new Error(`Onboarding finalize returned no session id: ${JSON.stringify(finalizeResponse)}`);
    }
    if (!finalizeResponse.taskId || finalizeResponse.taskId.trim().length === 0) {
      throw new Error(`Onboarding finalize returned no task id: ${JSON.stringify(finalizeResponse)}`);
    }

    const mainSurface = await waitForMainSurface(page);
    const activeContract = await waitForActiveDraftContract(
      page,
      finalizeResponse.sessionId,
      finalizeResponse.taskId,
    );

    if (!activeContract.contract.business_goal.includes('prediction workflow')) {
      throw new Error(
        `Expected active contract goal to mention prediction workflow, got: ${activeContract.contract.business_goal}`,
      );
    }

    if (mainSurface === 'legacy') {
      await page.getByTestId('sidebar-tab-workflow').click();
      await page.getByTestId('mission-brief-panel').waitFor({ state: 'visible', timeout: 30_000 });
      await page.getByTestId('mission-brief-status-badge').waitFor({
        state: 'visible',
        timeout: 30_000,
      });

      const statusText = await page.getByTestId('mission-brief-status-badge').textContent();
      if (!statusText || !statusText.toLowerCase().includes('draft')) {
        throw new Error(`Expected a draft task contract after onboarding, got: ${statusText}`);
      }

      const noContractCtaVisible = await page
        .getByTestId('mission-brief-create-contract-cta')
        .isVisible()
        .catch(() => false);
      if (noContractCtaVisible) {
        throw new Error('Onboarding landed on no-contract recovery CTA instead of an active draft.');
      }

      const businessGoalText = await page.getByTestId('mission-brief-business-goal').textContent();
      if (!businessGoalText || !businessGoalText.includes('prediction workflow')) {
        throw new Error(
          `Expected Mission Brief to show the prediction contract goal, got: ${businessGoalText}`,
        );
      }
    }

    console.log('[smoke] PASS — onboarding landed on a main surface with an active draft contract.');
  } finally {
    await app.close();
  }
}

run().catch((error) => {
  console.error('[smoke] FAIL:', error);
  process.exit(1);
});
