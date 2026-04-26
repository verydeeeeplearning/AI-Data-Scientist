"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const promises_1 = __importDefault(require("node:fs/promises"));
const node_os_1 = __importDefault(require("node:os"));
const node_path_1 = __importDefault(require("node:path"));
const node_module_1 = __importDefault(require("node:module"));
async function run() {
    const userDataDir = await promises_1.default.mkdtemp(node_path_1.default.join(node_os_1.default.tmpdir(), 'ds-agent-vault-'));
    const moduleWithLoader = node_module_1.default;
    const originalLoad = moduleWithLoader._load;
    moduleWithLoader._load = ((request, ...args) => {
        if (request === 'electron') {
            return {
                app: {
                    getPath: (name) => {
                        strict_1.default.equal(name, 'userData');
                        return userDataDir;
                    },
                },
                safeStorage: {
                    isEncryptionAvailable: () => true,
                    encryptString: (value) => Buffer.from(`enc:${value}`, 'utf-8'),
                    decryptString: (value) => value.toString('utf-8').replace(/^enc:/, ''),
                },
            };
        }
        return originalLoad(request, ...args);
    });
    try {
        const vault = await Promise.resolve().then(() => __importStar(require('../../src/main/secret-vault')));
        const telegramToken = '123456:ABCDEFGHIJKLMNOPQRSTUVWX';
        await vault.setConfigSecret('channels.telegram.bot_token', telegramToken);
        await vault.setConfigSecret('oauth.gemini_client_secret', 'gemini-secret');
        const env = await vault.buildDesktopSecretEnv();
        strict_1.default.equal(env.DS_AGENT_TELEGRAM_BOT_TOKEN, telegramToken);
        strict_1.default.equal(env.DS_AGENT_GEMINI_CLIENT_SECRET, 'gemini-secret');
        strict_1.default.equal(await vault.clearConfigSecret('channels.telegram.bot_token'), true);
        strict_1.default.equal(await vault.clearConfigSecret('channels.telegram.bot_token'), false);
        const afterClear = await vault.buildDesktopSecretEnv();
        strict_1.default.equal(afterClear.DS_AGENT_TELEGRAM_BOT_TOKEN, undefined);
        strict_1.default.equal(afterClear.DS_AGENT_GEMINI_CLIENT_SECRET, 'gemini-secret');
        await strict_1.default.rejects(() => vault.setConfigSecret('channels.telegram.unknown', 'secret'), /Unsupported config secret/);
        await strict_1.default.rejects(() => vault.clearConfigSecret('channels.telegram.unknown'), /Unsupported config secret/);
    }
    finally {
        moduleWithLoader._load = originalLoad;
        await promises_1.default.rm(userDataDir, { recursive: true, force: true });
    }
    console.log('[contract] PASS secret-vault-config-secret (9 cases)');
}
void run().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
