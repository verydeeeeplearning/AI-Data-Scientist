#!/usr/bin/env node
/**
 * lint:i18n CI gate.
 *
 * Two checks (both must pass for exit 0):
 *  1. ko/en/ja JSON files share identical key sets per namespace.
 *  2. No CJK (Korean) string literals remain in renderer/components, hooks,
 *     or stores under src/renderer (i18n migration completeness).
 *
 * Implementation note: avoids running i18next-parser in CI because dynamic
 * keys (variable arguments to `t()`) are intentionally used in some flows
 * — running --fail-on-update would yield false positives. The structural
 * checks below cover the spirit of the gate.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const ROOT = resolve(__dirname, '..');
const LOCALES_DIR = resolve(ROOT, 'public/locales');
const NAMESPACES = [
  'common',
  'mission',
  'workspace',
  'execution',
  'llm',
  'sidebar',
  'onboarding',
  'settings',
  'approval',
  'trust',
  'cards',
  'chat',
];
const LOCALES = ['ko', 'en', 'ja'];

const SCAN_ROOTS = [
  resolve(ROOT, 'src/renderer/components'),
  resolve(ROOT, 'src/renderer/hooks'),
];
const SKIP_FILE_BASENAMES = new Set([
  // generated or test files exempt from CJK literal check
]);

const HANGUL_REGEX = /[\u3131-\u318E\uAC00-\uD7A3]/;

function flatten(obj, prefix, out) {
  if (obj === null || obj === undefined) return;
  if (typeof obj !== 'object' || Array.isArray(obj)) {
    out.set(prefix, obj);
    return;
  }
  for (const [k, v] of Object.entries(obj)) {
    const next = prefix ? `${prefix}.${k}` : k;
    flatten(v, next, out);
  }
}

function loadFlat(lng, ns) {
  const file = join(LOCALES_DIR, lng, `${ns}.json`);
  const raw = readFileSync(file, 'utf8');
  const data = JSON.parse(raw);
  const out = new Map();
  flatten(data, '', out);
  return out;
}

function checkNamespaceConsistency() {
  const errors = [];
  for (const ns of NAMESPACES) {
    const flatByLng = {};
    for (const lng of LOCALES) {
      flatByLng[lng] = loadFlat(lng, ns);
    }
    const en = flatByLng.en;
    for (const lng of LOCALES) {
      if (lng === 'en') continue;
      const cur = flatByLng[lng];
      const missingInLng = [];
      const extraInLng = [];
      for (const key of en.keys()) {
        if (!cur.has(key)) missingInLng.push(key);
      }
      for (const key of cur.keys()) {
        if (!en.has(key)) extraInLng.push(key);
      }
      if (missingInLng.length || extraInLng.length) {
        errors.push(
          `[${ns}] ${lng} differs from en — missing=${missingInLng.length}, extra=${extraInLng.length}\n  ` +
            [
              ...missingInLng.slice(0, 5).map((k) => `- ${k}`),
              ...extraInLng.slice(0, 5).map((k) => `+ ${k}`),
            ].join('\n  '),
        );
      }
    }
  }
  return errors;
}

function walk(dir, out) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return;
  }
  for (const entry of entries) {
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) {
      walk(full, out);
    } else if (
      st.isFile() &&
      (entry.endsWith('.tsx') || entry.endsWith('.ts')) &&
      !SKIP_FILE_BASENAMES.has(entry)
    ) {
      out.push(full);
    }
  }
}

function checkNoHangulLiterals() {
  const violations = [];
  const files = [];
  for (const root of SCAN_ROOTS) {
    walk(root, files);
  }
  const stringLiteralRe = /(['"`])((?:\\.|(?!\1)[^\\])*)\1/g;
  for (const file of files) {
    const src = readFileSync(file, 'utf8');
    const lines = src.split('\n');
    for (let i = 0; i < lines.length; i += 1) {
      const line = lines[i];
      stringLiteralRe.lastIndex = 0;
      let m;
      while ((m = stringLiteralRe.exec(line)) !== null) {
        const literal = m[2];
        if (HANGUL_REGEX.test(literal)) {
          violations.push(`${file}:${i + 1} — '${literal.slice(0, 40)}...'`);
          if (violations.length > 50) return violations;
        }
      }
    }
  }
  return violations;
}

function main() {
  const nsErrors = checkNamespaceConsistency();
  const cjkErrors = checkNoHangulLiterals();

  if (nsErrors.length === 0 && cjkErrors.length === 0) {
    console.log(
      `[lint:i18n] OK — 12 namespaces × 3 locales key sets identical, 0 Hangul literals in components/hooks`,
    );
    process.exit(0);
  }

  if (nsErrors.length) {
    console.error(`[lint:i18n] namespace key-set mismatches:`);
    for (const err of nsErrors) console.error(err);
  }
  if (cjkErrors.length) {
    console.error(`\n[lint:i18n] Hangul string literals (use i18n keys instead):`);
    for (const v of cjkErrors) console.error(`  ${v}`);
  }
  process.exit(1);
}

main();
