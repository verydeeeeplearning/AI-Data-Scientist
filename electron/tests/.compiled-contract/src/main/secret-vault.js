"use strict";
/**
 * Desktop secret vault owned by the Electron main process.
 *
 * Uses Electron's safeStorage to encrypt secrets at rest so renderer code never
 * handles persisted plaintext outside direct user input moments.
 */
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getSecretVaultStatus = getSecretVaultStatus;
exports.setProviderApiKey = setProviderApiKey;
exports.deleteProviderApiKey = deleteProviderApiKey;
exports.getMaskedProviderApiKeys = getMaskedProviderApiKeys;
exports.setConfigSecret = setConfigSecret;
exports.clearConfigSecret = clearConfigSecret;
exports.buildDesktopSecretEnv = buildDesktopSecretEnv;
const promises_1 = __importDefault(require("fs/promises"));
const path_1 = __importDefault(require("path"));
const electron_1 = require("electron");
const VAULT_VERSION = 1;
const VAULT_FILENAME = 'secret-vault.json';
const PROVIDER_ENV_KEYS = {
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
const CONFIG_SECRET_ENV_KEYS = {
    'oauth.gemini_client_secret': 'DS_AGENT_GEMINI_CLIENT_SECRET',
    'channels.telegram.bot_token': 'DS_AGENT_TELEGRAM_BOT_TOKEN',
};
function getVaultPath() {
    return path_1.default.join(electron_1.app.getPath('userData'), VAULT_FILENAME);
}
function providerSecretKey(provider) {
    return `api_key:${provider}`;
}
function configSecretKey(secretPath) {
    return `config_secret:${secretPath}`;
}
function ensureProviderSupported(provider) {
    if (!(provider in PROVIDER_ENV_KEYS)) {
        throw new Error(`Unsupported provider secret: ${provider}`);
    }
}
function ensureConfigSecretSupported(secretPath) {
    if (!(secretPath in CONFIG_SECRET_ENV_KEYS)) {
        throw new Error(`Unsupported config secret: ${secretPath}`);
    }
}
function getUnavailableStatus() {
    return {
        available: false,
        persistent: false,
        backend: 'unavailable',
        error: 'Desktop secure storage is unavailable on this system.',
    };
}
function getSecretVaultStatus() {
    if (!electron_1.safeStorage.isEncryptionAvailable()) {
        return getUnavailableStatus();
    }
    return {
        available: true,
        persistent: true,
        backend: 'safeStorage',
    };
}
function assertVaultAvailable() {
    const status = getSecretVaultStatus();
    if (!status.available) {
        throw new Error(status.error ?? 'Desktop secure storage is unavailable.');
    }
}
async function readVaultFile() {
    const vaultPath = getVaultPath();
    try {
        const raw = await promises_1.default.readFile(vaultPath, 'utf-8');
        const parsed = JSON.parse(raw);
        if (parsed.version !== VAULT_VERSION
            || !parsed.secrets
            || typeof parsed.secrets !== 'object'
            || Array.isArray(parsed.secrets)) {
            return { version: VAULT_VERSION, secrets: {} };
        }
        return {
            version: VAULT_VERSION,
            secrets: { ...parsed.secrets },
        };
    }
    catch (error) {
        const nodeError = error;
        if (nodeError.code === 'ENOENT') {
            return { version: VAULT_VERSION, secrets: {} };
        }
        throw error;
    }
}
async function writeVaultFile(data) {
    const vaultPath = getVaultPath();
    await promises_1.default.mkdir(path_1.default.dirname(vaultPath), { recursive: true });
    await promises_1.default.writeFile(vaultPath, JSON.stringify(data, null, 2), 'utf-8');
}
function encryptSecret(value) {
    return electron_1.safeStorage.encryptString(value).toString('base64');
}
function decryptSecret(ciphertext) {
    return electron_1.safeStorage.decryptString(Buffer.from(ciphertext, 'base64'));
}
function maskSecret(value) {
    if (value.length <= 6) {
        return '***';
    }
    return `${value.slice(0, 4)}...${value.slice(-4)}`;
}
async function setProviderApiKey(provider, value) {
    ensureProviderSupported(provider);
    assertVaultAvailable();
    const vault = await readVaultFile();
    vault.secrets[providerSecretKey(provider)] = encryptSecret(value);
    await writeVaultFile(vault);
}
async function deleteProviderApiKey(provider) {
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
async function getMaskedProviderApiKeys() {
    const status = getSecretVaultStatus();
    if (!status.available) {
        return { ...status, maskedKeys: {} };
    }
    const vault = await readVaultFile();
    const maskedKeys = {};
    for (const provider of Object.keys(PROVIDER_ENV_KEYS)) {
        const ciphertext = vault.secrets[providerSecretKey(provider)];
        if (!ciphertext) {
            continue;
        }
        try {
            maskedKeys[provider] = maskSecret(decryptSecret(ciphertext));
        }
        catch {
            maskedKeys[provider] = '***';
        }
    }
    return { ...status, maskedKeys };
}
async function setConfigSecret(secretPath, value) {
    ensureConfigSecretSupported(secretPath);
    assertVaultAvailable();
    const vault = await readVaultFile();
    vault.secrets[configSecretKey(secretPath)] = encryptSecret(value);
    await writeVaultFile(vault);
}
async function clearConfigSecret(secretPath) {
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
async function buildDesktopSecretEnv() {
    const status = getSecretVaultStatus();
    if (!status.available) {
        return {};
    }
    const vault = await readVaultFile();
    const env = {};
    for (const [provider, envKey] of Object.entries(PROVIDER_ENV_KEYS)) {
        const ciphertext = vault.secrets[providerSecretKey(provider)];
        if (!ciphertext) {
            continue;
        }
        try {
            env[envKey] = decryptSecret(ciphertext);
        }
        catch {
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
        }
        catch {
            // Ignore corrupted values and let the backend surface config/auth issues.
        }
    }
    return env;
}
