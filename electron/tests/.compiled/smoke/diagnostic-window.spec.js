"use strict";
/**
 * Smoke: backend startup failure surfaces the diagnostic window (P0-03).
 *
 * Forces the backend launcher to point at a non-existent binary via the
 * `DS_AGENT_BACKEND_COMMAND` env override. The main process should classify
 * the failure as BINARY_NOT_FOUND and open the diagnostic window with a
 * reason-specific title rendered by `DiagnosticPanel`.
 *
 * Runner: plain Node (no @playwright/test dependency). Exits non-zero on
 * failure for CI usability.
 */
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const playwright_1 = require("playwright");
const node_path_1 = __importDefault(require("node:path"));
// Paths are resolved relative to the npm script CWD (electron/) so the test
// works whether run from the source tree or after compilation to tests/.compiled.
const ELECTRON_DIR = process.cwd();
const REPO_ROOT = node_path_1.default.resolve(ELECTRON_DIR, '..');
const ELECTRON_MAIN = node_path_1.default.resolve(ELECTRON_DIR, 'dist', 'main', 'index.js');
const BAD_BINARY = node_path_1.default.join(REPO_ROOT, 'this-binary-does-not-exist');
async function run() {
    const app = await playwright_1._electron.launch({
        args: [ELECTRON_MAIN],
        cwd: REPO_ROOT,
        env: {
            ...process.env,
            DS_AGENT_BACKEND_COMMAND: BAD_BINARY,
            DS_AGENT_SENTRY_DSN: '',
            DS_AGENT_E2E_USE_BUILT_RENDERER: '1',
        },
    });
    try {
        const window = await app.firstWindow({ timeout: 30000 });
        await window.waitForLoadState('domcontentloaded');
        // DiagnosticPanel renders the classified failure title as <h1>.
        // For a missing backend binary the copy is "Backend binary was not found".
        const titleText = await window.locator('h1').first().textContent({ timeout: 30000 });
        const ok = !!titleText && /Backend binary was not found/i.test(titleText);
        if (!ok) {
            const html = await window.content();
            throw new Error(`Diagnostic title not rendered as expected. Got: ${JSON.stringify(titleText)}\n` +
                `--- HTML (first 2 KB) ---\n${html.slice(0, 2048)}`);
        }
        console.log(`[smoke] PASS — diagnostic title: ${titleText}`);
    }
    finally {
        await app.close();
    }
}
run().catch((err) => {
    console.error('[smoke] FAIL:', err);
    process.exit(1);
});
