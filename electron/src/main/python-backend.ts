/**
 * Python backend process management with startup diagnostics.
 *
 * In dev mode: spawns `python -m ds_agent.api.app --port <port>`
 * In packaged mode: spawns the PyInstaller binary from resources/
 *
 * Waits for the `READY:<port>:<token>` signal on stdout and verifies `/health`
 * before reporting success. Startup failures are classified so the renderer can
 * show an actionable diagnostic panel instead of hanging on a blank screen.
 */

import { ChildProcess, spawn } from 'child_process';
import fs from 'fs';
import http from 'http';
import net from 'net';
import os from 'os';
import path from 'path';
import { app } from 'electron';
import { recordDiagnosticLog } from './diagnostics-collector';
import { buildDesktopSecretEnv } from './secret-vault';

let pythonProcess: ChildProcess | null = null;
let intentionalStop = false;
let currentBackendConnection: { port: number; token: string } | null = null;

const MAX_RESTARTS = 3;
const STARTUP_TIMEOUT_MS = 30_000;
const DEFAULT_PORT = 18790;

export enum StartupFailureReason {
  BINARY_NOT_FOUND = 'binary_not_found',
  BINARY_PERMISSION_DENIED = 'binary_permission_denied',
  PORT_IN_USE = 'port_in_use',
  PYTHON_ERROR = 'python_error',
  TIMEOUT = 'startup_timeout',
  ANTIVIRUS_BLOCKED = 'antivirus_blocked',
  CRASH_LOOP = 'crash_loop',
  HEALTH_CHECK_FAILED = 'health_check_failed',
}

export interface StartupDiagnostics {
  timestamp: string;
  appVersion: string;
  platform: string;
  arch: string;
  packaged: boolean;
  appPath: string;
  logsPath: string;
  cwd?: string;
  command: string;
  args: string[];
  binaryPath?: string;
  binaryExists: boolean;
  requestedPort: number;
  resolvedPort: number;
  attempts: number;
  exitCode?: number | null;
  stderrSummary?: string;
  detail?: string;
}

interface BackendStartSuccess {
  ok: true;
  port: number;
  token: string;
  diagnostics: StartupDiagnostics;
}

interface BackendStartFailure {
  ok: false;
  reason: StartupFailureReason;
  diagnostics: StartupDiagnostics;
}

export type BackendStartResult = BackendStartSuccess | BackendStartFailure;

interface BackendCommand {
  command: string;
  args: string[];
  cwd?: string;
  binaryPath?: string;
  packaged: boolean;
}

interface SpawnAttemptSuccess {
  ok: true;
  port: number;
  token: string;
  stderrSummary: string;
}

interface SpawnAttemptFailure {
  ok: false;
  reason: StartupFailureReason;
  stderrSummary: string;
  detail?: string;
  exitCode?: number | null;
  retryable: boolean;
}

type SpawnAttemptResult = SpawnAttemptSuccess | SpawnAttemptFailure;

interface BackendLaunchOptions {
  port?: number;
  wsToken?: string;
}

