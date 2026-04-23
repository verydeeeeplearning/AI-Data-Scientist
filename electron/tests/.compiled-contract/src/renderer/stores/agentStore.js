"use strict";
/**
 * @deprecated Use `executionStore` instead. This shim preserves the legacy
 * `useAgentStore` import for callers during the cross_cutting/PLAN_02 split
 * (Sub-Phase 1.2). New code MUST import from `./executionStore`.
 *
 * Removal target: end of Phase 2 (after all consumers migrated).
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.useAgentStore = void 0;
var executionStore_1 = require("./executionStore");
Object.defineProperty(exports, "useAgentStore", { enumerable: true, get: function () { return executionStore_1.useExecutionStore; } });
