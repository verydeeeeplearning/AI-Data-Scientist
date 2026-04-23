import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

// __dirname resolves inside `tests/.compiled-contract/tests/contract/`; climb 4 levels to electron/.
const ELECTRON_ROOT = path.resolve(__dirname, '..', '..', '..', '..');
const PRIMITIVES_DIR = path.join(
  ELECTRON_ROOT,
  'src',
  'renderer',
  'design-system',
  'primitives',
);

const REQUIRED_PRIMITIVES = ['Button', 'Card', 'DialogShell', 'Input', 'Tabs'] as const;
const REQUIRED_DENSITY_STORIES = [
  'CompactDensity',
  'ComfortableDensity',
  'SpaciousDensity',
] as const;
const REQUIRED_DATA_DENSITY_VALUES = ['compact', 'comfortable', 'spacious'] as const;

function readStoryFile(primitive: string): string {
  const file = path.join(PRIMITIVES_DIR, `${primitive}.stories.tsx`);
  return fs.readFileSync(file, 'utf8');
}

function exportedConsts(content: string): readonly string[] {
  return [...content.matchAll(/^export const (\w+)/gm)].map((match) => match[1]);
}

function run(): void {
  let totalChecks = 0;

  for (const primitive of REQUIRED_PRIMITIVES) {
    const content = readStoryFile(primitive);
    const exports = exportedConsts(content);

    for (const story of REQUIRED_DENSITY_STORIES) {
      assert.ok(
        exports.includes(story),
        `${primitive}.stories.tsx must export "${story}" story`,
      );
      totalChecks += 1;
    }

    assert.match(
      content,
      /applyDensityScale/,
      `${primitive}.stories.tsx must import applyDensityScale to scope CSS variables`,
    );
    totalChecks += 1;

    assert.match(
      content,
      /data-density=\{mode\}/,
      `${primitive}.stories.tsx must wrap density showcases in [data-density={mode}]`,
    );
    totalChecks += 1;

    for (const value of REQUIRED_DATA_DENSITY_VALUES) {
      const pattern = new RegExp(`mode=["']${value}["']`);
      assert.match(
        content,
        pattern,
        `${primitive}.stories.tsx must invoke a density showcase with mode="${value}"`,
      );
      totalChecks += 1;
    }
  }

  console.log(`[contract] PASS density-storybook-coverage (${totalChecks} cases)`);
}

run();
