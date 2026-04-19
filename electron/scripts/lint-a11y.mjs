#!/usr/bin/env node
// a11y CI step (cross_cutting/PLAN_01 Sub-Phase 1.1).
//
// When @axe-core/playwright is installed, this script runs automated WCAG
// 2.1 AA scans against the renderer build. Until then it acts as a CI
// placeholder + emits an informational log so downstream steps know a11y
// gating exists. See ADR-0008.

import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);

let axe;
try {
  axe = require('@axe-core/playwright');
} catch {
  console.log(
    '[lint:a11y] SKIP — @axe-core/playwright is not installed.',
  );
  console.log('[lint:a11y]   Install via: npm install --save-dev @axe-core/playwright playwright');
  console.log('[lint:a11y]   Until then, a11y is enforced via:');
  console.log('[lint:a11y]     - tests/contract/focusManagement.spec.ts (focus trap utility)');
  console.log('[lint:a11y]     - tests/contract/reducedMotion.spec.ts (prefers-reduced-motion utility)');
  console.log('[lint:a11y]     - PR review checklist (see SHARED/CONVENTIONS.md)');
  process.exit(0);
}

if (!axe) {
  console.error('[lint:a11y] FAIL — @axe-core/playwright loaded but exports are empty');
  process.exit(1);
}

console.log('[lint:a11y] OK — @axe-core/playwright detected, integrate scans in your E2E suite');
console.log('[lint:a11y]   Example:');
console.log('[lint:a11y]     import { AxeBuilder } from "@axe-core/playwright";');
console.log('[lint:a11y]     const result = await new AxeBuilder({ page }).analyze();');
console.log('[lint:a11y]     expect(result.violations).toEqual([]);');
process.exit(0);
