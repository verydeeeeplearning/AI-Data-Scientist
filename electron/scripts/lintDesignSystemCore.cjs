const fs = require('node:fs');
const path = require('node:path');

const MANAGED_SEGMENTS = [
  path.normalize('src/renderer/design-system/primitives/'),
  path.normalize('src/renderer/design-system/composites/'),
  path.normalize('src/renderer/components/providers/'),
];

const HEX_LITERAL = /#[0-9A-Fa-f]{3,8}\b/g;
const ARBITRARY_TAILWIND =
  /\b(?:bg|text|border|shadow|tracking|leading|rounded|h|w|min-h|min-w|max-h|max-w|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|ml|mr|gap)-\[[^\]]+\]/g;

function isManagedFile(file) {
  const normalized = path.normalize(file);
  if (normalized.endsWith('.stories.tsx') || normalized.endsWith('.stories.ts')) {
    return false;
  }
  return MANAGED_SEGMENTS.some((segment) => normalized.includes(segment));
}

function toLineNumber(content, index) {
  return content.slice(0, index).split(/\r?\n/).length;
}

function scanPattern(file, content, pattern, rule) {
  const violations = [];
  for (const match of content.matchAll(pattern)) {
    const value = match[0];
    const index = match.index ?? 0;
    violations.push({
      file: path.normalize(file),
      line: toLineNumber(content, index),
      rule,
      value,
    });
  }
  return violations;
}

function scanSourceFile(file, content) {
  if (!isManagedFile(file)) {
    return [];
  }
  return [
    ...scanPattern(file, content, HEX_LITERAL, 'hex-literal'),
    ...scanPattern(file, content, ARBITRARY_TAILWIND, 'tailwind-arbitrary-value'),
  ];
}

function walk(rootDir) {
  const files = [];
  for (const entry of fs.readdirSync(rootDir, { withFileTypes: true })) {
    const fullPath = path.join(rootDir, entry.name);
    if (entry.isDirectory()) {
      files.push(...walk(fullPath));
      continue;
    }
    if (fullPath.endsWith('.ts') || fullPath.endsWith('.tsx')) {
      files.push(fullPath);
    }
  }
  return files;
}

function scanProject(rootDir) {
  const violations = [];
  for (const file of walk(rootDir)) {
    const content = fs.readFileSync(file, 'utf8');
    violations.push(...scanSourceFile(file, content));
  }
  return violations;
}

module.exports = {
  scanProject,
  scanSourceFile,
};
