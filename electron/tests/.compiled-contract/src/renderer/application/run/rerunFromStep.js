"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.rerunFromStep = rerunFromStep;
async function rerunFromStep(port, input) {
    if (!input.parentRunId.trim()) {
        throw new Error('parentRunId is required');
    }
    if (!input.planNodeId.trim()) {
        throw new Error('planNodeId is required');
    }
    return port(input);
}
