import path from 'node:path';

export const ELECTRON_DIR = process.cwd();
export const REPO_ROOT = path.resolve(ELECTRON_DIR, '..');
export const ELECTRON_MAIN = path.resolve(ELECTRON_DIR, 'dist', 'main', 'index.js');
export const BACKEND_BIN = path.resolve(
  REPO_ROOT,
  'dist',
  'ds-agent-backend',
  process.platform === 'win32' ? 'ds-agent-api.exe' : 'ds-agent-api'
);
