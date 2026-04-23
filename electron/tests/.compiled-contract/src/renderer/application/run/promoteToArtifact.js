"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.promoteToArtifact = promoteToArtifact;
const promoteToArtifactPort_1 = require("./promoteToArtifactPort");
async function promoteToArtifact(port, input) {
    if (!input.runId.trim()) {
        throw new Error('runId is required');
    }
    if (!input.cardId.trim()) {
        throw new Error('cardId is required');
    }
    if (!promoteToArtifactPort_1.PROMOTE_AUDIENCES.includes(input.audience)) {
        throw new Error(`audience must be one of: ${promoteToArtifactPort_1.PROMOTE_AUDIENCES.join(', ')}`);
    }
    return port(input);
}
