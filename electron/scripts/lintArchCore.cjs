'use strict';

const { readdirSync, readFileSync, statSync } = require('node:fs');
const { join, relative, sep, posix } = require('node:path');

const LAYER_RULES = {
  domain: {
    forbidPackages: [
      /^react($|\/)/,
      /^react-dom($|\/)/,
      /^zustand($|\/)/,
      /^axios($|\/)/,
      /^@?[a-z][\w-]*\/.*ws/i,
    ],
    forbidLayers: ['application', 'infrastructure', 'components', 'hooks', 'stores'],
  },
  application: {
    forbidPackages: [
      /^react($|\/)/,
      /^react-dom($|\/)/,
    ],
    forbidLayers: ['infrastructure', 'components', 'hooks'],
  },
  components: {
    forbidPackages: [],
    forbidLayers: ['infrastructure'],
  },
};

function inferLayer(absoluteOrRelativePath) {
  const norm = absoluteOrRelativePath.replace(/\\/g, '/');
  const m = norm.match(/(?:^|\/)src\/renderer\/([^\/]+)\//);
  if (!m) {
    return null;
  }
  return m[1];
}

function listSourceFiles(root) {
  const out = [];
  function walk(dir) {
    let entries;
    try {
      entries = readdirSync(dir);
    } catch {
      return;
    }
    for (const name of entries) {
      const full = join(dir, name);
      let st;
      try {
        st = statSync(full);
      } catch {
        continue;
      }
      if (st.isDirectory()) {
        walk(full);
      } else if (/\.(ts|tsx|js|jsx|mjs|cjs)$/i.test(name)) {
        out.push(full);
      }
    }
  }
  walk(root);
  return out;
}

const STATIC_IMPORT_RE = /^\s*import\s+(?:[^'"]+from\s+)?['"]([^'"]+)['"]/;
const DYNAMIC_IMPORT_RE = /\bimport\s*\(\s*['"]([^'"]+)['"]/;
const REQUIRE_RE = /\brequire\s*\(\s*['"]([^'"]+)['"]/;

function extractImports(content) {
  const lines = content.split(/\r?\n/);
  const out = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    let m = line.match(STATIC_IMPORT_RE);
    if (m) {
      out.push({ specifier: m[1], line: i + 1 });
      continue;
    }
    m = line.match(DYNAMIC_IMPORT_RE);
    if (m) {
      out.push({ specifier: m[1], line: i + 1 });
      continue;
    }
    m = line.match(REQUIRE_RE);
    if (m) {
      out.push({ specifier: m[1], line: i + 1 });
    }
  }
  return out;
}

function classifyImport(specifier, layer) {
  const rules = LAYER_RULES[layer];
  if (!rules) {
    return null;
  }
  // Package import (no leading . or /)
  const isRelative = specifier.startsWith('.') || specifier.startsWith('/');
  if (!isRelative) {
    for (const re of rules.forbidPackages) {
      if (re.test(specifier)) {
        return { kind: 'package', match: specifier };
      }
    }
    return null;
  }
  // Relative import: detect target layer by path segments
  const norm = specifier.replace(/\\/g, '/');
  for (const targetLayer of rules.forbidLayers) {
    const re = new RegExp(`(^|/)${targetLayer}(/|$)`);
    if (re.test(norm)) {
      return { kind: 'layer', match: targetLayer };
    }
  }
  return null;
}

function scanSourceFile(filePath, content) {
  const layer = inferLayer(filePath);
  if (!layer || !LAYER_RULES[layer]) {
    return [];
  }
  const violations = [];
  for (const imp of extractImports(content)) {
    const verdict = classifyImport(imp.specifier, layer);
    if (verdict) {
      violations.push({
        file: filePath.replace(/\\/g, '/'),
        line: imp.line,
        layer,
        importedFrom: imp.specifier,
        rule:
          verdict.kind === 'package'
            ? `forbidden-package:${verdict.match}`
            : `forbidden-layer:${verdict.match}`,
      });
    }
  }
  return violations;
}

function scanProject(rootDir) {
  const all = [];
  for (const file of listSourceFiles(rootDir)) {
    let content;
    try {
      content = readFileSync(file, 'utf-8');
    } catch {
      continue;
    }
    const rel = relative(rootDir, file).split(sep).join(posix.sep);
    const logicalPath = rel.startsWith('src/renderer/')
      ? rel
      : `src/renderer/${rel}`;
    const violations = scanSourceFile(logicalPath, content);
    all.push(...violations);
  }
  return all;
}

module.exports = {
  LAYER_RULES,
  inferLayer,
  extractImports,
  classifyImport,
  scanSourceFile,
  scanProject,
  listSourceFiles,
};
