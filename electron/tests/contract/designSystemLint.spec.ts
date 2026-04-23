import assert from 'node:assert/strict';

// eslint-disable-next-line @typescript-eslint/no-require-imports
const path = require('node:path');
// eslint-disable-next-line @typescript-eslint/no-require-imports
const lint = require(
  path.resolve(__dirname, '..', '..', '..', '..', 'scripts', 'lintDesignSystemCore.cjs'),
);

const scanSourceFile: (
  file: string,
  content: string,
) => Array<{ file: string; line: number; rule: string; value: string }> = lint.scanSourceFile;

function run(): void {
  {
    const violations = scanSourceFile(
      'src/renderer/design-system/primitives/Button.tsx',
      "export const Button = () => <div className=\"text-[#fff]\">x</div>;\n",
    );
    assert.equal(violations.length, 2);
    assert.equal(violations[0].rule, 'hex-literal');
    assert.equal(violations[1].rule, 'tailwind-arbitrary-value');
  }

  {
    const violations = scanSourceFile(
      'src/renderer/design-system/themes/dark.ts',
      "export const token = '#ffffff';\n",
    );
    assert.equal(violations.length, 0);
  }

  {
    const violations = scanSourceFile(
      'src/renderer/components/providers/ThemeProvider.tsx',
      "export const X = () => <div className=\"tracking-[0.18em]\" />;\n",
    );
    assert.equal(violations.length, 1);
    assert.equal(violations[0].rule, 'tailwind-arbitrary-value');
  }

  {
    const violations = scanSourceFile(
      'src/renderer/components/mission/MissionHeader.tsx',
      "export const X = () => <div className=\"tracking-[0.18em]\" />;\n",
    );
    assert.equal(violations.length, 0);
  }

  console.log('[contract] PASS design-system-lint (4 cases)');
}

run();
