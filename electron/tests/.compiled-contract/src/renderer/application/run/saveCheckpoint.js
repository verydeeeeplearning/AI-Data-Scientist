"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.saveCheckpoint = saveCheckpoint;
async function saveCheckpoint(port, input) {
    if (!input.sessionId.trim()) {
        throw new Error('sessionId is required');
    }
    if (!input.name.trim()) {
        throw new Error('name is required');
    }
    return port(input);
}
