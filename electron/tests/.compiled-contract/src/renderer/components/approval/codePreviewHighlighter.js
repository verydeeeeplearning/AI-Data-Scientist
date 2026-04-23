"use strict";
/**
 * Lightweight syntax highlighter for the approval modal code preview.
 *
 * No external dependency. Tokenises one line at a time into spans with
 * deterministic class names so the modal can render coloured tokens via
 * tailwind utility classes. Supports python / sql / bash / shell / json /
 * javascript / typescript with conservative heuristics that prefer leaving
 * unknown text unstyled over miscolouring it.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.normalizeHighlightLanguage = normalizeHighlightLanguage;
exports.highlightLine = highlightLine;
exports.tokenClassName = tokenClassName;
const PYTHON_KEYWORDS = new Set([
    'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue', 'def', 'del',
    'elif', 'else', 'except', 'finally', 'for', 'from', 'global', 'if', 'import', 'in',
    'is', 'lambda', 'None', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'True',
    'False', 'try', 'while', 'with', 'yield',
]);
const SQL_KEYWORDS = new Set([
    'select', 'from', 'where', 'and', 'or', 'not', 'in', 'on', 'as', 'join', 'left', 'right',
    'inner', 'outer', 'full', 'group', 'by', 'having', 'order', 'limit', 'offset', 'union',
    'all', 'insert', 'into', 'values', 'update', 'set', 'delete', 'create', 'table', 'view',
    'index', 'drop', 'alter', 'with', 'case', 'when', 'then', 'else', 'end', 'distinct',
    'cast', 'is', 'null', 'true', 'false', 'between', 'like', 'exists',
]);
const BASH_KEYWORDS = new Set([
    'if', 'then', 'else', 'elif', 'fi', 'for', 'in', 'do', 'done', 'while', 'until', 'case',
    'esac', 'function', 'return', 'export', 'local', 'readonly', 'unset', 'echo', 'set',
    'source', 'cd', 'rm', 'mv', 'cp', 'mkdir', 'sudo', 'apt', 'yum', 'curl', 'wget',
]);
const JS_KEYWORDS = new Set([
    'await', 'break', 'case', 'catch', 'class', 'const', 'continue', 'debugger', 'default',
    'delete', 'do', 'else', 'enum', 'export', 'extends', 'false', 'finally', 'for', 'function',
    'if', 'import', 'in', 'instanceof', 'let', 'new', 'null', 'of', 'return', 'static',
    'super', 'switch', 'this', 'throw', 'true', 'try', 'typeof', 'undefined', 'var', 'void',
    'while', 'with', 'yield', 'async', 'as', 'from', 'interface', 'type', 'declare', 'readonly',
]);
const RULES_BY_LANGUAGE = {
    python: {
        keywords: PYTHON_KEYWORDS,
        comments: [/#.*$/y],
        strings: [
            /"(?:\\.|[^"\\])*"/y,
            /'(?:\\.|[^'\\])*'/y,
        ],
        identifierPattern: /[A-Za-z_][A-Za-z0-9_]*/y,
        numberPattern: /\d+(?:\.\d+)?/y,
        caseInsensitiveKeywords: false,
    },
    sql: {
        keywords: SQL_KEYWORDS,
        comments: [/--.*$/y],
        strings: [
            /"(?:""|[^"])*"/y,
            /'(?:''|[^'])*'/y,
        ],
        identifierPattern: /[A-Za-z_][A-Za-z0-9_]*/y,
        numberPattern: /\d+(?:\.\d+)?/y,
        caseInsensitiveKeywords: true,
    },
    bash: {
        keywords: BASH_KEYWORDS,
        comments: [/#.*$/y],
        strings: [
            /"(?:\\.|[^"\\])*"/y,
            /'[^']*'/y,
        ],
        identifierPattern: /[A-Za-z_][A-Za-z0-9_]*/y,
        numberPattern: /\d+(?:\.\d+)?/y,
        caseInsensitiveKeywords: false,
    },
    shell: {
        keywords: BASH_KEYWORDS,
        comments: [/#.*$/y],
        strings: [
            /"(?:\\.|[^"\\])*"/y,
            /'[^']*'/y,
        ],
        identifierPattern: /[A-Za-z_][A-Za-z0-9_]*/y,
        numberPattern: /\d+(?:\.\d+)?/y,
        caseInsensitiveKeywords: false,
    },
    sh: {
        keywords: BASH_KEYWORDS,
        comments: [/#.*$/y],
        strings: [
            /"(?:\\.|[^"\\])*"/y,
            /'[^']*'/y,
        ],
        identifierPattern: /[A-Za-z_][A-Za-z0-9_]*/y,
        numberPattern: /\d+(?:\.\d+)?/y,
        caseInsensitiveKeywords: false,
    },
    json: {
        keywords: new Set(['true', 'false', 'null']),
        comments: [],
        strings: [/"(?:\\.|[^"\\])*"/y],
        identifierPattern: /[A-Za-z_][A-Za-z0-9_]*/y,
        numberPattern: /-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/y,
        caseInsensitiveKeywords: false,
    },
    javascript: {
        keywords: JS_KEYWORDS,
        comments: [/\/\/.*$/y],
        strings: [
            /"(?:\\.|[^"\\])*"/y,
            /'(?:\\.|[^'\\])*'/y,
            /`(?:\\.|[^`\\])*`/y,
        ],
        identifierPattern: /[A-Za-z_$][A-Za-z0-9_$]*/y,
        numberPattern: /\d+(?:\.\d+)?/y,
        caseInsensitiveKeywords: false,
    },
    js: {
        keywords: JS_KEYWORDS,
        comments: [/\/\/.*$/y],
        strings: [
            /"(?:\\.|[^"\\])*"/y,
            /'(?:\\.|[^'\\])*'/y,
            /`(?:\\.|[^`\\])*`/y,
        ],
        identifierPattern: /[A-Za-z_$][A-Za-z0-9_$]*/y,
        numberPattern: /\d+(?:\.\d+)?/y,
        caseInsensitiveKeywords: false,
    },
    typescript: {
        keywords: JS_KEYWORDS,
        comments: [/\/\/.*$/y],
        strings: [
            /"(?:\\.|[^"\\])*"/y,
            /'(?:\\.|[^'\\])*'/y,
            /`(?:\\.|[^`\\])*`/y,
        ],
        identifierPattern: /[A-Za-z_$][A-Za-z0-9_$]*/y,
        numberPattern: /\d+(?:\.\d+)?/y,
        caseInsensitiveKeywords: false,
    },
    ts: {
        keywords: JS_KEYWORDS,
        comments: [/\/\/.*$/y],
        strings: [
            /"(?:\\.|[^"\\])*"/y,
            /'(?:\\.|[^'\\])*'/y,
            /`(?:\\.|[^`\\])*`/y,
        ],
        identifierPattern: /[A-Za-z_$][A-Za-z0-9_$]*/y,
        numberPattern: /\d+(?:\.\d+)?/y,
        caseInsensitiveKeywords: false,
    },
    plain: {
        keywords: new Set(),
        comments: [],
        strings: [],
        identifierPattern: /[A-Za-z_][A-Za-z0-9_]*/y,
        numberPattern: /\d+(?:\.\d+)?/y,
        caseInsensitiveKeywords: false,
    },
};
function normalizeHighlightLanguage(value) {
    if (!value)
        return 'plain';
    const lowered = value.trim().toLowerCase();
    if (lowered === '')
        return 'plain';
    if (lowered in RULES_BY_LANGUAGE) {
        return lowered;
    }
    return 'plain';
}
function highlightLine(line, language) {
    if (line.length === 0) {
        return [];
    }
    const rules = RULES_BY_LANGUAGE[language];
    const tokens = [];
    let cursor = 0;
    let pendingPlain = '';
    const flushPlain = () => {
        if (pendingPlain.length > 0) {
            tokens.push({ kind: 'plain', text: pendingPlain });
            pendingPlain = '';
        }
    };
    while (cursor < line.length) {
        const matched = matchAtCursor(line, cursor, rules);
        if (matched) {
            flushPlain();
            tokens.push(matched.token);
            cursor += matched.length;
            continue;
        }
        pendingPlain += line[cursor];
        cursor += 1;
    }
    flushPlain();
    return tokens;
}
function matchAtCursor(source, cursor, rules) {
    for (const pattern of rules.comments) {
        pattern.lastIndex = cursor;
        const match = pattern.exec(source);
        if (match && match.index === cursor) {
            return { token: { kind: 'comment', text: match[0] }, length: match[0].length };
        }
    }
    for (const pattern of rules.strings) {
        pattern.lastIndex = cursor;
        const match = pattern.exec(source);
        if (match && match.index === cursor) {
            return { token: { kind: 'string', text: match[0] }, length: match[0].length };
        }
    }
    rules.numberPattern.lastIndex = cursor;
    const numberMatch = rules.numberPattern.exec(source);
    if (numberMatch && numberMatch.index === cursor) {
        return { token: { kind: 'number', text: numberMatch[0] }, length: numberMatch[0].length };
    }
    rules.identifierPattern.lastIndex = cursor;
    const identifierMatch = rules.identifierPattern.exec(source);
    if (identifierMatch && identifierMatch.index === cursor) {
        const word = identifierMatch[0];
        const lookup = rules.caseInsensitiveKeywords ? word.toLowerCase() : word;
        if (rules.keywords.has(lookup)) {
            return { token: { kind: 'keyword', text: word }, length: word.length };
        }
        return null;
    }
    return null;
}
function tokenClassName(kind) {
    switch (kind) {
        case 'keyword':
            return 'text-sky-300';
        case 'comment':
            return 'text-slate-500 italic';
        case 'string':
            return 'text-amber-200';
        case 'number':
            return 'text-emerald-300';
        default:
            return '';
    }
}