export async function startPythonBackend(
  options: BackendLaunchOptions = {}
): Promise<BackendStartResult> {
  const port = options.port ?? DEFAULT_PORT;
  intentionalStop = false;
  const commandSpec = resolveBackendCommand();
  const desktopSecretEnv = await buildDesktopSecretEnv();
  const preflight = await preflightCheck(commandSpec, port);
  if (!preflight.ok) {
    currentBackendConnection = null;
    return {
      ok: false,
      reason: preflight.reason,
      diagnostics: buildDiagnostics({
        commandSpec,
        requestedPort: port,
        resolvedPort: port,
        attempts: 0,
        detail: preflight.detail,
      }),
    };
  }

  let resolvedPort = preflight.resolvedPort;
  let lastFailure: SpawnAttemptFailure | null = null;

  for (let attempt = 1; attempt <= MAX_RESTARTS; attempt += 1) {
    const result = await spawnBackend(commandSpec, resolvedPort, {
      desktopSecretEnv,
      wsToken: options.wsToken,
    });
    if (result.ok) {
      const healthOk = await verifyBackendHealth(result.port);
      if (!healthOk) {
        stopPythonBackend();
        currentBackendConnection = null;
        return {
          ok: false,
          reason: StartupFailureReason.HEALTH_CHECK_FAILED,
          diagnostics: buildDiagnostics({
            commandSpec,
            requestedPort: port,
            resolvedPort: result.port,
            attempts: attempt,
            stderrSummary: result.stderrSummary,
            detail: 'Backend emitted READY but /health did not respond successfully.',
          }),
        };
      }

      currentBackendConnection = {
        port: result.port,
        token: result.token,
      };
      return {
        ok: true,
        port: result.port,
        token: result.token,
        diagnostics: buildDiagnostics({
          commandSpec,
          requestedPort: port,
          resolvedPort: result.port,
          attempts: attempt,
          stderrSummary: result.stderrSummary,
        }),
      };
    }

    lastFailure = result;
    if (result.reason === StartupFailureReason.PORT_IN_USE) {
      resolvedPort = await findFreePort(resolvedPort + 1);
      continue;
    }

    if (!result.retryable || attempt === MAX_RESTARTS) {
      break;
    }
  }

  const failure = lastFailure ?? {
    ok: false,
    reason: StartupFailureReason.CRASH_LOOP,
    stderrSummary: '',
    retryable: false,
  };

  currentBackendConnection = null;
  return {
    ok: false,
    reason:
      failure.retryable && failure.reason !== StartupFailureReason.PORT_IN_USE
        ? StartupFailureReason.CRASH_LOOP
        : failure.reason,
    diagnostics: buildDiagnostics({
      commandSpec,
      requestedPort: port,
      resolvedPort,
      attempts: MAX_RESTARTS,
      stderrSummary: failure.stderrSummary,
      detail: failure.detail,
      exitCode: failure.exitCode,
    }),
  };
}

function resolveBackendCommand(): BackendCommand {
  // Env override lets ops point at a custom backend binary and lets E2E tests
  // force a controlled failure without needing a real Python install.
  const envCommand = process.env.DS_AGENT_BACKEND_COMMAND;
  if (envCommand) {
    const envArgs = process.env.DS_AGENT_BACKEND_ARGS;
    return {
      command: envCommand,
      args: envArgs ? envArgs.split(' ').filter(Boolean) : [],
      binaryPath: envCommand,
      packaged: true,
    };
  }

  if (app.isPackaged) {
    const binaryPath = path.join(
      process.resourcesPath,
      'ds-agent-backend',
      process.platform === 'win32' ? 'ds-agent-api.exe' : 'ds-agent-api'
    );
    return {
      command: binaryPath,
      args: [],
      binaryPath,
      packaged: true,
    };
  }

  return {
    command: 'python',
    args: ['-m', 'ds_agent.api.app'],
    cwd: path.resolve(__dirname, '../../..'),
    packaged: false,
  };
}

async function preflightCheck(
  commandSpec: BackendCommand,
  port: number
): Promise<
  | { ok: true; resolvedPort: number }
  | { ok: false; reason: StartupFailureReason; detail: string }
> {
  if (commandSpec.packaged && commandSpec.binaryPath) {
    if (!fs.existsSync(commandSpec.binaryPath)) {
      return {
        ok: false,
        reason: StartupFailureReason.BINARY_NOT_FOUND,
        detail: `Backend binary was not found at ${commandSpec.binaryPath}.`,
      };
    }

    if (process.platform !== 'win32') {
      try {
        fs.accessSync(commandSpec.binaryPath, fs.constants.X_OK);
      } catch {
        return {
          ok: false,
          reason: StartupFailureReason.BINARY_PERMISSION_DENIED,
          detail: `Backend binary is not executable: ${commandSpec.binaryPath}.`,
        };
      }
    }
  }

  return { ok: true, resolvedPort: await findFreePort(port) };
}

