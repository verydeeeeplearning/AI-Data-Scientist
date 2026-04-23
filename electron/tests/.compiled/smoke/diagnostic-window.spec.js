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
const node_path_1 = __importDefault(require("node:path"));
const artifacts_1 = require("../e2e/_shared/artifacts");
const launcher_1 = require("../e2e/_shared/launcher");
const paths_1 = require("../e2e/_shared/paths");
const BAD_BINARY = node_path_1.default.join(paths_1.REPO_ROOT, 'this-binary-does-not-exist');
async function run() {
    const { app, page, isolated } = await (0, launcher_1.launchApp)('diagnostic-window', {
        skipBinaryCheck: true,
        extraEnv: { DS_AGENT_BACKEND_COMMAND: BAD_BINARY },
    });
    try {
        const titleText = await page.locator('h1').first().textContent({ timeout: 30000 });
        const ok = !!titleText && /Backend binary was not found/i.test(titleText);
        if (!ok) {
            const html = await page.content();
            throw new Error(`Diagnostic title not rendered as expected. Got: ${JSON.stringify(titleText)}\n` +
                `--- HTML (first 2 KB) ---\n${html.slice(0, 2048)}`);
        }
        console.log(`[smoke] PASS — diagnostic title: ${titleText}`);
    }
    catch (err) {
        await (0, artifacts_1.captureFailureArtifacts)(page, isolated.artifacts, 'diagnostic-window').catch(() => { });
        throw err;
    }
    finally {
        await app.close();
    }
}
run().catch((err) => {
    console.error('[smoke] FAIL:', err);
    process.exit(1);
});
