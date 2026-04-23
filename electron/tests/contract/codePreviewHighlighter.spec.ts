/**
 * Contract test for the lightweight syntax highlighter used by the
 * SandboxApprovalModal code preview.
 */

import assert from 'node:assert/strict';
import {
  highlightLine,
  normalizeHighlightLanguage,
  tokenClassName,
} from '../../src/renderer/components/approval/codePreviewHighlighter';

const results: Array<{ name: string; ok: boolean; error?: unknown }> = [];

function test(name: string, fn: () => void): void {
  try {
    fn();
    results.push({ name, ok: true });
  } catch (error) {
    results.push({ name, ok: false, error });
  }
}

test('normalizeHighlightLanguage falls back to plain for unknown languages', () => {
  assert.equal(normalizeHighlightLanguage(undefined), 'plain');
  assert.equal(normalizeHighlightLanguage('  '), 'plain');
  assert.equal(normalizeHighlightLanguage('Cobol'), 'plain');
  assert.equal(normalizeHighlightLanguage('Python'), 'python');
});

test('python highlighter classifies keywords, comments, strings, numbers', () => {
  const line = 'def main():  # entry';
  const tokens = highlightLine(line, 'python');
  const def = tokens.find((token) => token.text === 'def');
  assert.ok(def && def.kind === 'keyword');
  const comment = tokens.find((token) => token.text === '# entry');
  assert.ok(comment && comment.kind === 'comment');

  const numericTokens = highlightLine('x = 42', 'python');
  const number = numericTokens.find((token) => token.text === '42');
  assert.ok(number && number.kind === 'number');

  const stringTokens = highlightLine('print("hi")', 'python');
  const stringToken = stringTokens.find((token) => token.text === '"hi"');
  assert.ok(stringToken && stringToken.kind === 'string');
});

test('sql highlighter is case insensitive for keywords', () => {
  const tokens = highlightLine('SELECT id FROM users', 'sql');
  const select = tokens.find((token) => token.text === 'SELECT');
  const from = tokens.find((token) => token.text === 'FROM');
  assert.ok(select && select.kind === 'keyword');
  assert.ok(from && from.kind === 'keyword');
});

test('plain language returns text without keyword highlighting', () => {
  const tokens = highlightLine('def main():', 'plain');
  const def = tokens.find((token) => token.text === 'def');
  assert.ok(!def || def.kind !== 'keyword');
});

test('tokenClassName maps every token kind to a non-throwing string', () => {
  for (const kind of ['keyword', 'comment', 'string', 'number', 'plain'] as const) {
    const className = tokenClassName(kind);
    assert.equal(typeof className, 'string');
  }
});

test('highlightLine round-trips line content for plain text segments', () => {
  const tokens = highlightLine('hello world', 'plain');
  const reconstructed = tokens.map((token) => token.text).join('');
  assert.equal(reconstructed, 'hello world');
});

test('highlightLine handles empty string without throwing', () => {
  assert.deepEqual(highlightLine('', 'python'), []);
});

const failed = results.filter((entry) => !entry.ok);
for (const entry of results) {
  console.log(`  ${entry.ok ? 'ok' : 'FAIL'}  ${entry.name}`);
  if (!entry.ok) {
    console.log('       ', entry.error);
  }
}
console.log(
  `\ncodePreviewHighlighter.spec — ${results.length - failed.length}/${results.length} passed`,
);
if (failed.length > 0) {
  process.exitCode = 1;
}
