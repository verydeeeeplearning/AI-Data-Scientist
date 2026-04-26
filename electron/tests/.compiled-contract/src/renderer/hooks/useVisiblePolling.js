"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.useVisiblePolling = useVisiblePolling;
const react_1 = require("react");
function useVisiblePolling(callback, options) {
    const { intervalMs, enabled, fireOnVisible = true } = options;
    const callbackRef = (0, react_1.useRef)(callback);
    callbackRef.current = callback;
    (0, react_1.useEffect)(() => {
        if (!enabled) {
            return;
        }
        let timer = null;
        const stop = () => {
            if (timer !== null) {
                window.clearInterval(timer);
                timer = null;
            }
        };
        const start = () => {
            if (timer !== null) {
                return;
            }
            if (fireOnVisible) {
                callbackRef.current();
            }
            timer = window.setInterval(() => {
                callbackRef.current();
            }, intervalMs);
        };
        const handleVisibilityChange = () => {
            if (document.hidden) {
                stop();
                return;
            }
            start();
        };
        if (!document.hidden) {
            start();
        }
        document.addEventListener('visibilitychange', handleVisibilityChange);
        return () => {
            stop();
            document.removeEventListener('visibilitychange', handleVisibilityChange);
        };
    }, [enabled, fireOnVisible, intervalMs]);
}
