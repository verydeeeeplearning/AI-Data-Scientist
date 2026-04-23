"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.aggregateStages = aggregateStages;
const stage_1 = require("../../domain/execution/stage");
const stageMapper_1 = require("../../domain/execution/stageMapper");
const inferOutcome_1 = require("./inferOutcome");
function toExecutionToolEvent(activity) {
    return (0, stage_1.createExecutionToolEvent)({
        toolName: activity.name,
        category: (0, stageMapper_1.inferToolCategory)(activity.name),
        status: activity.status === 'done'
            ? 'completed'
            : activity.status === 'error'
                ? 'failed'
                : 'running',
        args: activity.args,
        outputPreview: activity.result,
        elapsedMs: activity.elapsed,
        startedAt: activity.startedAt,
        completedAt: activity.status === 'running'
            ? undefined
            : activity.elapsed !== undefined
                ? activity.startedAt + activity.elapsed
                : activity.startedAt,
    });
}
function deriveStageStatus(events) {
    if (events.length === 0) {
        return 'pending';
    }
    if (events.some((event) => event.status === 'failed')) {
        return 'failed';
    }
    if (events.some((event) => event.status === 'running')) {
        return 'running';
    }
    if (events.every((event) => event.status === 'completed')) {
        return 'completed';
    }
    return 'pending';
}
function minTimestamp(values) {
    const filtered = values.filter((value) => typeof value === 'number');
    if (filtered.length === 0) {
        return undefined;
    }
    return Math.min(...filtered);
}
function maxTimestamp(values) {
    const filtered = values.filter((value) => typeof value === 'number');
    if (filtered.length === 0) {
        return undefined;
    }
    return Math.max(...filtered);
}
function aggregateStages(activities) {
    const grouped = new Map();
    for (const activity of activities) {
        if ((0, stageMapper_1.isAgentControlTool)(activity.name)) {
            continue;
        }
        const toolEvent = toExecutionToolEvent(activity);
        const stageKey = (0, stageMapper_1.mapToolToStage)(toolEvent.toolName) ?? 'eda';
        if (!grouped.has(stageKey)) {
            grouped.set(stageKey, []);
        }
        grouped.get(stageKey)?.push(toolEvent);
    }
    return stage_1.STAGE_ORDER
        .filter((stageKey) => grouped.has(stageKey))
        .map((stageKey) => {
        const toolEvents = grouped.get(stageKey) ?? [];
        const metadata = (0, stage_1.getStageMetadata)(stageKey);
        const status = deriveStageStatus(toolEvents);
        return (0, stage_1.createStage)({
            key: stageKey,
            label: metadata.label,
            labelKey: metadata.labelKey,
            status,
            toolEvents,
            startedAt: minTimestamp(toolEvents.map((event) => event.startedAt)),
            completedAt: status === 'completed' || status === 'failed'
                ? maxTimestamp(toolEvents.map((event) => event.completedAt))
                : undefined,
            outcome: (0, inferOutcome_1.inferOutcome)({ key: stageKey, toolEvents }),
        });
    });
}
