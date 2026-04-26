/**
 * Startup diagnostics and support-bundle assembly for Electron.
 */

import fs from 'fs/promises';
import { readFileSync } from 'fs';
import os from 'os';
import path from 'path';
import { app } from 'electron';

const MAX_RECENT_LOGS = 200;
const MAX_CONFIG_PREVIEW_CHARS = 20_000;
const MAX_FILE_PREVIEW_CHARS = 12_000;
const MAX_RUNTIME_EVENTS = 50;
const MAX_DIR_ENTRIES = 30;

type LogLevel = 'info' | 'warn' | 'error';

export interface DiagnosticLogEntry {
  timestamp: string;
  level: LogLevel;
  source: string;
  message: string;
  context?: Record<string, unknown>;
}

const recentDiagnosticLogs: DiagnosticLogEntry[] = [];

export function recordDiagnosticLog(
  level: LogLevel,
  source: string,
  message: string,
  context?: Record<string, unknown>
): void {
  recentDiagnosticLogs.push({
    timestamp: new Date().toISOString(),
    level,
    source,
    message: sanitizeText(message),
    context: context ? sanitizeObject(context) as Record<string, unknown> : undefined,
  });
  if (recentDiagnosticLogs.length > MAX_RECENT_LOGS) {
    recentDiagnosticLogs.splice(0, recentDiagnosticLogs.length - MAX_RECENT_LOGS);
  }
}

export function getRecentDiagnosticLogs(): DiagnosticLogEntry[] {
  return recentDiagnosticLogs.slice();
}

export async function buildSupportBundle(startupPayload: Record<string, unknown> | null): Promise<Record<string, unknown>> {
  const sanitizedStartup = sanitizeObject(startupPayload ?? {});
  const configSnapshot = await collectConfigSnapshot();
  const runtimeSnapshot = await collectRuntimeSnapshot(configSnapshot.workspaceDir);
  const logDirSnapshot = await collectLogDirectorySnapshot();

  return {
    bundleVersion: 1,
    bundleType: 'startup-support-bundle',
    generatedAt: new Date().toISOString(),
    startup: sanitizedStartup,
    system: sanitizeObject({
      appVersion: app.getVersion(),
      appName: app.getName(),
      platform: process.platform,
      release: os.release(),
      arch: process.arch,
      hostname: os.hostname(),
      electron: process.versions.electron,
      chrome: process.versions.chrome,
      node: process.versions.node,
    }),
    paths: sanitizeObject({
      appPath: app.getAppPath(),
      userData: app.getPath('userData'),
      logs: app.getPath('logs'),
      temp: app.getPath('temp'),
      documents: app.getPath('documents'),
      home: os.homedir(),
      configPath: configSnapshot.path,
      authProfilesPath: path.join(os.homedir(), '.ds-agent', 'auth_profiles.json'),
      workspaceDir: configSnapshot.workspaceDir,
      runtimeRoot: runtimeSnapshot.runtimeRoot,
      runtimeEventsPath: runtimeSnapshot.runtimeEventsPath,
    }),
    config: {
      exists: configSnapshot.exists,
      workspaceDir: configSnapshot.workspaceDir,
      preview: configSnapshot.preview,
    },
    runtime: runtimeSnapshot.snapshot,
    logs: {
      recentMainProcess: sanitizeObject(getRecentDiagnosticLogs()),
      logDirectory: logDirSnapshot,
    },
  };
}

async function collectConfigSnapshot(): Promise<{
  exists: boolean;
  path: string;
  workspaceDir: string;
  preview: string | null;
}> {
  const configPath = resolveConfigPath();
  const fallbackWorkspace = path.join(os.homedir(), '.ds-agent', 'workspace');

  try {
    const raw = await fs.readFile(configPath, 'utf-8');
    const workspaceDir = extractWorkspaceDir(raw) ?? fallbackWorkspace;
    return {
      exists: true,
      path: configPath,
      workspaceDir,
      preview: sanitizeText(raw).slice(0, MAX_CONFIG_PREVIEW_CHARS),
    };
  } catch {
    return {
      exists: false,
      path: configPath,
      workspaceDir: fallbackWorkspace,
      preview: null,
    };
  }
}

function resolveConfigPath(): string {
  const override = process.env.DS_AGENT_CONFIG_PATH?.trim();
  if (override) {
    return override;
  }
  return path.join(os.homedir(), '.ds-agent', 'config.yaml');
}

/**
 * Resolve the workspace directory the backend is using.
 *
 * Reads the same config file the Python backend uses so the Electron main
 * process can derive trusted paths (e.g. the export staging root) without
 * coupling to the renderer or the live backend connection.  Falls back to the
 * same default the Python schema uses: `~/.ds-agent/workspace`.
 */
export function resolveWorkspaceDir(): string {
  const fallback = path.join(os.homedir(), '.ds-agent', 'workspace');
  try {
    const raw = readFileSync(resolveConfigPath(), 'utf-8');
    return extractWorkspaceDir(raw) ?? fallback;
  } catch {
    return fallback;
  }
}

