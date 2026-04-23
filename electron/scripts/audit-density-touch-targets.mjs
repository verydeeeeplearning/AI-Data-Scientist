#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, '..');

const PRIMITIVES_DIR = path.join(
  repoRoot,
  'src',
  'renderer',
  'design-system',
  'primitives',
);

// WCAG 2.5.5 minimum target size = 44 × 44 CSS px.
// Tailwind's default spacing scale uses 0.25rem per step → at 16px root the threshold is 11 steps.
const MIN_TAILWIND_STEPS = 11;

const TARGETS = [
  { file: 'Button.tsx', label: 'Button', interactive: 'root button' },
  { file: 'Select.tsx', label: 'Select', interactive: 'select element' },
  { file: 'Tabs.tsx', label: 'Tabs', interactive: 'tab button' },
  { file: 'Checkbox.tsx', label: 'Checkbox', interactive: 'label wrapper' },
  { file: 'Radio.tsx', label: 'Radio', interactive: 'label wrapper' },
  { file: 'Toast.tsx', label: 'Toast.dismiss', interactive: 'dismiss button' },
  { file: 'DrawerShell.tsx', label: 'DrawerShell.dismiss', interactive: 'dismiss button' },
];

// Each primitive must declare at least one Tailwind hit-target token whose step >= 11.
// We look across all string literals concatenated in the file and pick the MAXIMUM step
// for `min-h-N` / `h-N`. Width is enforced when the file contains an icon-button pattern
// (`h-N w-N` with same N — square element). For row-style hit targets we treat width as fluid.
const HIT_TARGET_HEIGHT_RE = /\b(?:min-h|h)-(\d+)\b/g;
const SQUARE_HIT_TARGET_RE = /\b(?:h-(\d+)\s+w-\1|w-(\d+)\s+h-\2)\b/g;

// Density-scaled hit target (excludes max-w/max-h container caps).
const DENSITY_HIT_TARGET_RE = /(?<!max-)\b(?:min-h|min-w|h|w)-ds-\w+/g;

function read(file) {
  return fs.readFileSync(path.join(PRIMITIVES_DIR, file), 'utf8');
}

function maxHeightStep(content) {
  let best = 0;
  for (const match of content.matchAll(HIT_TARGET_HEIGHT_RE)) {
    const numeric = Number(match[1]);
    if (Number.isFinite(numeric) && numeric > best) {
      best = numeric;
    }
  }
  return best;
}

function smallestSquareTarget(content) {
  // Returns the smallest "square hit target" (h-N w-N) used in the file, or null if none.
  let smallest = null;
  for (const match of content.matchAll(SQUARE_HIT_TARGET_RE)) {
    const numeric = Number(match[1] ?? match[2]);
    if (!Number.isFinite(numeric)) continue;
    if (smallest === null || numeric < smallest) smallest = numeric;
  }
  return smallest;
}

function densityHitTargetTokens(content) {
  return [...content.matchAll(DENSITY_HIT_TARGET_RE)].map((match) => match[0]);
}

function auditTarget(target) {
  const filePath = path.join(PRIMITIVES_DIR, target.file);
  if (!fs.existsSync(filePath)) {
    return { target, status: 'missing', violations: [`file not found: ${target.file}`] };
  }
  const content = read(target.file);
  const violations = [];

  const heightStep = maxHeightStep(content);
  if (heightStep < MIN_TAILWIND_STEPS) {
    violations.push(
      `${target.label}: tallest hit-target token is min-h-${heightStep || 0} / h-${heightStep || 0} (< 44px). Add min-h-11 (or larger) to the ${target.interactive}.`,
    );
  }

  // Icon-square hit targets (e.g., dismiss buttons rendered as h-N w-N icons).
  // Flag only when the file has no min-h-11+ guard at all (i.e., the square IS the hit target).
  // If min-h-11 already exists elsewhere in the file, the actual hit-target is guarded and
  // the small h-N w-N element is treated as a decorative inner mark (Checkbox/Radio pattern).
  const square = smallestSquareTarget(content);
  const hasHeightGuard = /\bmin-h-(?:1[1-9]|[2-9]\d)\b/.test(content);
  const hasWidthGuard = /\bmin-w-(?:1[1-9]|[2-9]\d)\b/.test(content);
  if (
    square !== null &&
    square < MIN_TAILWIND_STEPS &&
    !hasHeightGuard &&
    !hasWidthGuard
  ) {
    violations.push(
      `${target.label}: icon-square hit target h-${square} w-${square} (= ${square * 4}px) is below 44 × 44 and the file lacks any min-h-11/min-w-11 guard. Add min-w-11 min-h-11 to the ${target.interactive} (visual size can stay smaller via padding).`,
    );
  }

  const densityTokens = densityHitTargetTokens(content);
  if (densityTokens.length > 0) {
    violations.push(
      `${target.label}: density-scaled hit-target tokens detected (${densityTokens.join(', ')}). Hit targets MUST use fixed Tailwind steps so compact mode (0.75x) does not shrink them below 44px.`,
    );
  }

  return {
    target,
    heightStep,
    square,
    status: violations.length === 0 ? 'pass' : 'fail',
    violations,
  };
}

export function runAudit() {
  return TARGETS.map(auditTarget);
}

const results = runAudit();
const failures = results.filter((result) => result.status !== 'pass');

if (process.argv.includes('--json')) {
  console.log(JSON.stringify({ results, failures }, null, 2));
} else {
  for (const result of results) {
    if (result.status === 'pass') {
      console.log(
        `[audit:density-a11y] PASS ${result.target.label} (max h step ${result.heightStep}, min square ${result.square ?? 'n/a'})`,
      );
    } else {
      console.log(`[audit:density-a11y] FAIL ${result.target.label}`);
      for (const violation of result.violations) {
        console.log(`  - ${violation}`);
      }
    }
  }
  console.log(
    `[audit:density-a11y] overall=${failures.length === 0 ? 'PASS' : 'FAIL'} (${results.length - failures.length}/${results.length})`,
  );
}

process.exit(failures.length === 0 ? 0 : 1);
