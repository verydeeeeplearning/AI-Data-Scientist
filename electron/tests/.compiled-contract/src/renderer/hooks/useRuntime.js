"use strict";
/**
 * Runtime hook that polls operator-console state from backend RPCs.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.useRuntime = useRuntime;
const react_1 = require("react");
const runtimeStore_1 = require("../stores/runtimeStore");
function useRuntime(on, rpc, connected) {
    const setStatus = (0, runtimeStore_1.useRuntimeStore)((s) => s.setStatus);
    const setSessions = (0, runtimeStore_1.useRuntimeStore)((s) => s.setSessions);
    const setRuns = (0, runtimeStore_1.useRuntimeStore)((s) => s.setRuns);
    const setTasks = (0, runtimeStore_1.useRuntimeStore)((s) => s.setTasks);
    const markUpdated = (0, runtimeStore_1.useRuntimeStore)((s) => s.markUpdated);
    const resetRuntime = (0, runtimeStore_1.useRuntimeStore)((s) => s.resetRuntime);
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
        if (!connected) {
            resetRuntime();
            return;
        }
        let cancelled = false;
        const guardedRefresh = async () => {
            try {
                await refreshRuntime();
            }
            catch (err) {
                if (!cancelled) {
                    console.warn('[useRuntime] refresh failed:', err);
                }
            }
        };
        void guardedRefresh();
        const timer = window.setInterval(() => {
            void guardedRefresh();
        }, 3000);
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
            cancelled = true;
            window.clearInterval(timer);
            unsubs.forEach((unsub) => unsub());
        };
    }, [connected, on, refreshRuntime, resetRuntime]);
}
