"use strict";
/**
 * Contract: IA V2 Recovery Path (Gap 1B-2)
 *
 * Verifies that the renderer-level wiring for the IA V2 no-contract recovery
 * path is in place:
 *
 *   1. MissionPage imports and renders MissionBriefPanel — so the panel is
 *      always present in the mission route, not hidden behind a gate.
 *
 *   2. MissionBriefPanel exposes data-testid="mission-brief-create-contract-cta"
 *      — the "Draft Contract" CTA that surfaces in the no-contract state, giving
 *      operators a recovery path without requiring a full Electron e2e run.
 *
 * These are intentionally source-level checks so that the tests remain fast and
 * runnable in CI without a display server or Electron process.
 */
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const node_fs_1 = require("node:fs");
const node_path_1 = require("node:path");
// __dirname at runtime is  <project>/tests/.compiled-contract/tests/contract/
// The TypeScript source lives at <project>/src/renderer/
// We need to climb four levels from the compiled output directory to reach the
// project root, then descend into src/renderer.
const ROOT = (0, node_path_1.resolve)(__dirname, '../../../../src/renderer');
function readSource(relativePath) {
    return (0, node_fs_1.readFileSync)((0, node_path_1.resolve)(ROOT, relativePath), 'utf-8');
}
function run() {
    // -------------------------------------------------------------------------
    // Test 1: MissionPage renders MissionBriefPanel for the IA V2 recovery path
    // -------------------------------------------------------------------------
    {
        const source = readSource('pages/mission/MissionPage.tsx');
        // The import must reference MissionBriefPanel from the mission components.
        strict_1.default.match(source, /import\s*\{[^}]*MissionBriefPanel[^}]*\}\s*from\s*['"][^'"]*mission\/MissionBriefPanel['"]/, 'MissionPage.tsx must import MissionBriefPanel from the mission components directory');
        // The JSX must include a <MissionBriefPanel usage (self-closing or opening tag).
        strict_1.default.match(source, /<MissionBriefPanel\s*(\/?>|[^/])/, 'MissionPage.tsx must render <MissionBriefPanel> in its JSX tree');
    }
    // -------------------------------------------------------------------------
    // Test 2: MissionBriefPanel exposes the "Draft Contract" CTA for the
    //         no-contract recovery state.
    // -------------------------------------------------------------------------
    {
        const source = readSource('components/mission/MissionBriefPanel.tsx');
        // The CTA button must carry the agreed data-testid so Playwright / a11y
        // tests can locate it without relying on text content or visual position.
        strict_1.default.match(source, /data-testid="mission-brief-create-contract-cta"/, 'MissionBriefPanel.tsx must expose data-testid="mission-brief-create-contract-cta" for the no-contract recovery CTA');
        // The CTA must be inside the no-contract conditional block — confirm the
        // button text ("Draft Contract") is adjacent to the test-id in source.
        strict_1.default.match(source, /data-testid="mission-brief-create-contract-cta"[^<]*>[\s\S]{0,200}Draft Contract/, 'The mission-brief-create-contract-cta element must contain "Draft Contract" label text');
    }
    console.log('[contract] PASS ia-v2-recovery-path (2 cases)');
}
run();
