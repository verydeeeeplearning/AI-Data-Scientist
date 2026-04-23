"use strict";
/**
 * Canonical backend→frontend event payload types.
 *
 * Each interface here is the single source of truth for an event received via
 * the WebSocket RPC channel. The matching Python TypedDicts live in
 * ``src/ds_agent/api/event_schemas.py``.
 *
 * Keep both files in sync when adding or changing events.
 */
Object.defineProperty(exports, "__esModule", { value: true });
