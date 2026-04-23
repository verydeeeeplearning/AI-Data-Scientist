"use strict";
/**
 * Application-layer port for fetching trust metadata.
 *
 * Trust store consumers depend only on this port; infrastructure binds the
 * implementation (`infrastructure/api/trustApi.ts`) at the composition root.
 */
Object.defineProperty(exports, "__esModule", { value: true });
