"use strict";
/**
 * Smoke: happy-path Electron startup with the packaged backend binary.
 *
 * Launches Electron, lets the main process spawn the real PyInstaller
 * backend, and asserts the renderer reaches the post-handshake UI
 * (OnboardingWizard's "DS Agent" hero shown on first launch). This
 * exercises the full chain: backend READY emit → /health probe → window
 * navigation → WebSocket handshake → first-paint of app UI.
 *
 * Runner: plain Node (no @playwright/test). Exits non-zero on failure.
 */
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const playwright_1 = require("playwright");
const node_path_1 = __importDefault(require("node:path"));
const node_fs_1 = __importDefault(require("node:fs"));
const ELECTRON_DIR = process.cwd();
const REPO_ROOT = node_path_1.default.resolve(ELECTRON_DIR, '..');
const ELECTRON_MAIN = node_path_1.default.resolve(ELECTRON_DIR, 'dist', 'main', 'index.js');
const BACKEND_BIN = node_path_1.default.resolve(REPO_ROOT, 'dist', 'ds-agent-backend', process.platform === 'win32' ? 'ds-agent-api.exe' : 'ds-agent-api');
async function run() {
    if (!node_fs_1.default.existsSync(BACKEND_BIN)) {
        throw new Error(`Backend binary not found at ${BACKEND_BIN}. ` +
            `Run "python scripts/build_backend.py" first.`);
    }
    const app = await playwright_1._electron.launch({
        args: [ELECTRON_MAIN],
        cwd: REPO_ROOT,
        env: {
            ...process.env,
            DS_AGENT_BACKEND_COMMAND: BACKEND_BIN,
            DS_AGENT_SENTRY_DSN: '',
            DS_AGENT_E2E_USE_BUILT_RENDERER: '1',
        },
        timeout: 60000,
    });
    try {
        const window = await app.firstWindow({ timeout: 60000 });
        await window.waitForLoadState('domcontentloaded');
        // Fail fast if main process classified the backend as failed and routed
        // us to the diagnostic window instead of the main UI.
        const hero = window.locator('h1', { hasText: /DS Agent/i }).first();
        await hero.waitFor({ state: 'visible', timeout: 60000 });
        const heroText = await hero.textContent();
        if (!heroText || !/DS Agent/i.test(heroText)) {
            const html = await window.content();
            throw new Error(`Hero not rendered. Got: ${JSON.stringify(heroText)}\n` +
                `--- HTML (first 2 KB) ---\n${html.slice(0, 2048)}`);
        }
        // Diagnostic title would override hero on failure — make absolutely sure
        // the diagnostic window did NOT open instead.
        const diagnosticHit = await window
            .locator('h1', { hasText: /Backend|Failed to start/i })
            .count();
        if (diagnosticHit > 0) {
            throw new Error(`Diagnostic window appeared instead of main UI. ` +
                `Backend handshake likely failed.`);
        }
        console.log(`[smoke] PASS — main UI hero rendered: ${heroText.trim()}`);
    }
    finally {
        await app.close();
    }
}
run().catch((err) => {
    console.error('[smoke] FAIL:', err);
    process.exit(1);
});
