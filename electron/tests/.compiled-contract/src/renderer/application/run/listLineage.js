"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.listLineage = listLineage;
async function listLineage(port, input) {
    const rootRunId = input.rootRunId.trim();
    if (!rootRunId) {
        throw new Error('rootRunId is required');
    }
    return port({ rootRunId });
}
