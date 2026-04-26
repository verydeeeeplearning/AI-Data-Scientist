"use strict";
/**
 * Session-summary formatters shared by MissionContextBar, SessionDrawer,
 * and FloatingChat header. Pure functions — no React, no stores.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.formatBudget = formatBudget;
exports.formatBudgetRatio = formatBudgetRatio;
exports.formatElapsed = formatElapsed;
exports.formatStage = formatStage;
function formatBudget(cost, limit) {
    const safeCost = Number.isFinite(cost) ? cost : 0;
    if (!Number.isFinite(limit) || limit <= 0) {
        return `$${safeCost.toFixed(2)}`;
    }
    return `$${safeCost.toFixed(2)} / $${limit.toFixed(0)}`;
}
function formatBudgetRatio(cost, limit) {
    if (!Number.isFinite(cost) || !Number.isFinite(limit) || limit <= 0)
        return 0;
    return Math.max(0, Math.min(1, cost / limit));
}
/** "12s" / "3m 04s" / "1h 12m". Stops at hour granularity. */
function formatElapsed(startedAt, now = Date.now()) {
    if (!startedAt || !Number.isFinite(startedAt))
        return '—';
    const seconds = Math.max(0, Math.floor((now - startedAt) / 1000));
    if (seconds < 60)
        return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remSeconds = seconds % 60;
    if (minutes < 60)
        return `${minutes}m ${remSeconds.toString().padStart(2, '0')}s`;
    const hours = Math.floor(minutes / 60);
    const remMinutes = minutes % 60;
    return `${hours}h ${remMinutes.toString().padStart(2, '0')}m`;
}
function formatStage(current, total, idleLabel) {
    if (!Number.isFinite(total) || total <= 0)
        return idleLabel;
    const safeCurrent = Math.max(0, Math.min(current, total));
    return `${safeCurrent}/${total}`;
}
