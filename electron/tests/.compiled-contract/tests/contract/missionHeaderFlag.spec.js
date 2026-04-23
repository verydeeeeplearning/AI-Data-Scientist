"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const configStore_1 = require("../../src/renderer/stores/configStore");
class MemoryStorage {
    constructor() {
        this.store = new Map();
    }
    get length() {
        return this.store.size;
    }
    clear() {
        this.store.clear();
    }
    getItem(key) {
        return this.store.has(key) ? this.store.get(key) ?? null : null;
    }
    key(index) {
        return Array.from(this.store.keys())[index] ?? null;
    }
    removeItem(key) {
        this.store.delete(key);
    }
    setItem(key, value) {
        this.store.set(key, value);
    }
}
function run() {
    strict_1.default.equal((0, configStore_1.parseMissionHeaderEnabled)(null), true);
    strict_1.default.equal((0, configStore_1.parseMissionHeaderEnabled)('true'), true);
    strict_1.default.equal((0, configStore_1.parseMissionHeaderEnabled)('false'), false);
    strict_1.default.equal((0, configStore_1.parseMissionHeaderEnabled)('0'), false);
    strict_1.default.equal((0, configStore_1.parseMissionHeaderEnabled)('off'), false);
    strict_1.default.equal((0, configStore_1.parseMissionHeaderEnabled)('unexpected'), true);
    const storageHost = globalThis;
    const previousLocalStorage = storageHost.localStorage;
    const storage = new MemoryStorage();
    storageHost.localStorage = storage;
    try {
        strict_1.default.equal((0, configStore_1.loadMissionHeaderEnabled)(), true);
        storage.setItem(configStore_1.MISSION_HEADER_FLAG_STORAGE_KEY, 'false');
        strict_1.default.equal((0, configStore_1.loadMissionHeaderEnabled)(), false);
        storage.setItem(configStore_1.MISSION_HEADER_FLAG_STORAGE_KEY, 'true');
        strict_1.default.equal((0, configStore_1.loadMissionHeaderEnabled)(), true);
    }
    finally {
        if (previousLocalStorage === undefined) {
            delete storageHost.localStorage;
        }
        else {
            storageHost.localStorage = previousLocalStorage;
        }
    }
    console.log('[contract] PASS mission-header-flag (9 cases)');
}
run();
