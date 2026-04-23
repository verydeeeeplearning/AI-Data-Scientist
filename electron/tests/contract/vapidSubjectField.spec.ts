import assert from 'node:assert/strict';

import {
  isValidVapidSubject,
  normalizeVapidSubject,
} from '../../src/mobile/components/VapidSubjectField';

interface TestCase {
  name: string;
  fn: () => void;
}

const tests: TestCase[] = [];

function test(name: string, fn: () => void): void {
  tests.push({ name, fn });
}

test('normalizeVapidSubject trims surrounding whitespace', () => {
  assert.equal(normalizeVapidSubject('  mailto:admin@example.com  '), 'mailto:admin@example.com');
});

test('isValidVapidSubject accepts mailto subjects', () => {
  assert.equal(isValidVapidSubject('mailto:admin@example.com'), true);
});

test('isValidVapidSubject accepts https subjects', () => {
  assert.equal(isValidVapidSubject('https://example.com/contact'), true);
});

test('isValidVapidSubject rejects unsupported schemes and blanks', () => {
  assert.equal(isValidVapidSubject('ftp://example.com'), false);
  assert.equal(isValidVapidSubject('   '), false);
  assert.equal(isValidVapidSubject('admin@example.com'), false);
});

let passed = 0;
let failed = 0;

for (const current of tests) {
  try {
    current.fn();
    console.log(`  ok  ${current.name}`);
    passed += 1;
  } catch (error) {
    console.error(`  FAIL ${current.name}`);
    console.error(`    ${(error as Error).message}`);
    failed += 1;
  }
}

console.log(
  `\nvapidSubjectField.spec - ${passed}/${passed + failed} passed${failed ? ` (${failed} failed)` : ''}`,
);

if (failed > 0) {
  process.exit(1);
}
