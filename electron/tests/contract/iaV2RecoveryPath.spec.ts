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

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// __dirname at runtime is  <project>/tests/.compiled-contract/tests/contract/
// The TypeScript source lives at <project>/src/renderer/
// We need to climb four levels from the compiled output directory to reach the
// project root, then descend into src/renderer.
const ROOT = resolve(__dirname, '../../../../src/renderer');

function readSource(relativePath: string): string {
  return readFileSync(resolve(ROOT, relativePath), 'utf-8');
}

function run(): void {
  // -------------------------------------------------------------------------
  // Test 1: MissionPage renders MissionBriefPanel for the IA V2 recovery path
  // -------------------------------------------------------------------------
  {
    const source = readSource('pages/mission/MissionPage.tsx');

    // The import must reference MissionBriefPanel from the mission components.
    assert.match(
      source,
      /import\s*\{[^}]*MissionBriefPanel[^}]*\}\s*from\s*['"][^'"]*mission\/MissionBriefPanel['"]/,
      'MissionPage.tsx must import MissionBriefPanel from the mission components directory',
    );

    // The JSX must include a <MissionBriefPanel usage (self-closing or opening tag).
    assert.match(
      source,
      /<MissionBriefPanel\s*(\/?>|[^/])/,
      'MissionPage.tsx must render <MissionBriefPanel> in its JSX tree',
    );
  }

  // -------------------------------------------------------------------------
  // Test 2: MissionBriefPanel exposes the "Draft Contract" CTA for the
  //         no-contract recovery state.
  // -------------------------------------------------------------------------
  {
    const source = readSource('components/mission/MissionBriefPanel.tsx');

    // The CTA button must carry the agreed data-testid so Playwright / a11y
    // tests can locate it without relying on text content or visual position.
    assert.match(
      source,
      /data-testid="mission-brief-create-contract-cta"/,
      'MissionBriefPanel.tsx must expose data-testid="mission-brief-create-contract-cta" for the no-contract recovery CTA',
    );

    // The CTA must be inside the no-contract conditional block — confirm the
    // button text ("Draft Contract") is adjacent to the test-id in source.
    assert.match(
      source,
      /data-testid="mission-brief-create-contract-cta"[^<]*>[\s\S]{0,200}Draft Contract/,
      'The mission-brief-create-contract-cta element must contain "Draft Contract" label text',
    );
  }

  console.log('[contract] PASS ia-v2-recovery-path (2 cases)');
}

run();
