"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.loadRecentCommandIds = loadRecentCommandIds;
exports.recordRecentCommandId = recordRecentCommandId;
exports.buildCommandMap = buildCommandMap;
const RECENT_COMMAND_IDS_STORAGE_KEY = 'ds-agent-command-palette-recent';
const MAX_RECENT_COMMANDS = 12;
function loadRecentIdsFromStorage() {
    try {
        const raw = window.localStorage.getItem(RECENT_COMMAND_IDS_STORAGE_KEY);
        if (!raw) {
            return [];
        }
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) {
            return [];
        }
        return parsed.filter((value) => typeof value === 'string');
    }
    catch {
        return [];
    }
}
function persistRecentIds(ids) {
    try {
        window.localStorage.setItem(RECENT_COMMAND_IDS_STORAGE_KEY, JSON.stringify(ids));
    }
    catch {
        // Ignore storage failures. The palette still works without persistence.
    }
}
function loadRecentCommandIds() {
    return loadRecentIdsFromStorage();
}
function recordRecentCommandId(commandId) {
    const current = loadRecentIdsFromStorage();
    const next = [
        commandId,
        ...current.filter((candidate) => candidate !== commandId),
    ].slice(0, MAX_RECENT_COMMANDS);
    persistRecentIds(next);
    return next;
}
function buildCommandMap(commands) {
    return new Map(commands.map((command) => [command.id, command]));
}
