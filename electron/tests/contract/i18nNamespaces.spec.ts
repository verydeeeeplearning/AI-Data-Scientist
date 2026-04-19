import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

// Resolve repository electron/ root regardless of compiled output depth.
function findElectronRoot(start: string): string {
  let dir = start;
  for (let i = 0; i < 8; i += 1) {
    if (dir.endsWith('electron') || dir.endsWith('electron\\') || dir.endsWith('electron/')) {
      return dir;
    }
    const parent = resolve(dir, '..');
    if (parent === dir) break;
    dir = parent;
  }
  return resolve(start, '..', '..', '..', '..');
}

const ELECTRON_ROOT = findElectronRoot(__dirname);
const LOCALES_DIR = join(ELECTRON_ROOT, 'public', 'locales');

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
] as const;

const LOCALES = ['ko', 'en', 'ja'] as const;

type Tree = Record<string, unknown>;

function flatten(tree: Tree, prefix = ''): Map<string, string> {
  const out = new Map<string, string>();
  for (const [k, v] of Object.entries(tree)) {
    const next = prefix ? `${prefix}.${k}` : k;
    if (typeof v === 'string') {
      out.set(next, v);
    } else if (v && typeof v === 'object' && !Array.isArray(v)) {
      for (const [kk, vv] of flatten(v as Tree, next)) {
        out.set(kk, vv as string);
      }
    } else {
      out.set(next, String(v));
    }
  }
  return out;
}

function loadFlat(lng: string, ns: string): Map<string, string> {
  const filePath = join(LOCALES_DIR, lng, `${ns}.json`);
  const data = JSON.parse(readFileSync(filePath, 'utf8')) as Tree;
  return flatten(data);
}

function extractInterpolationVars(template: string): Set<string> {
  const result = new Set<string>();
  const re = /\{\s*(\w+)\s*\}/g;
  let m;
  while ((m = re.exec(template)) !== null) {
    result.add(m[1]);
  }
  return result;
}

interface TestCase {
  name: string;
  fn: () => void;
}

const tests: TestCase[] = [];

function test(name: string, fn: () => void): void {
  tests.push({ name, fn });
}

test('every namespace JSON file loads as a valid object', () => {
  for (const lng of LOCALES) {
    for (const ns of NAMESPACES) {
      const flat = loadFlat(lng, ns);
      assert.ok(flat instanceof Map, `${lng}/${ns}.json failed to load`);
    }
  }
});

test('ko / en / ja share identical key sets per namespace', () => {
  for (const ns of NAMESPACES) {
    const enKeys = new Set(loadFlat('en', ns).keys());
    for (const lng of LOCALES) {
      if (lng === 'en') continue;
      const cur = new Set(loadFlat(lng, ns).keys());
      const missing: string[] = [];
      const extra: string[] = [];
      for (const k of enKeys) if (!cur.has(k)) missing.push(k);
      for (const k of cur) if (!enKeys.has(k)) extra.push(k);
      assert.equal(
        missing.length,
        0,
        `[${ns}] ${lng} missing keys: ${missing.slice(0, 5).join(', ')} (${missing.length} total)`,
      );
      assert.equal(
        extra.length,
        0,
        `[${ns}] ${lng} extra keys: ${extra.slice(0, 5).join(', ')} (${extra.length} total)`,
      );
    }
  }
});

test('interpolation variables match across locales for every key', () => {
  for (const ns of NAMESPACES) {
    const en = loadFlat('en', ns);
    for (const lng of LOCALES) {
      if (lng === 'en') continue;
      const cur = loadFlat(lng, ns);
      for (const [key, enValue] of en.entries()) {
        const enVars = extractInterpolationVars(enValue);
        const lngValue = cur.get(key);
        if (lngValue === undefined) continue;
        const lngVars = extractInterpolationVars(lngValue);
        for (const v of enVars) {
          assert.ok(
            lngVars.has(v),
            `[${ns}.${key}] ${lng} missing interpolation var {${v}} present in en`,
          );
        }
      }
    }
  }
});

