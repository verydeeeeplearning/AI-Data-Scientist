"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.resumeFromCheckpoint = resumeFromCheckpoint;
async function resumeFromCheckpoint(port, input) {
    if (!input.sessionId.trim()) {
        throw new Error('sessionId is required');
    }
    if (!input.message.trim()) {
        throw new Error('message is required');
    }
    return port(input);
}
