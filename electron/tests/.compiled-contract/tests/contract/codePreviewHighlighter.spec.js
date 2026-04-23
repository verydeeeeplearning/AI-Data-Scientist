"use strict";
/**
 * Contract test for the lightweight syntax highlighter used by the
 * SandboxApprovalModal code preview.
 */
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const codePreviewHighlighter_1 = require("../../src/renderer/components/approval/codePreviewHighlighter");
const results = [];
function test(name, fn) {
    try {
        fn();
        results.push({ name, ok: true });
    }
    catch (error) {
        results.push({ name, ok: false, error });
    }
}
test('normalizeHighlightLanguage falls back to plain for unknown languages', () => {
    strict_1.default.equal((0, codePreviewHighlighter_1.normalizeHighlightLanguage)(undefined), 'plain');
    strict_1.default.equal((0, codePreviewHighlighter_1.normalizeHighlightLanguage)('  '), 'plain');
    strict_1.default.equal((0, codePreviewHighlighter_1.normalizeHighlightLanguage)('Cobol'), 'plain');
    strict_1.default.equal((0, codePreviewHighlighter_1.normalizeHighlightLanguage)('Python'), 'python');
});
test('python highlighter classifies keywords, comments, strings, numbers', () => {
    const line = 'def main():  # entry';
    const tokens = (0, codePreviewHighlighter_1.highlightLine)(line, 'python');
    const def = tokens.find((token) => token.text === 'def');
    strict_1.default.ok(def && def.kind === 'keyword');
    const comment = tokens.find((token) => token.text === '# entry');
    strict_1.default.ok(comment && comment.kind === 'comment');
    const numericTokens = (0, codePreviewHighlighter_1.highlightLine)('x = 42', 'python');
    const number = numericTokens.find((token) => token.text === '42');
    strict_1.default.ok(number && number.kind === 'number');
    const stringTokens = (0, codePreviewHighlighter_1.highlightLine)('print("hi")', 'python');
    const stringToken = stringTokens.find((token) => token.text === '"hi"');
    strict_1.default.ok(stringToken && stringToken.kind === 'string');
});
test('sql highlighter is case insensitive for keywords', () => {
    const tokens = (0, codePreviewHighlighter_1.highlightLine)('SELECT id FROM users', 'sql');
    const select = tokens.find((token) => token.text === 'SELECT');
    const from = tokens.find((token) => token.text === 'FROM');
    strict_1.default.ok(select && select.kind === 'keyword');
    strict_1.default.ok(from && from.kind === 'keyword');
});
test('plain language returns text without keyword highlighting', () => {
    const tokens = (0, codePreviewHighlighter_1.highlightLine)('def main():', 'plain');
    const def = tokens.find((token) => token.text === 'def');
    strict_1.default.ok(!def || def.kind !== 'keyword');
});
test('tokenClassName maps every token kind to a non-throwing string', () => {
    for (const kind of ['keyword', 'comment', 'string', 'number', 'plain']) {
        const className = (0, codePreviewHighlighter_1.tokenClassName)(kind);
        strict_1.default.equal(typeof className, 'string');
    }
});
test('highlightLine round-trips line content for plain text segments', () => {
    const tokens = (0, codePreviewHighlighter_1.highlightLine)('hello world', 'plain');
    const reconstructed = tokens.map((token) => token.text).join('');
    strict_1.default.equal(reconstructed, 'hello world');
});
test('highlightLine handles empty string without throwing', () => {
    strict_1.default.deepEqual((0, codePreviewHighlighter_1.highlightLine)('', 'python'), []);
});
const failed = results.filter((entry) => !entry.ok);
for (const entry of results) {
    console.log(`  ${entry.ok ? 'ok' : 'FAIL'}  ${entry.name}`);
    if (!entry.ok) {
        console.log('       ', entry.error);
    }
}
console.log(`\ncodePreviewHighlighter.spec — ${results.length - failed.length}/${results.length} passed`);
if (failed.length > 0) {
    process.exitCode = 1;
}
