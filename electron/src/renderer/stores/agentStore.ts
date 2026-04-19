/**
 * @deprecated Use `executionStore` instead. This shim preserves the legacy
 * `useAgentStore` import for callers during the cross_cutting/PLAN_02 split
 * (Sub-Phase 1.2). New code MUST import from `./executionStore`.
 *
 * Removal target: end of Phase 2 (after all consumers migrated).
 */

export { useExecutionStore as useAgentStore } from './executionStore';
export type { ExecutionMode, QualityPreset } from './executionStore';