async function spawnBackend(
  commandSpec: BackendCommand,
  requestedPort: number,
  options: {
    desktopSecretEnv: NodeJS.ProcessEnv;
    wsToken?: string;
  }
): Promise<SpawnAttemptResult> {
  return new Promise((resolve) => {
    const args = [...commandSpec.args, '--port', String(requestedPort)];
    const stderrChunks: string[] = [];
    let settled = false;
    const spawnEnv: NodeJS.ProcessEnv = {
      ...process.env,
      ...options.desktopSecretEnv,
    };
    if (options.wsToken) {
      spawnEnv.DS_AGENT_WS_TOKEN = options.wsToken;
    }

    console.log(`[backend] Starting: ${commandSpec.command} ${args.join(' ')}`);
    recordDiagnosticLog('info', 'backend', 'Starting backend process.', {
      command: commandSpec.command,
      args,
      cwd: commandSpec.cwd,
      packaged: commandSpec.packaged,
      envKeys: Object.keys(options.desktopSecretEnv),
      hasFixedWsToken: Boolean(options.wsToken),
    });

    const child = spawn(commandSpec.command, args, {
      stdio: ['pipe', 'pipe', 'pipe'],
      cwd: commandSpec.cwd,
      env: spawnEnv,
    });
    pythonProcess = child;

    const finish = (result: SpawnAttemptResult): void => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      if (!result.ok && pythonProcess === child) {
        pythonProcess = null;
      }
      resolve(result);
    };

    const timeout = setTimeout(() => {
      const stderrSummary = summarizeStderr(stderrChunks);
      child.kill();
      finish({
        ok: false,
        reason: StartupFailureReason.TIMEOUT,
        stderrSummary,
        detail: 'Python backend did not emit READY within 30 seconds.',
        retryable: false,
      });
    }, STARTUP_TIMEOUT_MS);

    child.stdout?.on('data', (data: Buffer) => {
      const output = data.toString();
      const sanitizedOutput = sanitizeText(output.trim());
      console.log(`[backend:stdout] ${sanitizedOutput}`);
      if (sanitizedOutput) {
        recordDiagnosticLog('info', 'backend:stdout', sanitizedOutput);
      }

      const match = output.match(/READY:(\d+):([^\s]+)/);
      if (!match) {
        return;
      }

      finish({
        ok: true,
        port: parseInt(match[1], 10),
        token: match[2],
        stderrSummary: summarizeStderr(stderrChunks),
      });
    });

    child.stderr?.on('data', (data: Buffer) => {
      const chunk = data.toString().trim();
      if (!chunk) {
        return;
      }
      stderrChunks.push(chunk);
      console.error(`[backend:stderr] ${chunk}`);
      recordDiagnosticLog('error', 'backend:stderr', chunk);
    });

    child.on('error', (err: NodeJS.ErrnoException) => {
      recordDiagnosticLog('error', 'backend', 'Backend process emitted spawn error.', {
        message: err.message,
        code: err.code,
      });
      finish({
        ok: false,
        reason: classifySpawnError(err.message, err.code),
        stderrSummary: summarizeStderr(stderrChunks),
        detail: err.message,
        retryable: false,
      });
    });

    child.on('exit', (code) => {
      console.log(`[backend] Process exited with code ${code}`);
      recordDiagnosticLog('warn', 'backend', 'Backend process exited.', {
        code,
        intentionalStop,
      });
      if (pythonProcess === child) {
        pythonProcess = null;
        currentBackendConnection = null;
      }
      if (settled || intentionalStop) {
        return;
      }

      const stderrSummary = summarizeStderr(stderrChunks);
      const reason = classifyStderr(stderrSummary, code);
      finish({
        ok: false,
        reason,
        stderrSummary,
        exitCode: code,
        detail: code === null ? 'Backend exited unexpectedly.' : `Backend exited with code ${code}.`,
        retryable: reason === StartupFailureReason.PYTHON_ERROR,
      });
    });
  });
}

function classifySpawnError(message: string, code?: string): StartupFailureReason {
  const text = `${message} ${code ?? ''}`.toLowerCase();
  if (text.includes('enoent')) {
    return StartupFailureReason.BINARY_NOT_FOUND;
  }
  if (text.includes('eacces') || text.includes('permission denied')) {
    return StartupFailureReason.BINARY_PERMISSION_DENIED;
  }
  if (text.includes('access is denied') || text.includes('operation not permitted')) {
    return StartupFailureReason.ANTIVIRUS_BLOCKED;
  }
  return StartupFailureReason.PYTHON_ERROR;
}

