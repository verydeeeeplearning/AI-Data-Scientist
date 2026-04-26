"use strict";
/**
 * Runtime hook that polls operator-console state from backend RPCs.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.useRuntime = useRuntime;
const react_1 = require("react");
const runtimeStore_1 = require("../stores/runtimeStore");
const useVisiblePolling_1 = require("./useVisiblePolling");
function useRuntime(on, rpc, connected) {
    const setStatus = (0, runtimeStore_1.useRuntimeStore)((s) => s.setStatus);
    const setSessions = (0, runtimeStore_1.useRuntimeStore)((s) => s.setSessions);
    const setRuns = (0, runtimeStore_1.useRuntimeStore)((s) => s.setRuns);
    const setTasks = (0, runtimeStore_1.useRuntimeStore)((s) => s.setTasks);
    const markUpdated = (0, runtimeStore_1.useRuntimeStore)((s) => s.markUpdated);
    const resetRuntime = (0, runtimeStore_1.useRuntimeStore)((s) => s.resetRuntime);
    const refreshGenerationRef = (0, react_1.useRef)(0);
    const refreshRuntime = (0, react_1.useCallback)(async () => {
        const [statusResult, sessionsResult, runsResult, tasksResult] = await Promise.all([
            rpc('status.get'),
            rpc('session.list', { limit: 12 }),
            rpc('run.list', { limit: 12 }),
            rpc('task.list', { limit: 12 }),
        ]);
        setStatus(statusResult ?? null);
        setSessions(sessionsResult.sessions ?? []);
        setRuns(runsResult.runs ?? []);
        setTasks(tasksResult.tasks ?? []);
        markUpdated();
    }, [markUpdated, rpc, setRuns, setSessions, setStatus, setTasks]);
    (0, react_1.useEffect)(() => {
        refreshGenerationRef.current += 1;
        if (!connected) {
            resetRuntime();
        }
        return () => {
            refreshGenerationRef.current += 1;
        };
    }, [connected, refreshRuntime, resetRuntime]);
    const guardedRefresh = (0, react_1.useCallback)(async () => {
        const generation = refreshGenerationRef.current;
        try {
            await refreshRuntime();
        }
        catch (err) {
            if (refreshGenerationRef.current === generation) {
                console.warn('[useRuntime] refresh failed:', err);
            }
        }
    }, [refreshRuntime]);
    (0, useVisiblePolling_1.useVisiblePolling)(() => {
        void guardedRefresh();
    }, { intervalMs: 3000, enabled: connected });
    (0, react_1.useEffect)(() => {
        if (!connected) {
            return;
        }
        const unsubs = [
            on('stream.done', () => {
                void guardedRefresh();
            }),
            on('approval.requested', () => {
                void guardedRefresh();
            }),
            on('approval.resolved', () => {
                void guardedRefresh();
            }),
            on('workspace.changed', () => {
                void guardedRefresh();
            }),
            on('runtime.alert', () => {
                void guardedRefresh();
            }),
        ];
        return () => {
            unsubs.forEach((unsub) => unsub());
        };
    }, [connected, guardedRefresh, on]);
}
