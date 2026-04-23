import fs from 'node:fs';
import { _electron as electron, type ElectronApplication, type Page } from 'playwright';
import { buildE2eEnv, createIsolatedRoot, type IsolatedRoot } from './env';
import { BACKEND_BIN, ELECTRON_MAIN, REPO_ROOT } from './paths';

export interface LaunchResult {
  readonly app: ElectronApplication;
  readonly page: Page;
  readonly isolated: IsolatedRoot;
}

export interface LaunchOptions {
  readonly extraEnv?: Record<string, string>;
  readonly skipBinaryCheck?: boolean;
}

export async function launchApp(label: string, options: LaunchOptions = {}): Promise<LaunchResult> {
  const { extraEnv = {}, skipBinaryCheck = false } = options;
  if (!skipBinaryCheck && !fs.existsSync(BACKEND_BIN)) {
    throw new Error(
      `Backend binary not found: ${BACKEND_BIN}\nRun: python scripts/build_backend.py`
    );
  }
  const isolated = createIsolatedRoot(label);
  const env = { ...buildE2eEnv(isolated), ...extraEnv };
  const app = await electron.launch({
    args: [ELECTRON_MAIN],
    cwd: REPO_ROOT,
    env,
    timeout: 60_000,
  });
  const page = await app.firstWindow({ timeout: 60_000 });
  await page.waitForLoadState('domcontentloaded');
  return { app, page, isolated };
}
