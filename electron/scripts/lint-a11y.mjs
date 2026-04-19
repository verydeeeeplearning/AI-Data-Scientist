#!/usr/bin/env node
// a11y CI step (cross_cutting/PLAN_01 Sub-Phase 1.1 + Phase B finalization).
//
// Strict mode (ADR-0010, supersedes placeholder policy of ADR-0008): the
// presence of @axe-core/playwright is now mandatory. Missing install → exit 1
// with an actionable message. Successful sanity check just verifies the
// AxeBuilder constructor can be imported; the actual scans live in
// tests/e2e/a11y/*.a11y.spec.ts and run via `npm run test:e2e:a11y`.

import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const require = createRequire(import.meta.url);
const __dirname = dirname(fileURLToPath(import.meta.url));

let axeModule;
try {
  axeModule = require('@axe-core/playwright');
} catch (err) {
  console.error('[lint:a11y] FAIL — @axe-core/playwright is not installed.');
  console.error('[lint:a11y]   Required by ADR-0010 (Wave 0–1 finalization Phase B).');
  console.error('[lint:a11y]   Run from electron/:');
  console.error('[lint:a11y]     npm install --save-dev @axe-core/playwright');
  console.error('[lint:a11y]   Underlying error: ' + (err && err.message ? err.message : String(err)));
  process.exit(1);
}

const AxeBuilder = axeModule.default ?? axeModule.AxeBuilder ?? axeModule;
if (typeof AxeBuilder !== 'function') {
  console.error('[lint:a11y] FAIL — @axe-core/playwright resolved but AxeBuilder is not a constructor.');
  console.error('[lint:a11y]   Got: ' + typeof AxeBuilder);
  process.exit(1);
}

let version = 'unknown';
try {
  const pkgPath = resolve(__dirname, '..', 'node_modules', '@axe-core', 'playwright', 'package.json');
  version = JSON.parse(readFileSync(pkgPath, 'utf8')).version;
} catch {
  // version string is informational only; missing metadata does not fail the gate.
}

console.log('[lint:a11y] OK — @axe-core/playwright loaded (version: ' + version + ').');
console.log('[lint:a11y]   Run E2E axe scans with: npm run test:e2e:a11y');
console.log('[lint:a11y]   Coverage: WCAG 2.1 A + AA on 5 surfaces (mission, onboarding, chat, settings, sidebar).');
process.exit(0);
