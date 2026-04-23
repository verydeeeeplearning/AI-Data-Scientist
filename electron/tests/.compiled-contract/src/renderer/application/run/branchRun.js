"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.branchRun = branchRun;
async function branchRun(port, input) {
    if (!input.parentRunId.trim()) {
        throw new Error('parentRunId is required');
    }
    if (!input.message.trim()) {
        throw new Error('message is required');
    }
    return port(input);
}
