"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.pauseAgent = pauseAgent;
async function pauseAgent(port, input) {
    return port(input);
}