function extractWorkspaceDir(raw: string): string | null {
  let inAgentSection = false;
  for (const line of raw.split(/\r?\n/)) {
    if (/^[A-Za-z0-9_]+\s*:\s*$/.test(line.trim()) && !line.startsWith(' ')) {
      inAgentSection = line.trim() === 'agent:';
      continue;
    }
    if (!inAgentSection) {
      continue;
    }
    const match = line.match(/^\s+workspace_dir:\s*(.+)\s*$/);
    if (!match) {
      continue;
    }
    const value = match[1].trim().replace(/^['"]|['"]$/g, '');
    if (!value) {
      return null;
    }
    return resolveHome(value);
  }
  return null;
}

async function collectRuntimeSnapshot(workspaceDir: string): Promise<{
  runtimeRoot: string;
  runtimeEventsPath: string;
  snapshot: Record<string, unknown>;
}> {
  const runtimeRoot = path.join(workspaceDir, '.ds-agent', 'runtime');
  const runtimeEventsPath = path.join(runtimeRoot, 'runtime-events.jsonl');
  const runtimeEntries = await listDirectorySummary(runtimeRoot, MAX_DIR_ENTRIES);
  const recentRuntimeEvents = await readJsonLinesTail(runtimeEventsPath, MAX_RUNTIME_EVENTS);

  return {
    runtimeRoot,
    runtimeEventsPath,
    snapshot: sanitizeObject({
      runtimeRootExists: await pathExists(runtimeRoot),
      runtimeEntries,
      runtimeEventsExists: await pathExists(runtimeEventsPath),
      recentRuntimeEvents,
    }) as Record<string, unknown>,
  };
}

async function collectLogDirectorySnapshot(): Promise<Record<string, unknown>> {
  const logDir = app.getPath('logs');
  return sanitizeObject({
    exists: await pathExists(logDir),
    entries: await listDirectorySummary(logDir, MAX_DIR_ENTRIES),
  }) as Record<string, unknown>;
}

async function listDirectorySummary(dirPath: string, limit: number): Promise<Array<Record<string, unknown>>> {
  try {
    const entries = await fs.readdir(dirPath, { withFileTypes: true });
    const sliced = entries
      .slice(0, limit)
      .map((entry) => ({
        name: entry.name,
        kind: entry.isDirectory() ? 'dir' : entry.isFile() ? 'file' : 'other',
      }));
    return sliced;
  } catch {
    return [];
  }
}

async function readJsonLinesTail(filePath: string, limit: number): Promise<Array<Record<string, unknown> | string>> {
  const text = await readFileIfExists(filePath);
  if (!text) {
    return [];
  }

  const lines = text.split(/\r?\n/).filter(Boolean).slice(-limit);
  return lines.map((line) => {
    try {
      const parsed = JSON.parse(line);
      return sanitizeObject(parsed) as Record<string, unknown>;
    } catch {
      return sanitizeText(line);
    }
  });
}

async function readFileIfExists(filePath: string): Promise<string | null> {
  try {
    const content = await fs.readFile(filePath, 'utf-8');
    return content.slice(-MAX_FILE_PREVIEW_CHARS);
  } catch {
    return null;
  }
}

async function pathExists(targetPath: string): Promise<boolean> {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

function resolveHome(value: string): string {
  if (value.startsWith('~/')) {
    return path.join(os.homedir(), value.slice(2));
  }
  if (value === '~') {
    return os.homedir();
  }
  return value;
}

function sanitizeObject(value: unknown): unknown {
  if (typeof value === 'string') {
    return sanitizeText(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeObject(item));
  }
  if (value && typeof value === 'object') {
    const result: Record<string, unknown> = {};
    for (const [key, entry] of Object.entries(value as Record<string, unknown>)) {
      const lower = key.toLowerCase();
      if (
        lower.includes('token')
        || lower.includes('secret')
        || lower.includes('api_key')
        || lower.includes('apikey')
        || lower.includes('password')
      ) {
        result[key] = '***REDACTED***';
        continue;
      }
      result[key] = sanitizeObject(entry);
    }
    return result;
  }
  return value;
}

function sanitizeText(value: string): string {
  const secretPatterns = [
    /READY:(\d+):[^\s]+/g,
    /sk-ant-[A-Za-z0-9\-_]+/g,
    /sk-[A-Za-z0-9\-_]{20,}/g,
    /ya29\.[A-Za-z0-9\-_]+/g,
    /1\/\/[A-Za-z0-9\-_]+/g,
    /\b\d{8,}:[A-Za-z0-9\-_]{20,}\b/g,
  ];

  let sanitized = value;
  for (const pattern of secretPatterns) {
    sanitized = sanitized.replace(pattern, (match) => {
      if (match.startsWith('READY:')) {
        const port = match.split(':')[1] ?? 'unknown';
        return `READY:${port}:***REDACTED***`;
      }
      return '***REDACTED***';
    });
  }
  return sanitized;
}
