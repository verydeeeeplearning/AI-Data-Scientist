import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import path from 'node:path';

function run(): void {
  const repoRoot = path.resolve(__dirname, '..', '..', '..', '..');
  const output = execFileSync(
    process.execPath,
    ['scripts/audit-design-system-usage.mjs', '--json'],
    {
      cwd: repoRoot,
      encoding: 'utf8',
    },
  );

  const audit = JSON.parse(output) as {
    overallPassed: boolean;
    storybook: { exports: number; passed: boolean };
    wave4SurfaceAdoption: { percentage: number; passed: boolean };
    legacyMigration: { percentage: number; passed: boolean };
  };

  assert.equal(typeof audit.storybook.exports, 'number');
  assert.equal(typeof audit.wave4SurfaceAdoption.percentage, 'number');
  assert.equal(typeof audit.legacyMigration.percentage, 'number');
  assert.ok(audit.storybook.exports >= 50);
  assert.ok(audit.wave4SurfaceAdoption.percentage >= 80);
  assert.ok(audit.legacyMigration.percentage >= 30);
  assert.equal(audit.storybook.passed, true);
  assert.equal(audit.wave4SurfaceAdoption.passed, true);
  assert.equal(audit.legacyMigration.passed, true);
  assert.equal(audit.overallPassed, true);

  console.log('[contract] PASS design-system-audit (4 cases)');
}

run();
