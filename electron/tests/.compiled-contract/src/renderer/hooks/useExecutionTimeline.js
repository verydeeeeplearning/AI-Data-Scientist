"use strict";
/**
 * useExecutionTimeline — bridges chatStore tool activities to the stage timeline.
 *
 * Wraps `aggregateStages` with memoization, derives the currently-running stage,
 * and exposes the latest stage transition so callers can drive announcements
 * or jump targets without re-implementing aggregation.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.selectExecutionTimeline = selectExecutionTimeline;
exports.useExecutionTimeline = useExecutionTimeline;
const react_1 = require("react");
const aggregateStages_1 = require("../application/execution/aggregateStages");
const chatStore_1 = require("../stores/chatStore");
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
/**
 * Pure aggregator slice — exposed for testing the hook contract without React.
 */
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
function useExecutionTimeline(options = {}) {
    const storeActivities = (0, chatStore_1.useChatStore)((state) => state.toolActivities);
    const activities = options.activitiesOverride ?? storeActivities;
    const snapshot = (0, react_1.useMemo)(() => selectExecutionTimeline(activities), [activities]);
    const previousTransitionRef = (0, react_1.useRef)(null);
    const transitionForCallers = (0, react_1.useMemo)(() => {
        if (transitionsEqual(previousTransitionRef.current, snapshot.latestTransition)) {
            return previousTransitionRef.current;
        }
        return snapshot.latestTransition;
    }, [snapshot.latestTransition]);
    (0, react_1.useEffect)(() => {
        previousTransitionRef.current = transitionForCallers;
    }, [transitionForCallers]);
    if (transitionForCallers === snapshot.latestTransition) {
        return snapshot;
    }
    return Object.freeze({
        ...snapshot,
        latestTransition: transitionForCallers,
    });
}
