#!/usr/bin/env node
/**
 * One-shot script: extract translations from legacy i18nStore.ts and split
 * into per-namespace JSON files under public/locales/<lng>/<ns>.json.
 *
 * After D2 lands, this script is no longer required (i18next-parser handles
 * later additions). Kept for reference and re-runs.
 */

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');
const STORE_PATH =
  process.env.I18N_STORE_PATH ?? resolve(ROOT, 'src/renderer/stores/i18nStore.ts');
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

const NAMESPACE_PREFIX_TO_NS = new Map([
  ['mission', 'mission'],
  ['workspace', 'workspace'],
  ['execution', 'execution'],
  ['llm', 'llm'],
  ['sidebar', 'sidebar'],
  ['onboarding', 'onboarding'],
  ['settings', 'settings'],
  ['approval', 'approval'],
  ['trust', 'trust'],
  ['run', 'run'],
  ['cards', 'cards'],
  ['chat', 'chat'],
  ['mode', 'common'],
  ['workflow', 'common'],
  ['quality', 'common'],
  ['experiments', 'common'],
  ['alert', 'common'],
  ['budget', 'common'],
  ['update', 'common'],
  ['status', 'common'],
  ['error', 'common'],
  ['splash', 'common'],
  ['common', 'common'],
]);

function namespaceForKey(fullKey) {
  const top = fullKey.split('.', 1)[0];
  return NAMESPACE_PREFIX_TO_NS.get(top) ?? 'common';
}

function setFlat(obj, path, value) {
  obj[path] = value;
}

function parseDictBlock(source, dictName) {
  const startMarker = `const ${dictName}: TranslationDict = {`;
  const startIdx = source.indexOf(startMarker);
  if (startIdx < 0) {
    throw new Error(`Could not find ${dictName} block`);
  }
  let cursor = startIdx + startMarker.length;
  let depth = 1;
  while (cursor < source.length && depth > 0) {
    const ch = source[cursor];
    if (ch === '{') depth += 1;
    else if (ch === '}') depth -= 1;
    if (depth === 0) break;
    cursor += 1;
  }
  const block = source.slice(startIdx + startMarker.length, cursor);

  const entries = {};
  const re = /'([^']+)'\s*:\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*,?/g;
  let match;
  while ((match = re.exec(block)) !== null) {
    const key = match[1];
    let raw = match[2] !== undefined ? match[2] : match[3];
    raw = raw
      .replace(/\\'/g, "'")
      .replace(/\\"/g, '"')
      .replace(/\\\\/g, '\\')
      .replace(/\\n/g, '\n')
      .replace(/\\t/g, '\t');
    entries[key] = raw;
  }
  return entries;
}

function stripNamespacePrefix(fullKey, ns) {
  // For every namespace, strip the leading "<ns>." so callers can use
  // t('header.title', { ns: 'mission' }) and t('close', { ns: 'common' }).
  if (fullKey === ns) return fullKey;
  if (fullKey.startsWith(`${ns}.`)) return fullKey.slice(ns.length + 1);
  return fullKey;
}

function buildNamespaceTrees(flatDict) {
  const trees = {};
  for (const ns of NAMESPACES) trees[ns] = {};
  for (const [fullKey, value] of Object.entries(flatDict)) {
    const ns = namespaceForKey(fullKey);
    const localKey = stripNamespacePrefix(fullKey, ns);
    setFlat(trees[ns], localKey, value);
  }
  return trees;
}

function ensureDir(dir) {
  mkdirSync(dir, { recursive: true });
}

function writeNamespaceFiles(lng, trees) {
  const lngDir = resolve(OUT_DIR, lng);
  ensureDir(lngDir);
  for (const ns of NAMESPACES) {
    const filePath = resolve(lngDir, `${ns}.json`);
    const data = trees[ns] ?? {};
    writeFileSync(filePath, `${JSON.stringify(data, null, 2)}\n`, 'utf8');
  }
}

function fillMissingFromEn(dict, en) {
  const out = { ...dict };
  for (const [k, v] of Object.entries(en)) {
    if (!(k in out)) {
      out[k] = v;
    }
  }
  return out;
}

function main() {
  const source = readFileSync(STORE_PATH, 'utf8');
  const en = parseDictBlock(source, 'EN_TRANSLATIONS');
  const koRaw = parseDictBlock(source, 'KO_TRANSLATIONS');
  const jaRaw = parseDictBlock(source, 'JA_TRANSLATIONS');

  const ko = fillMissingFromEn(koRaw, en);
  const ja = fillMissingFromEn(jaRaw, en);

  for (const [lng, dict] of Object.entries({ en, ko, ja })) {
    const trees = buildNamespaceTrees(dict);
    writeNamespaceFiles(lng, trees);
    const total = Object.keys(dict).length;
    const perNs = Object.fromEntries(
      Object.entries(trees).map(([ns, tree]) => [ns, countLeaves(tree)]),
    );
    console.log(`[${lng}] total=${total}`, perNs);
  }
}

function countLeaves(tree) {
  return Object.keys(tree).length;
}

main();
