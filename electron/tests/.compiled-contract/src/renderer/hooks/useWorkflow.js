"use strict";
/**
 * Workflow hook — subscribes to DS workflow events and updates workflowStore.
 *
 * Event payload shapes are defined in ``types/events.ts`` (canonical contract).
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.useWorkflow = useWorkflow;
const react_1 = require("react");
const workflowStore_1 = require("../stores/workflowStore");
function cast(payload) {
    return payload;
}
function useWorkflow(on, rpc, connected) {
    const updateStage = (0, workflowStore_1.useWorkflowStore)((s) => s.updateStage);
    const addWarning = (0, workflowStore_1.useWorkflowStore)((s) => s.addWarning);
    const addExperiment = (0, workflowStore_1.useWorkflowStore)((s) => s.addExperiment);
    const setApprovals = (0, workflowStore_1.useWorkflowStore)((s) => s.setApprovals);
    const upsertApproval = (0, workflowStore_1.useWorkflowStore)((s) => s.upsertApproval);
    const setProfileResults = (0, workflowStore_1.useWorkflowStore)((s) => s.setProfileResults);
    const updateBudget = (0, workflowStore_1.useWorkflowStore)((s) => s.updateBudget);
    const updateContext = (0, workflowStore_1.useWorkflowStore)((s) => s.updateContext);
    const setOverallQuality = (0, workflowStore_1.useWorkflowStore)((s) => s.setOverallQuality);
    const recordSandboxViolation = (0, workflowStore_1.useWorkflowStore)((s) => s.recordSandboxViolation);
    (0, react_1.useEffect)(() => {
        const unsubs = [
            on('workflow.step', (payload) => {
                const e = cast(payload);
                updateStage(e.stage, e.status, e.score);
            }),
            on('quality.update', (payload) => {
                const e = cast(payload);
                updateStage(e.stage, 'done', e.score);
                if (typeof e.overall === 'number' && typeof e.grade === 'string') {
                    setOverallQuality(e.overall, e.grade);
                }
            }),
            on('harness.warning', (payload) => {
                const e = cast(payload);
                addWarning({
                    id: e.id ?? '',
                    type: e.type ?? 'unknown',
                    severity: e.severity ?? 'medium',
                    message: e.message ?? '',
                    suggestion: e.suggestion,
                });
            }),
            on('experiment.log', (payload) => {
                const e = cast(payload);
                addExperiment({
                    id: e.id ?? `exp-${Date.now()}`,
                    model: e.model ?? 'unknown',
                    isBaseline: e.isBaseline ?? false,
                    metrics: e.metrics ?? {},
                    trainingTime: e.trainingTime,
                    timestamp: e.timestamp ?? Date.now(),
                });
            }),
            on('profile.results', (payload) => {
                const e = cast(payload);
                setProfileResults({
                    summary: e.summary ?? '',
                    grade: e.grade ?? 'C',
                    rows: e.rows ?? 0,
                    columns: e.columns ?? 0,
                    missingPct: e.missingPct ?? 0,
                    issues: e.issues ?? [],
                });
            }),
            on('budget.detail', (payload) => {
                const e = cast(payload);
                updateBudget({
                    tokensUsed: e.tokensUsed ?? 0,
                    tokensMax: e.tokensMax ?? 200000,
                    costUsd: e.costUsd ?? 0,
                    costMax: e.costMax ?? 10,
                });
            }),
            on('budget.warning', (payload) => {
                const e = cast(payload);
                addWarning({
                    id: `budget-${e.level ?? 'warning'}-${Math.round(e.pct ?? 0)}`,
                    type: 'budget',
                    severity: e.level === 'exhausted' ? 'high' : 'medium',
                    message: e.message ?? 'Budget warning',
                    suggestion: e.level === 'exhausted'
                        ? 'Increase the monthly budget in Settings to start another analysis.'
                        : 'Review the monthly budget before launching another expensive run.',
                });
            }),
            on('context.status', (payload) => {
                const e = cast(payload);
                updateContext({
                    usedPct: e.usedPct ?? 0,
                    compressed: e.compressed ?? false,
                });
            }),
            on('approval.requested', (payload) => {
                const e = cast(payload);
                upsertApproval(e);
            }),
            on('approval.resolved', (payload) => {
                const e = cast(payload);
                upsertApproval(e);
            }),
            on('sandbox.violation', (payload) => {
                const e = cast(payload);
                recordSandboxViolation({
                    kind: e.kind,
                    detail: e.detail,
                    blocked: e.blocked,
                    tool: e.tool,
                    sessionId: e.sessionId ?? null,
                    runId: e.runId ?? null,
                    // backend emits seconds; store uses ms
                    timestamp: Math.round((e.timestamp ?? Date.now() / 1000) * 1000),
                });
            }),
        ];
        return () => {
            unsubs.forEach((fn) => fn());
        };
    }, [
        on,
        updateStage,
        addWarning,
        addExperiment,
        upsertApproval,
        recordSandboxViolation,
        setProfileResults,
        updateBudget,
        updateContext,
        setOverallQuality,
    ]);
    (0, react_1.useEffect)(() => {
        if (!connected) {
            setApprovals([]);
            return;
        }
        let cancelled = false;
        const loadApprovals = async () => {
            try {
                const result = await rpc('approval.list', { limit: 20 });
                if (!cancelled) {
                    setApprovals(result.approvals ?? []);
                }
            }
            catch (err) {
                console.warn('[useWorkflow] approval.list failed:', err);
            }
        };
        void loadApprovals();
        const timer = window.setInterval(() => {
            void loadApprovals();
        }, 3000);
        return () => {
            cancelled = true;
            window.clearInterval(timer);
        };
    }, [connected, rpc, setApprovals]);
}
