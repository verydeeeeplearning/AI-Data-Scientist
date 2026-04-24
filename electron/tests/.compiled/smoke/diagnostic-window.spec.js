"use strict";
/**
 * Smoke: backend startup failure surfaces the diagnostic window (P0-03).
 *
 * Forces the backend launcher to point at a non-existent binary via the
 * `DS_AGENT_BACKEND_COMMAND` env override. The main process should classify
 * the failure as BINARY_NOT_FOUND and open the diagnostic window.
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
        const panel = page.locator('main[aria-labelledby="diagnostic-title"]').first();
        await panel.waitFor({ state: 'visible', timeout: 30000 });
        const titleText = await page.locator('#diagnostic-title').textContent();
        const diagnosticJson = await page.locator('pre').first().textContent();
        const hasTitle = !!titleText?.trim();
        const hasBinaryNotFoundReason = diagnosticJson?.includes('"reason": "binary_not_found"') ?? false;
        if (!hasTitle || !hasBinaryNotFoundReason) {
            const html = await page.content();
            throw new Error(`Diagnostic window did not render expected failure details. ` +
                `Got title=${JSON.stringify(titleText)}, reasonHit=${hasBinaryNotFoundReason}\n` +
                `--- HTML (first 2 KB) ---\n${html.slice(0, 2048)}`);
        }
        console.log(`[smoke] PASS diagnostic title: ${titleText?.trim()}`);
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