function classifyStderr(stderrSummary: string, exitCode?: number | null): StartupFailureReason {
  const text = stderrSummary.toLowerCase();
  if (text.includes('address already in use') || text.includes('only one usage of each socket')) {
    return StartupFailureReason.PORT_IN_USE;
  }
  if (
    text.includes('access is denied') ||
    text.includes('operation not permitted') ||
    text.includes('blocked')
  ) {
    return StartupFailureReason.ANTIVIRUS_BLOCKED;
  }
  if (text.includes('permission denied')) {
    return StartupFailureReason.BINARY_PERMISSION_DENIED;
  }
  if (text.includes('no such file') || text.includes('not found')) {
    return StartupFailureReason.BINARY_NOT_FOUND;
  }
  if (exitCode !== undefined && exitCode !== null) {
    return StartupFailureReason.PYTHON_ERROR;
  }
  return StartupFailureReason.CRASH_LOOP;
}

function summarizeStderr(stderrChunks: string[]): string {
  return stderrChunks.join('\n').slice(0, 1500);
}

async function verifyBackendHealth(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const request = http.get(
      {
        host: '127.0.0.1',
        port,
        path: '/health',
        timeout: 5_000,
      },
      (response) => {
        const ok = response.statusCode === 200;
        response.resume();
        resolve(ok);
      }
    );
    request.on('timeout', () => {
      request.destroy();
      resolve(false);
    });
    request.on('error', () => {
      resolve(false);
    });
  });
}

async function findFreePort(startPort: number, maxAttempts = 10): Promise<number> {
  for (let offset = 0; offset < maxAttempts; offset += 1) {
    const candidate = startPort + offset;
    if (await isPortFree(candidate)) {
      return candidate;
    }
  }
  return startPort;
}

function isPortFree(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', () => resolve(false));
    server.once('listening', () => {
      server.close(() => resolve(true));
    });
    server.listen(port, '127.0.0.1');
  });
}

function buildDiagnostics(input: {
  commandSpec: BackendCommand;
  requestedPort: number;
  resolvedPort: number;
  attempts: number;
  exitCode?: number | null;
  stderrSummary?: string;
  detail?: string;
}): StartupDiagnostics {
  return {
    timestamp: new Date().toISOString(),
    appVersion: app.getVersion(),
    platform: `${process.platform} ${os.release()}`,
    arch: process.arch,
    packaged: input.commandSpec.packaged,
    appPath: app.getAppPath(),
    logsPath: app.getPath('logs'),
    cwd: input.commandSpec.cwd,
    command: input.commandSpec.command,
    args: [...input.commandSpec.args, '--port', String(input.resolvedPort)],
    binaryPath: input.commandSpec.binaryPath,
    binaryExists: input.commandSpec.binaryPath ? fs.existsSync(input.commandSpec.binaryPath) : true,
    requestedPort: input.requestedPort,
    resolvedPort: input.resolvedPort,
    attempts: input.attempts,
    exitCode: input.exitCode,
    stderrSummary: input.stderrSummary,
    detail: input.detail,
  };
}

function sanitizeText(value: string): string {
  return value.replace(/READY:(\d+):[^\s]+/g, 'READY:$1:***REDACTED***');
}

export function stopPythonBackend(): void {
  intentionalStop = true;
  if (pythonProcess) {
    console.log('[backend] Stopping Python backend...');
    recordDiagnosticLog('info', 'backend', 'Stopping Python backend.');
    pythonProcess.kill();
    pythonProcess = null;
  }
  currentBackendConnection = null;
}

export function isBackendRunning(): boolean {
  return pythonProcess !== null && pythonProcess.exitCode === null;
}

export function getBackendConnection(): { port: number; token: string } | null {
  return currentBackendConnection;
}

export async function restartPythonBackend(): Promise<BackendStartResult> {
  const previous = currentBackendConnection;
  const currentProcess = pythonProcess;

  if (currentProcess) {
    intentionalStop = true;
    await new Promise<void>((resolve) => {
      const timeout = setTimeout(resolve, 3_000);
      currentProcess.once('exit', () => {
        clearTimeout(timeout);
        resolve();
      });
      currentProcess.kill();
    });
    if (pythonProcess === currentProcess) {
      pythonProcess = null;
    }
  }

  return startPythonBackend({
    port: previous?.port ?? DEFAULT_PORT,
    wsToken: previous?.token,
  });
}
