"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getMissionContext = getMissionContext;
async function getMissionContext(port, sessionId) {
    return port(sessionId);
}
