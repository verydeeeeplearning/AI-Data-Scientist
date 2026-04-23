#!/usr/bin/env node
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url));
const { scanProject } = require(resolve(here, 'lintDesignSystemCore.cjs'));

const root = resolve(here, '..', 'src', 'renderer');
const violations = scanProject(root);

if (violations.length === 0) {
  console.log('[lint:design-system] OK - managed design-system surfaces stay token-driven');
  process.exit(0);
}

console.error(`[lint:design-system] FAIL - ${violations.length} violation(s):`);
for (const violation of violations) {
  console.error(
    `  ${violation.file}:${violation.line}  rule=${violation.rule}  value=${violation.value}`,
  );
}
process.exit(1);

