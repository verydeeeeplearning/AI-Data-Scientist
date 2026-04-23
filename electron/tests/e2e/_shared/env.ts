import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { BACKEND_BIN } from './paths';

export interface IsolatedRoot {
  readonly root: string;
  readonly workspace: string;
  readonly userData: string;
  readonly artifacts: string;
}

export function createIsolatedRoot(label: string): IsolatedRoot {
  const id = `${label}-${Date.now()}-${crypto.randomBytes(4).toString('hex')}`;
  const root = path.join(os.tmpdir(), `ds-agent-e2e-${id}`);
  const workspace = path.join(root, 'workspace');
  const userData = path.join(root, 'userData');
  const artifacts = path.join(root, 'artifacts');
  for (const dir of [workspace, userData, artifacts]) {
    fs.mkdirSync(dir, { recursive: true });
  }
  return { root, workspace, userData, artifacts };
}

export function buildE2eEnv(isolated: IsolatedRoot): Record<string, string> {
  const base: Record<string, string> = {};
  for (const [k, v] of Object.entries(process.env)) {
    if (v !== undefined) base[k] = v;
  }
  return {
    ...base,
    DS_AGENT_BACKEND_COMMAND: BACKEND_BIN,
    DS_AGENT_E2E_USE_BUILT_RENDERER: '1',
    DS_AGENT_E2E_USER_DATA_DIR: isolated.userData,
    DS_AGENT_E2E_DISABLE_AUTO_UPDATER: '1',
    DS_AGENT_E2E_DISABLE_PROTOCOL_REGISTRATION: '1',
    DS_AGENT_SENTRY_DSN: '',
    DS_AGENT_ERROR_REPORTING_ENABLED: '0',
    DS_AGENT_TELEMETRY_ENABLED: '0',
  };
}
