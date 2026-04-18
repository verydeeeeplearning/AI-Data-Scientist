"use strict";
/**
 * E2E: Mission Brief lifecycle flow for a seeded task contract.
 *
 * Covers edit, agree, start-work, review, and close transitions against the
 * packaged backend with a seeded contract that already has close prerequisites.
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
const SEEDED_SESSION_ID = 'seeded-task-contract-session';
function ensureDir(target) {
    node_fs_1.default.mkdirSync(target, { recursive: true });
}
function buildIsolatedPaths() {
    const rootDir = node_fs_1.default.mkdtempSync(node_path_1.default.join(node_os_1.default.tmpdir(), 'ds-agent-task-contract-lifecycle-'));
    const workspaceDir = node_path_1.default.join(rootDir, 'workspace');
    const configDir = node_path_1.default.join(rootDir, 'config');
    const configPath = node_path_1.default.join(configDir, 'config.yaml');
    [workspaceDir, configDir].forEach(ensureDir);
    return {
        rootDir,
        workspaceDir,
        configDir,
        configPath,
    };
}
function seedWorkspace(configPath, workspaceDir) {
    const scriptPath = node_path_1.default.resolve(REPO_ROOT, 'scripts', 'seed_task_contract_lifecycle_e2e_workspace.py');
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
    throw new Error(lastError ?? 'Failed to seed task-contract lifecycle E2E workspace.');
}
async function waitForTextContains(page, testId, needle) {
    await page.waitForFunction(({ currentTestId, currentNeedle }) => {
        const node = document.querySelector(`[data-testid="${currentTestId}"]`);
        return Boolean(node?.textContent?.includes(currentNeedle));
    }, { currentTestId: testId, currentNeedle: needle }, { timeout: 30000 });
}
async function waitForClosedOrThrow(page) {
    try {
        await waitForTextContains(page, 'mission-brief-status-badge', 'closed');
        return;
    }
    catch (error) {
        const actionError = await page.getByTestId('mission-brief-action-error').textContent().catch(() => null);
        const actionNotice = await page
            .getByTestId('mission-brief-action-notice')
            .textContent()
            .catch(() => null);
        throw new Error(`close transition did not reach closed. actionError=${JSON.stringify(actionError)} `
            + `actionNotice=${JSON.stringify(actionNotice)} original=${String(error)}`);
    }
}
async function run() {
    if (!node_fs_1.default.existsSync(BACKEND_BIN)) {
        throw new Error(`Backend binary not found at ${BACKEND_BIN}. ` +
            `Run "python scripts/build_backend.py" first.`);
    }
    const paths = buildIsolatedPaths();
    seedWorkspace(paths.configPath, paths.workspaceDir);
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
    try {
        const page = await app.firstWindow({ timeout: 60000 });
        await page.waitForLoadState('domcontentloaded');
        await page.getByTestId('open-settings').waitFor({ state: 'visible', timeout: 60000 });
        await page.getByTestId('sidebar-tab-runtime').click();
        await page.getByTestId(`open-session-${SEEDED_SESSION_ID}`).waitFor({
            state: 'visible',
            timeout: 30000,
        });
        await page.getByTestId(`open-session-${SEEDED_SESSION_ID}`).click();
        await page.getByTestId('sidebar-tab-workflow').click();
        await page.getByTestId('mission-brief-panel').waitFor({ state: 'visible', timeout: 30000 });
        await page.getByTestId('mission-brief-action-edit').waitFor({
            state: 'visible',
            timeout: 30000,
        });
        await waitForTextContains(page, 'mission-brief-status-badge', 'draft');
        await page.getByTestId('mission-brief-action-edit').click();
        await page.getByTestId('contract-editor').waitFor({ state: 'visible', timeout: 30000 });
        await page
            .getByTestId('contract-editor-business-goal')
            .fill('Prepare a retention-risk readout with explicit owner-ready next actions.');
        await page.getByTestId('contract-editor-decision-owner').fill('retention-lead@corp');
        await page.getByTestId('contract-editor-save').click();
        await waitForTextContains(page, 'mission-brief-business-goal', 'Prepare a retention-risk readout with explicit owner-ready next actions.');
        await waitForTextContains(page, 'mission-brief-decision-owner', 'retention-lead@corp');
        await page.getByTestId('mission-brief-action-agree').click();
        await waitForTextContains(page, 'mission-brief-status-badge', 'agreed');
        await page.getByTestId('mission-brief-action-start-work').click();
        await waitForTextContains(page, 'mission-brief-status-badge', 'in_progress');
        await page.getByTestId('mission-brief-action-send-review').click();
        await waitForTextContains(page, 'mission-brief-status-badge', 'review');
        await page.getByTestId('mission-brief-action-close').click();
        await page.getByTestId('mission-brief-close-dialog').waitFor({
            state: 'visible',
            timeout: 30000,
        });
        await page
            .getByTestId('mission-brief-close-note')
            .fill('Operator verified all closure criteria.');
        await page.getByTestId('mission-brief-close-confirm').click();
        await waitForClosedOrThrow(page);
        await page.getByText('DoD Summary').waitFor({ state: 'visible', timeout: 30000 });
        console.log('[e2e] PASS task-contract lifecycle flow.');
    }
    finally {
        await app.close();
    }
}
run().catch((error) => {
    console.error('[e2e] FAIL:', error);
    process.exit(1);
});
