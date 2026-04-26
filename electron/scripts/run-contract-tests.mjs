import { spawnSync } from 'node:child_process';
import { existsSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const electronRoot = dirname(scriptDir);
const compiledRoot = join(electronRoot, 'tests', '.compiled-contract', 'tests', 'contract');
const filters = process.argv
  .slice(2)
  .filter((arg) => arg !== '--')
  .map((arg) => arg.toLowerCase());

function collectSpecs(dir) {
  if (!existsSync(dir)) {
    return [];
  }

  const specs = [];
  for (const entry of readdirSync(dir)) {
    const fullPath = join(dir, entry);
    const stat = statSync(fullPath);
    if (stat.isDirectory()) {
      specs.push(...collectSpecs(fullPath));
    } else if (entry.endsWith('.spec.js')) {
      specs.push(fullPath);
    }
  }
  return specs;
}

function matchesFilters(specPath) {
  if (filters.length === 0) {
    return true;
  }
  const normalized = relative(compiledRoot, specPath).replaceAll('\\', '/').toLowerCase();
  const withoutSuffix = normalized.replace(/\.spec\.js$/, '');
  return filters.some((filter) => normalized.includes(filter) || withoutSuffix.includes(filter));
}

const specs = collectSpecs(compiledRoot).filter(matchesFilters).sort();

if (specs.length === 0) {
  console.error(
    filters.length > 0
      ? `[contract] No compiled specs matched: ${filters.join(', ')}`
      : '[contract] No compiled specs found. Run tsc first.',
  );
  process.exit(1);
}

for (const spec of specs) {
  const result = spawnSync(process.execPath, [spec], {
    cwd: electronRoot,
    stdio: 'inherit',
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

console.log(`[contract] Completed ${specs.length} spec file(s).`);
