/**
 * Desktop secret vault owned by the Electron main process.
 *
 * Uses Electron's safeStorage to encrypt secrets at rest so renderer code never
 * handles persisted plaintext outside direct user input moments.
 */

import fs from 'fs/promises';
import path from 'path';
import { app, safeStorage } from 'electron';

type SecretVaultRecord = Record<string, string>;

interface SecretVaultFile {
  version: 1;
  secrets: SecretVaultRecord;
}

interface VaultStatus {
  available: boolean;
  persistent: boolean;
  backend: 'safeStorage' | 'unavailable';
  error?: string;
}

interface MaskedApiKeySnapshot extends VaultStatus {
  maskedKeys: Record<string, string>;
}

const VAULT_VERSION = 1;
const VAULT_FILENAME = 'secret-vault.json';

const PROVIDER_ENV_KEYS: Record<string, string> = {
  anthropic: 'ANTHROPIC_API_KEY',
  openai: 'OPENAI_API_KEY',
  gemini: 'GEMINI_API_KEY',
  groq: 'GROQ_API_KEY',
  deepseek: 'DEEPSEEK_API_KEY',
  minimax: 'MINIMAX_API_KEY',
  qwen: 'QWEN_API_KEY',
  zhipu: 'ZHIPU_API_KEY',
  moonshot: 'MOONSHOT_API_KEY',
};

const CONFIG_SECRET_ENV_KEYS: Record<string, string> = {
  'oauth.gemini_client_secret': 'DS_AGENT_GEMINI_CLIENT_SECRET',
  'channels.telegram.bot_token': 'DS_AGENT_TELEGRAM_BOT_TOKEN',
};

function getVaultPath(): string {
  return path.join(app.getPath('userData'), VAULT_FILENAME);
}

function providerSecretKey(provider: string): string {
  return `api_key:${provider}`;
}

function configSecretKey(secretPath: string): string {
  return `config_secret:${secretPath}`;
}

function ensureProviderSupported(provider: string): void {
  if (!(provider in PROVIDER_ENV_KEYS)) {
    throw new Error(`Unsupported provider secret: ${provider}`);
  }
}

function ensureConfigSecretSupported(secretPath: string): void {
  if (!(secretPath in CONFIG_SECRET_ENV_KEYS)) {
    throw new Error(`Unsupported config secret: ${secretPath}`);
  }
}

function getUnavailableStatus(): VaultStatus {
  return {
    available: false,
    persistent: false,
    backend: 'unavailable',
    error: 'Desktop secure storage is unavailable on this system.',
  };
}

export function getSecretVaultStatus(): VaultStatus {
  if (!safeStorage.isEncryptionAvailable()) {
    return getUnavailableStatus();
  }
  return {
    available: true,
    persistent: true,
    backend: 'safeStorage',
  };
}

function assertVaultAvailable(): void {
  const status = getSecretVaultStatus();
  if (!status.available) {
    throw new Error(status.error ?? 'Desktop secure storage is unavailable.');
  }
}

async function readVaultFile(): Promise<SecretVaultFile> {
  const vaultPath = getVaultPath();
  try {
    const raw = await fs.readFile(vaultPath, 'utf-8');
    const parsed = JSON.parse(raw) as Partial<SecretVaultFile>;
    if (
      parsed.version !== VAULT_VERSION
      || !parsed.secrets
      || typeof parsed.secrets !== 'object'
      || Array.isArray(parsed.secrets)
    ) {
      return { version: VAULT_VERSION, secrets: {} };
    }
    return {
      version: VAULT_VERSION,
      secrets: { ...parsed.secrets },
    };
  } catch (error) {
    const nodeError = error as NodeJS.ErrnoException;
    if (nodeError.code === 'ENOENT') {
      return { version: VAULT_VERSION, secrets: {} };
    }
    throw error;
  }
}

async function writeVaultFile(data: SecretVaultFile): Promise<void> {
  const vaultPath = getVaultPath();
  await fs.mkdir(path.dirname(vaultPath), { recursive: true });
  await fs.writeFile(
    vaultPath,
    JSON.stringify(data, null, 2),
    'utf-8'
  );
}

function encryptSecret(value: string): string {
  return safeStorage.encryptString(value).toString('base64');
}

function decryptSecret(ciphertext: string): string {
  return safeStorage.decryptString(Buffer.from(ciphertext, 'base64'));
}

function maskSecret(value: string): string {
  if (value.length <= 6) {
    return '***';
  }
  return `${value.slice(0, 4)}...${value.slice(-4)}`;
}

export async function setProviderApiKey(provider: string, value: string): Promise<void> {
  ensureProviderSupported(provider);
  assertVaultAvailable();
  const vault = await readVaultFile();
  vault.secrets[providerSecretKey(provider)] = encryptSecret(value);
  await writeVaultFile(vault);
}

export async function deleteProviderApiKey(provider: string): Promise<boolean> {
  ensureProviderSupported(provider);
  assertVaultAvailable();
  const vault = await readVaultFile();
  const key = providerSecretKey(provider);
  if (!(key in vault.secrets)) {
    return false;
  }
  delete vault.secrets[key];
  await writeVaultFile(vault);
  return true;
}

export async function getMaskedProviderApiKeys(): Promise<MaskedApiKeySnapshot> {
  const status = getSecretVaultStatus();
  if (!status.available) {
    return { ...status, maskedKeys: {} };
  }

  const vault = await readVaultFile();
  const maskedKeys: Record<string, string> = {};

  for (const provider of Object.keys(PROVIDER_ENV_KEYS)) {
    const ciphertext = vault.secrets[providerSecretKey(provider)];
    if (!ciphertext) {
      continue;
    }
    try {
      maskedKeys[provider] = maskSecret(decryptSecret(ciphertext));
    } catch {
      maskedKeys[provider] = '***';
    }
  }

  return { ...status, maskedKeys };
}

export async function setConfigSecret(secretPath: string, value: string): Promise<void> {
  ensureConfigSecretSupported(secretPath);
  assertVaultAvailable();
  const vault = await readVaultFile();
  vault.secrets[configSecretKey(secretPath)] = encryptSecret(value);
  await writeVaultFile(vault);
}

export async function clearConfigSecret(secretPath: string): Promise<boolean> {
  ensureConfigSecretSupported(secretPath);
  assertVaultAvailable();
  const vault = await readVaultFile();
  const key = configSecretKey(secretPath);
  if (!(key in vault.secrets)) {
    return false;
  }
  delete vault.secrets[key];
  await writeVaultFile(vault);
  return true;
}

export async function buildDesktopSecretEnv(): Promise<NodeJS.ProcessEnv> {
  const status = getSecretVaultStatus();
  if (!status.available) {
    return {};
  }

  const vault = await readVaultFile();
  const env: NodeJS.ProcessEnv = {};

  for (const [provider, envKey] of Object.entries(PROVIDER_ENV_KEYS)) {
    const ciphertext = vault.secrets[providerSecretKey(provider)];
    if (!ciphertext) {
      continue;
    }
    try {
      env[envKey] = decryptSecret(ciphertext);
    } catch {
      // Ignore corrupted values and let the backend surface auth issues normally.
    }
  }

  for (const [secretPath, envKey] of Object.entries(CONFIG_SECRET_ENV_KEYS)) {
    const ciphertext = vault.secrets[configSecretKey(secretPath)];
    if (!ciphertext) {
      continue;
    }
    try {
      env[envKey] = decryptSecret(ciphertext);
    } catch {
      // Ignore corrupted values and let the backend surface config/auth issues.
    }
  }

  return env;
}
