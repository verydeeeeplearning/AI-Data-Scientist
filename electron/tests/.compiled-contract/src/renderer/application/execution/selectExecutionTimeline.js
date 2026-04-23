"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.transitionsEqual = transitionsEqual;
exports.selectExecutionTimeline = selectExecutionTimeline;
const aggregateStages_1 = require("./aggregateStages");
function pickCurrentStage(stages) {
    for (let index = stages.length - 1; index >= 0; index -= 1) {
        const stage = stages[index];
        if (stage.status === 'running') {
            return stage;
        }
    }
    return stages[stages.length - 1] ?? null;
}
function buildTransition(stage) {
    if (!stage) {
        return null;
    }
    return Object.freeze({
        stageKey: stage.key,
        status: stage.status,
        toolEventCount: stage.toolEvents.length,
    });
}
function transitionsEqual(a, b) {
    if (a === b)
        return true;
    if (a === null || b === null)
        return false;
    return (a.stageKey === b.stageKey
        && a.status === b.status
        && a.toolEventCount === b.toolEventCount);
}
function selectExecutionTimeline(activities) {
    const stages = (0, aggregateStages_1.aggregateStages)(activities);
    const currentStage = pickCurrentStage(stages);
    return Object.freeze({
        stages,
        currentStage,
        latestTransition: buildTransition(currentStage),
        hasActivity: activities.length > 0,
    });
}
