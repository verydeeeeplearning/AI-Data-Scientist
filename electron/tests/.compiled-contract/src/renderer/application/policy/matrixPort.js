"use strict";
/**
 * Renderer-side ports for the risk-tier matrix backend.
 *
 * Each port is a single async function so the composition hook
 * (`usePolicyMatrix`) can wire them to `rpc('policy.matrix.*')` while
 * keeping the application use cases (load/save/preview) pure and
 * trivially mockable in contract tests.
 */
Object.defineProperty(exports, "__esModule", { value: true });