test('mission namespace preserves Phase C-introduced keys', () => {
  const ns = 'mission';
  const required = [
    'header.title',
    'header.budgetAlert.warningTitle',
    'header.budgetAlert.snooze.5m',
    'header.budgetAlert.pause',
    'drawer.title.goal',
    'drawer.title.budget',
    'drawer.readonly',
    'dropdown.mode.title',
    'connection.tooltip.healthy',
  ];
  for (const lng of LOCALES) {
    const flat = loadFlat(lng, ns);
    for (const key of required) {
      assert.ok(flat.has(key), `[${ns}/${lng}] missing Phase C key: ${key}`);
    }
  }
});

test('execution namespace preserves W1-F 31 stage keys', () => {
  const ns = 'execution';
  const required = [
    'title',
    'empty',
    'stage.data_loading',
    'stage.export',
    'status.pending',
    'announce.started',
    'row.expand',
    'outcome.jump',
    'raw_log.toggle',
  ];
  for (const lng of LOCALES) {
    const flat = loadFlat(lng, ns);
    for (const key of required) {
      assert.ok(flat.has(key), `[${ns}/${lng}] missing W1-F key: ${key}`);
    }
  }
});

test('llm namespace preserves W1-C capability/recommend keys', () => {
  const ns = 'llm';
  const required = [
    'recommend.badge',
    'recommend.reason.ready',
    'group.fast_start.title',
    'group.fast_start.emptyTitle',
    'badge.fast',
    'badge.strong_korean',
  ];
  for (const lng of LOCALES) {
    const flat = loadFlat(lng, ns);
    for (const key of required) {
      assert.ok(flat.has(key), `[${ns}/${lng}] missing W1-C key: ${key}`);
    }
  }
});

test('workspace namespace preserves W1-D drop overlay + upload error keys', () => {
  const ns = 'workspace';
  const required = [
    'dropOverlay.title',
    'dropOverlay.announce.entered',
    'uploadError.network.title',
    'uploadError.tooLarge.description',
    'upload.suggestedActions.queued',
  ];
  for (const lng of LOCALES) {
    const flat = loadFlat(lng, ns);
    for (const key of required) {
      assert.ok(flat.has(key), `[${ns}/${lng}] missing W1-D key: ${key}`);
    }
  }
});

test('sidebar namespace preserves W1-B collapse keys', () => {
  const ns = 'sidebar';
  const required = ['toggle.collapse', 'toggle.expand', 'toggle.shortcut'];
  for (const lng of LOCALES) {
    const flat = loadFlat(lng, ns);
    for (const key of required) {
      assert.ok(flat.has(key), `[${ns}/${lng}] missing W1-B key: ${key}`);
    }
  }
});

test('common namespace contains baseline shared vocabulary', () => {
  const ns = 'common';
  const required = ['close', 'cancel', 'save', 'continue', 'back', 'retry', 'loading'];
  for (const lng of LOCALES) {
    const flat = loadFlat(lng, ns);
    for (const key of required) {
      assert.ok(flat.has(key), `[${ns}/${lng}] missing common key: ${key}`);
    }
  }
});

test('approval / trust / cards / chat namespaces exist (placeholder ok)', () => {
  for (const lng of LOCALES) {
    for (const ns of ['approval', 'trust', 'cards', 'chat']) {
      const flat = loadFlat(lng, ns);
      assert.ok(flat instanceof Map, `${lng}/${ns}.json failed to load`);
    }
  }
});

let passed = 0;
let failed = 0;
for (const t of tests) {
  try {
    t.fn();
    console.log(`  ok  ${t.name}`);
    passed += 1;
  } catch (err) {
    console.error(`  FAIL ${t.name}`);
    console.error(`    ${(err as Error).message}`);
    failed += 1;
  }
}

console.log(
  `\ni18nNamespaces.spec — ${passed}/${passed + failed} passed${failed ? ' (' + failed + ' failed)' : ''}`,
);

if (failed > 0) {
  process.exit(1);
}
