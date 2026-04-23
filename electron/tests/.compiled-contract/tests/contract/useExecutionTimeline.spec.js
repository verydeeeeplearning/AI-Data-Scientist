"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const selectExecutionTimeline_1 = require("../../src/renderer/application/execution/selectExecutionTimeline");
function makeActivity(name, overrides = {}) {
    return {
        name,
        status: 'done',
        startedAt: 1000,
        ...overrides,
    };
}
function run() {
    // Empty input → empty snapshot.
    {
        const snap = (0, selectExecutionTimeline_1.selectExecutionTimeline)([]);
        strict_1.default.equal(snap.stages.length, 0);
        strict_1.default.equal(snap.currentStage, null);
        strict_1.default.equal(snap.latestTransition, null);
        strict_1.default.equal(snap.hasActivity, false);
    }
    // Single completed stage → currentStage falls back to last stage.
    {
        const snap = (0, selectExecutionTimeline_1.selectExecutionTimeline)([
            makeActivity('read_file', { result: 'Loaded 100 rows from a.csv' }),
        ]);
        strict_1.default.equal(snap.stages.length, 1);
        strict_1.default.equal(snap.currentStage?.key, 'data_loading');
        strict_1.default.equal(snap.currentStage?.status, 'completed');
        strict_1.default.equal(snap.latestTransition?.stageKey, 'data_loading');
        strict_1.default.equal(snap.latestTransition?.status, 'completed');
        strict_1.default.equal(snap.latestTransition?.toolEventCount, 1);
        strict_1.default.equal(snap.hasActivity, true);
    }
    // Running stage takes precedence over later completed/failed.
    {
        const snap = (0, selectExecutionTimeline_1.selectExecutionTimeline)([
            makeActivity('read_file', { result: 'Loaded 1 file', startedAt: 1 }),
            makeActivity('train_model', { status: 'running', startedAt: 2 }),
            makeActivity('evaluate_model', { startedAt: 3 }),
        ]);
        strict_1.default.equal(snap.currentStage?.status, 'running');
        strict_1.default.equal(snap.currentStage?.key, 'baseline_modeling');
        strict_1.default.equal(snap.latestTransition?.status, 'running');
    }
    // Agent-control tools must not appear as stages.
    {
        const snap = (0, selectExecutionTimeline_1.selectExecutionTimeline)([
            makeActivity('ask_user'),
            makeActivity('memory_search'),
            makeActivity('skill_search'),
        ]);
        strict_1.default.equal(snap.stages.length, 0, 'Pure agent-control input → no stages');
        strict_1.default.equal(snap.currentStage, null);
        strict_1.default.equal(snap.latestTransition, null);
        strict_1.default.equal(snap.hasActivity, true, 'hasActivity reflects raw activity input');
    }
    // Failed stage surfaces as the current stage if newest in order.
    {
        const snap = (0, selectExecutionTimeline_1.selectExecutionTimeline)([
            makeActivity('read_file', { startedAt: 1 }),
            makeActivity('train_model', { status: 'error', startedAt: 2 }),
        ]);
        strict_1.default.equal(snap.currentStage?.key, 'baseline_modeling');
        strict_1.default.equal(snap.currentStage?.status, 'failed');
    }
    // Snapshot stability: identical inputs produce equal transitions.
    {
        const input = [
            makeActivity('read_file', { startedAt: 1 }),
            makeActivity('run_eda', { status: 'running', startedAt: 2 }),
        ];
        const a = (0, selectExecutionTimeline_1.selectExecutionTimeline)(input);
        const b = (0, selectExecutionTimeline_1.selectExecutionTimeline)(input);
        strict_1.default.deepEqual(a.latestTransition, b.latestTransition);
        strict_1.default.equal((0, selectExecutionTimeline_1.transitionsEqual)(a.latestTransition, b.latestTransition), true);
    }
    // transitionsEqual contract.
    {
        strict_1.default.equal((0, selectExecutionTimeline_1.transitionsEqual)(null, null), true);
        strict_1.default.equal((0, selectExecutionTimeline_1.transitionsEqual)(null, { stageKey: 'eda', status: 'running', toolEventCount: 1 }), false);
        strict_1.default.equal((0, selectExecutionTimeline_1.transitionsEqual)({ stageKey: 'eda', status: 'running', toolEventCount: 1 }, { stageKey: 'eda', status: 'running', toolEventCount: 1 }), true);
        strict_1.default.equal((0, selectExecutionTimeline_1.transitionsEqual)({ stageKey: 'eda', status: 'running', toolEventCount: 1 }, { stageKey: 'eda', status: 'completed', toolEventCount: 1 }), false);
        strict_1.default.equal((0, selectExecutionTimeline_1.transitionsEqual)({ stageKey: 'eda', status: 'running', toolEventCount: 1 }, { stageKey: 'reporting', status: 'running', toolEventCount: 1 }), false);
    }
    console.log('[contract] PASS use-execution-timeline (22 cases)');
}
run();
