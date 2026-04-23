#!/usr/bin/env node
/**
 * One-shot: rewrite public/locales/<lng>/<ns>.json so the leading "<ns>."
 * is stripped from every key. Idempotent.
 */

import { readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = resolve(fileURLToPath(new URL('.', import.meta.url)));
const ROOT = resolve(__dirname, '..');
const OUT_DIR = resolve(ROOT, 'public/locales');

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
  'run',
  'cards',
  'chat',
];
const LOCALES = ['ko', 'en', 'ja'];

function stripPrefix(tree, ns) {
  // Flat-key form: rewrite keys that start with `<ns>.` to drop the prefix
  // so callers can use t('close', { ns: 'common' }) etc.
  const out = {};
  for (const [k, v] of Object.entries(tree)) {
    if (k === ns) {
      out[k] = v;
    } else if (k.startsWith(`${ns}.`)) {
      out[k.slice(ns.length + 1)] = v;
    } else {
      out[k] = v;
    }
  }
  return out;
}

for (const lng of LOCALES) {
  for (const ns of NAMESPACES) {
    const file = join(OUT_DIR, lng, `${ns}.json`);
    const data = JSON.parse(readFileSync(file, 'utf8'));
    const stripped = stripPrefix(data, ns);
    writeFileSync(file, `${JSON.stringify(stripped, null, 2)}\n`, 'utf8');
  }
}
console.log('namespace prefixes stripped');
