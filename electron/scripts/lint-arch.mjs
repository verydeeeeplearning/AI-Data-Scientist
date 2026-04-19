#!/usr/bin/env node
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url));
const { scanProject } = require(resolve(here, 'lintArchCore.cjs'));

const root = resolve(here, '..', 'src', 'renderer');
const violations = scanProject(root);

if (violations.length === 0) {
  console.log('[lint:arch] OK — Clean Architecture layer rules respected (0 violations)');
  process.exit(0);
}

console.error(`[lint:arch] FAIL — ${violations.length} violation(s):`);
for (const v of violations) {
  console.error(`  ${v.file}:${v.line}  layer=${v.layer}  imported=${v.importedFrom}  rule=${v.rule}`);
}
process.exit(1);
