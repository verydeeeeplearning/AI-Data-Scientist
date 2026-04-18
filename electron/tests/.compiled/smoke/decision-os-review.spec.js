"use strict";
/**
 * E2E: Decision OS full review flow against the packaged backend.
 *
 * Covers overview loading, shared-skill review artifacts, run diff,
 * promotion request, and post-deploy status retrieval from the real
 * Electron renderer + packaged backend stack.
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
function ensureDir(target) {
    node_fs_1.default.mkdirSync(target, { recursive: true });
}
function buildIsolatedPaths() {
    const rootDir = node_fs_1.default.mkdtempSync(node_path_1.default.join(node_os_1.default.tmpdir(), 'ds-agent-decision-os-e2e-'));
    const workspaceDir = node_path_1.default.join(rootDir, 'workspace');
    const configDir = node_path_1.default.join(rootDir, 'config');
    const configPath = node_path_1.default.join(configDir, 'config.yaml');
    [workspaceDir, configDir].forEach(ensureDir);
    return { rootDir, workspaceDir, configDir, configPath };
}
function seedWorkspace(configPath, workspaceDir) {
    const scriptPath = node_path_1.default.resolve(REPO_ROOT, 'scripts', 'seed_decision_os_e2e_workspace.py');
    const attempts = process.platform === 'win32'
        ? [
            { command: 'py', prefixArgs: ['-3'] },
            { command: 'python', prefixArgs: [] },
        ]
        : [{ command: 'python', prefixArgs: [] }];
    let lastError = null;
    for (const attempt of attempts) {
        const result = (0, node_child_process_1.spawnSync)(attempt.command, [...attempt.prefixArgs, scriptPath, '--config-path', configPath, '--workspace-dir', workspaceDir], {
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
    throw new Error(lastError ?? 'Failed to seed Decision OS E2E workspace.');
}
async function screenshot(page, targetPath) {
    ensureDir(node_path_1.default.dirname(targetPath));
    await page.screenshot({ path: targetPath, fullPage: true });
}
async function waitForNumericTestIdAtLeast(page, testId, minimum) {
    await page.waitForFunction(({ currentTestId, currentMinimum }) => {
        const node = document.querySelector(`[data-testid="${currentTestId}"]`);
        const raw = node?.textContent?.trim() ?? '';
        const match = raw.match(/-?\d+/);
        const value = match ? Number.parseInt(match[0], 10) : Number.NaN;
        return Number.isFinite(value) && value >= currentMinimum;
    }, { currentTestId: testId, currentMinimum: minimum }, { timeout: 30000 });
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
        await page.getByTestId('sidebar-tab-review').click();
        await page.getByTestId('decision-os-overview').waitFor({ state: 'visible', timeout: 30000 });
        await waitForNumericTestIdAtLeast(page, 'decision-os-overview-run-count', 2);
        await waitForNumericTestIdAtLeast(page, 'decision-os-overview-model-count', 2);
        await waitForNumericTestIdAtLeast(page, 'decision-os-overview-monitor-count', 1);
        await screenshot(page, node_path_1.default.join(artifactsDir, 'review-overview.png'));
        await page.getByTestId('decision-os-artifact-run').selectOption('run-candidate');
        await page
            .getByTestId('decision-os-artifact-retrain-vs-rollback')
            .waitFor({ state: 'visible', timeout: 30000 });
        await page.getByTestId('decision-os-artifact-toggle-retrain-vs-rollback').click();
        await page
            .getByTestId('decision-os-artifact-narrative-retrain-vs-rollback')
            .waitFor({ state: 'visible', timeout: 30000 });
        await page.getByTestId('decision-os-run-diff-base').selectOption('run-champion');
        await page.getByTestId('decision-os-run-diff-candidate').selectOption('run-candidate');
        await page.getByTestId('decision-os-run-diff-compare').click();
        await page
            .getByTestId('decision-os-run-diff-result')
            .waitFor({ state: 'visible', timeout: 30000 });
        await page.getByText('New: monitor feature freshness after promotion').waitFor({
            state: 'visible',
            timeout: 30000,
        });
        await screenshot(page, node_path_1.default.join(artifactsDir, 'review-run-diff.png'));
        await page.getByTestId('decision-os-run-diff-open-promotion').click();
        await page
            .getByTestId('decision-os-promotion-gate-modal')
            .waitFor({ state: 'visible', timeout: 30000 });
        await page.getByTestId('decision-os-promotion-stage').selectOption('staging');
        await page.getByTestId('decision-os-promotion-submit').click();
        await page
            .getByTestId('decision-os-promotion-result')
            .waitFor({ state: 'visible', timeout: 30000 });
        await page
            .getByTestId('decision-os-promotion-result')
            .getByText('pending_DS')
            .waitFor({ state: 'visible', timeout: 30000 });
        await screenshot(page, node_path_1.default.join(artifactsDir, 'review-promotion-gate.png'));
        await page.getByTestId('decision-os-promotion-close').click();
        await waitForNumericTestIdAtLeast(page, 'decision-os-overview-decision-count', 1);
        await page.getByTestId('decision-os-post-deploy-model').selectOption('m_churn_lightgbm');
        await page.getByTestId('decision-os-post-deploy-window').fill('7d');
        await page.getByTestId('decision-os-post-deploy-load').click();
        await page
            .getByTestId('decision-os-post-deploy-result')
            .waitFor({ state: 'visible', timeout: 30000 });
        await page.getByTestId('decision-os-post-deploy-alerts').waitFor({
            state: 'visible',
            timeout: 30000,
        });
        await page.getByText('Drift threshold exceeded').waitFor({
            state: 'visible',
            timeout: 30000,
        });
        await screenshot(page, node_path_1.default.join(artifactsDir, 'review-post-deploy-status.png'));
        console.log(`[e2e] PASS decision-os review flow. Artifacts: ${artifactsDir}`);
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
