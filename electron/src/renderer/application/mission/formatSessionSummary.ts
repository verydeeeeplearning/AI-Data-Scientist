/**
 * Session-summary formatters shared by MissionContextBar, SessionDrawer,
 * and FloatingChat header. Pure functions — no React, no stores.
 */

export function formatBudget(cost: number, limit: number): string {
  const safeCost = Number.isFinite(cost) ? cost : 0;
  if (!Number.isFinite(limit) || limit <= 0) {
    return `$${safeCost.toFixed(2)}`;
  }
  return `$${safeCost.toFixed(2)} / $${limit.toFixed(0)}`;
}

export function formatBudgetRatio(cost: number, limit: number): number {
  if (!Number.isFinite(cost) || !Number.isFinite(limit) || limit <= 0) return 0;
  return Math.max(0, Math.min(1, cost / limit));
}

/** "12s" / "3m 04s" / "1h 12m". Stops at hour granularity. */
export function formatElapsed(startedAt: number | null | undefined, now: number = Date.now()): string {
  if (!startedAt || !Number.isFinite(startedAt)) return '—';
  const seconds = Math.max(0, Math.floor((now - startedAt) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remSeconds = seconds % 60;
  if (minutes < 60) return `${minutes}m ${remSeconds.toString().padStart(2, '0')}s`;
  const hours = Math.floor(minutes / 60);
  const remMinutes = minutes % 60;
  return `${hours}h ${remMinutes.toString().padStart(2, '0')}m`;
}

export function formatStage(current: number, total: number, idleLabel: string): string {
  if (!Number.isFinite(total) || total <= 0) return idleLabel;
  const safeCurrent = Math.max(0, Math.min(current, total));
  return `${safeCurrent}/${total}`;
}
