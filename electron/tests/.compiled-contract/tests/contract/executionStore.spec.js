"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const executionState_1 = require("../../src/renderer/domain/execution/executionState");
function run() {
    // === createExecutionState defaults match historical agentStore ===
    {
        const state = (0, executionState_1.createExecutionState)();
        strict_1.default.equal(state.model, 'anthropic/claude-sonnet-4-6');
        strict_1.default.equal(state.qualityPreset, 'balanced');
        strict_1.default.equal(state.mode, 'auto');
        strict_1.default.equal(state.cost, 0);
        strict_1.default.equal(state.step, 0);
        strict_1.default.equal(state.activeSessions, 0);
        strict_1.default.equal(state.connected, false);
    }
    // === reduceSetModel returns a new state with updated model ===
    {
        const a = (0, executionState_1.createExecutionState)();
        const b = (0, executionState_1.reduceSetModel)(a, 'openai/gpt-5.4');
        strict_1.default.equal(a.model, 'anthropic/claude-sonnet-4-6', 'original immutable');
        strict_1.default.equal(b.model, 'openai/gpt-5.4');
        strict_1.default.notEqual(a, b);
    }
    // === reduceSetCost ===
    {
        const a = (0, executionState_1.createExecutionState)();
        const b = (0, executionState_1.reduceSetCost)(a, 1.234);
        strict_1.default.equal(b.cost, 1.234);
    }
    // === reduceSetConnected ===
    {
        const a = (0, executionState_1.createExecutionState)();
        const b = (0, executionState_1.reduceSetConnected)(a, true);
        strict_1.default.equal(b.connected, true);
        strict_1.default.equal((0, executionState_1.reduceSetConnected)(b, false).connected, false);
    }
    // === reduceUpdateFromStatus picks known fields and falls back to current ===
    {
        const a = (0, executionState_1.createExecutionState)();
        const partial = {
            model: 'openai/gpt-5.4',
            qualityPreset: 'fast',
            mode: 'supervised',
            activeSessions: 7,
        };
        const b = (0, executionState_1.reduceUpdateFromStatus)(a, partial);
        strict_1.default.equal(b.model, 'openai/gpt-5.4');
        strict_1.default.equal(b.qualityPreset, 'fast');
        strict_1.default.equal(b.mode, 'supervised');
        strict_1.default.equal(b.activeSessions, 7);
    }
    // === reduceUpdateFromStatus tolerates missing fields (preserves current) ===
    {
        const a = (0, executionState_1.reduceSetModel)((0, executionState_1.createExecutionState)(), 'anthropic/claude-opus-4-7');
        const b = (0, executionState_1.reduceUpdateFromStatus)(a, {});
        strict_1.default.equal(b.model, 'anthropic/claude-opus-4-7');
        strict_1.default.equal(b.mode, 'auto');
    }
    // === reduceUpdateFromStatus normalises unknown qualityPreset to 'custom' (legacy) ===
    {
        const a = (0, executionState_1.createExecutionState)();
        const b = (0, executionState_1.reduceUpdateFromStatus)(a, { qualityPreset: 'gibberish' });
        strict_1.default.equal(b.qualityPreset, 'custom');
    }
    console.log('[contract] PASS execution-store reducers (7 cases)');
}
run();
