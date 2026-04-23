"use strict";
/**
 * Application-layer port for toggling result card pin state.
 *
 * Components depend on the port; the composition root binds the HTTP
 * adapter (`infrastructure/api/cardApi.ts`) so the components layer never
 * imports from infrastructure (Clean Arch + lint:arch compliance).
 */
Object.defineProperty(exports, "__esModule", { value: true });
