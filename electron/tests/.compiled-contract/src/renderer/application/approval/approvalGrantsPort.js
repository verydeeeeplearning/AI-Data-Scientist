"use strict";
/**
 * Application-layer ports for approval grants (W2-F).
 *
 * The settings UI consumes these ports; the composition root binds them to
 * the HTTP adapter in `infrastructure/api/approvalGrantsApi.ts`. Components
 * never import from infrastructure directly, satisfying the Clean Arch
 * dependency rule enforced by `lint:arch`.
 */
Object.defineProperty(exports, "__esModule", { value: true });
