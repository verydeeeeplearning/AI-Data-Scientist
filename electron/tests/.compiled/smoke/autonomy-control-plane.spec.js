"use strict";
/**
 * E2E: autonomy control plane operator flow with a seeded workspace.
 *
 * Covers Runtime overlay changes, session attach, Policy Studio contract edits,
 * and Action Matrix override persistence against the real packaged backend.
 */
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const node_fs_1 = __importDefault(require("node:fs"));
const node_os_1 = __importDefault(require("node:os"));
const node_path_1 = __importDefault(require("node:path"));
const node_child_process_1 = require("node:child_process");
const playwright_1 = require("playwright");
const ELECTRON_DIR = process.cwd();
const REPO_ROOT = node_path_1.default.resolve(ELECTRON_DIR, '..');
const ELECTRON_MAIN = node_path_1.default.resolve(ELECTRON_DIR, 'dist', 'main', 'index.js');
const BACKEND_BIN = node_path_1.default.resolve(REPO_ROOT, 'dist', 'ds-agent-backend', process.platform === 'win32' ? 'ds-agent-api.exe' : 'ds-agent-api');
const SEEDED_SESSION_ID = 'seeded-autonomy-session';
function ensureDir(target) {
    node_fs_1.default.mkdirSync(target, { recursive: true });
}
function buildIsolatedPaths() {
    const rootDir = node_fs_1.default.mkdtempSync(node_path_1.default.join(node_os_1.default.tmpdir(), 'ds-agent-autonomy-e2e-'));
    const workspaceDir = node_path_1.default.join(rootDir, 'workspace');
    const configDir = node_path_1.default.join(rootDir, 'config');
    const configPath = node_path_1.default.join(configDir, 'config.yaml');
    const tempDir = node_path_1.default.join(rootDir, 'tmp');
    [workspaceDir, configDir, tempDir].forEach(ensureDir);
    return {
        rootDir,
        workspaceDir,
        configDir,
        configPath,
        tempDir,
    };
}
function seedWorkspace(configPath, workspaceDir) {
    const scriptPath = node_path_1.default.resolve(REPO_ROOT, 'scripts', 'seed_autonomy_e2e_workspace.py');
    const attempts = process.platform === 'win32'
        ? [
            { command: 'py', prefixArgs: ['-3'] },
            { command: 'python', prefixArgs: [] },
        ]
        : [{ command: 'python', prefixArgs: [] }];
    let lastError = null;
    for (const attempt of attempts) {
        const result = (0, node_child_process_1.spawnSync)(attempt.command, [
            ...attempt.prefixArgs,
            scriptPath,
            '--config-path',
            configPath,
            '--workspace-dir',
            workspaceDir,
            '--session-id',
            SEEDED_SESSION_ID,
        ], {
            cwd: REPO_ROOT,
            encoding: 'utf8',
        });
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
async function waitForTextContains(page, testId, needle) {
    await page.waitForFunction(({ currentTestId, currentNeedle }) => {
        const node = document.querySelector(`[data-testid="${currentTestId}"]`);
        return Boolean(node?.textContent?.includes(currentNeedle));
    }, { currentTestId: testId, currentNeedle: needle }, { timeout: 30000 });
}
async function waitForNumericTestIdAtLeast(page, testId, minimum) {
    await page.waitForFunction(({ currentTestId, currentMinimum }) => {
        const node = document.querySelector(`[data-testid="${currentTestId}"]`);
        const raw = node?.textContent?.trim() ?? '';
        const value = Number.parseInt(raw, 10);
        return Number.isFinite(value) && value >= currentMinimum;
    }, { currentTestId: testId, currentMinimum: minimum }, { timeout: 30000 });
}
async function screenshot(page, targetPath) {
    ensureDir(node_path_1.default.dirname(targetPath));
    await page.screenshot({ path: targetPath, fullPage: true });
}
async function run() {
    if (!node_fs_1.default.existsSync(BACKEND_BIN)) {
        throw new Error(`Backend binary not found at ${BACKEND_BIN}. ` +
            `Run "python scripts/build_backend.py" first.`);
    }
    const paths = buildIsolatedPaths();
    seedWorkspace(paths.configPath, paths.workspaceDir);
    const artifactsDir = node_path_1.default.join(paths.rootDir, 'artifacts');
    const app = await playwright_1._electron.launch({
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
        timeout: 60000,
    });
    let page = null;
    try {
        page = await app.firstWindow({ timeout: 60000 });
        await page.waitForLoadState('domcontentloaded');
        await page.getByTestId('open-settings').waitFor({ state: 'visible', timeout: 60000 });
        await page.getByTestId('sidebar-tab-runtime').click();
        await page.getByText('Runtime Console').waitFor({ state: 'visible', timeout: 30000 });
        await page.getByTestId('certification-board').waitFor({ state: 'visible', timeout: 30000 });
        await page.getByTestId('runtime-authority-overlay').selectOption('freeze');
        await waitForTextContains(page, 'runtime-effective-authority', 'freeze');
        await page.getByText('Freeze blocks write-side tool actions until the overlay is cleared.').waitFor({
            state: 'visible',
            timeout: 30000,
        });
        await screenshot(page, node_path_1.default.join(artifactsDir, 'runtime-console-freeze.png'));
        await page.getByTestId(`open-session-${SEEDED_SESSION_ID}`).click();
        await page.getByTestId('open-settings').click();
        await page.getByTestId('policy-studio').waitFor({ state: 'visible', timeout: 30000 });
        await page.getByTestId('policy-contract-card').waitFor({ state: 'visible', timeout: 30000 });
        await page.getByTestId('policy-overlay-banner').waitFor({ state: 'visible', timeout: 30000 });
        await page.getByTestId('policy-mission-select').waitFor({ state: 'visible', timeout: 30000 });
        const missionValue = await page.getByTestId('policy-mission-select').inputValue();
        if (!missionValue.startsWith('weekly-kpi-triage')) {
            throw new Error(`Expected mission select to target weekly-kpi-triage, got ${missionValue}`);
        }
        await page.getByTestId('policy-quick-preset-executive-review').click();
        await page.waitForFunction(() => {
            const authority = document.querySelector('[data-testid="policy-authority-select"]');
            const audience = document.querySelector('[data-testid="policy-audience-select"]');
            return authority?.value === 'supervised' && audience?.value === 'executive';
        }, undefined, { timeout: 30000 });
        await page.getByTestId('policy-apply-task-contract').waitFor({ state: 'visible', timeout: 30000 });
        await page.getByTestId('policy-apply-task-contract').click();
        await waitForTextContains(page, 'policy-studio', 'Current authority: Supervised');
        await waitForTextContains(page, 'policy-studio', 'Current audience: Executive');
        await page.getByTestId('policy-matrix-jira_create-delegate').selectOption('auto');
        await page.waitForFunction(() => {
            const node = document.querySelector('[data-testid="policy-matrix-save"]');
            return Boolean(node && !node.disabled);
        }, undefined, { timeout: 30000 });
        await page.getByTestId('policy-matrix-save').click();
        await waitForNumericTestIdAtLeast(page, 'policy-matrix-stored-count', 1);
        const storedOverrideText = (await page.getByTestId('policy-matrix-stored-count').textContent())?.trim() ?? '';
        const storedOverrideCount = Number.parseInt(storedOverrideText, 10);
        if (!Number.isFinite(storedOverrideCount) || storedOverrideCount < 1) {
            throw new Error(`Expected stored override count >= 1 after save, got ${JSON.stringify(storedOverrideText)}`);
        }
        await screenshot(page, node_path_1.default.join(artifactsDir, 'policy-studio-autonomy.png'));
        console.log(`[e2e] PASS autonomy control plane flow. Artifacts: ${artifactsDir}`);
    }
    catch (error) {
        if (page) {
            await screenshot(page, node_path_1.default.join(artifactsDir, 'failure.png'));
            const html = await page.content();
            node_fs_1.default.writeFileSync(node_path_1.default.join(artifactsDir, 'failure.html'), html, 'utf8');
        }
        throw error;
    }
    finally {
        await app.close();
    }
}
run().catch((error) => {
    console.error('[e2e] FAIL:', error);
    process.exit(1);
});
