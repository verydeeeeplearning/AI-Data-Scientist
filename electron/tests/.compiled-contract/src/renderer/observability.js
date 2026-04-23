"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.bootstrapRendererObservabilityFromQuery = bootstrapRendererObservabilityFromQuery;
exports.configureRendererObservability = configureRendererObservability;
exports.captureRendererException = captureRendererException;
const RendererSentry = __importStar(require("@sentry/electron/renderer"));
const REDACTED = '***REDACTED***';
const SECRET_FIELD_TOKENS = ['key', 'token', 'secret', 'password', 'authorization', 'cookie'];
const SECRET_PATTERNS = [
    /READY:(\d+):[^\s]+/g,
    /sk-ant-[A-Za-z0-9\-_]+/g,
    /sk-[A-Za-z0-9\-_]{20,}/g,
    /ya29\.[A-Za-z0-9\-_]+/g,
    /1\/\/[A-Za-z0-9\-_]+/g,
    /\b\d{8,}:[A-Za-z0-9\-_]{20,}\b/g,
];
const state = {
    initialized: false,
    sentryConfigured: false,
    errorReportingEnabled: false,
    telemetryEnabled: false,
};
function bootstrapRendererObservabilityFromQuery() {
    const params = new URLSearchParams(window.location.search);
    return configureRendererObservability({
        sentryConfigured: params.get('sentry') === '1',
        errorReportingEnabled: params.get('errorReporting') === '1',
        telemetryEnabled: params.get('telemetry') === '1',
    });
}
function configureRendererObservability(update) {
    state.sentryConfigured = update.sentryConfigured ?? state.sentryConfigured;
    state.errorReportingEnabled = update.errorReportingEnabled ?? state.errorReportingEnabled;
    state.telemetryEnabled = update.telemetryEnabled ?? state.telemetryEnabled;
    if (state.sentryConfigured && !state.initialized) {
        RendererSentry.init({
            beforeSend(event) {
                if (!state.errorReportingEnabled) {
                    return null;
                }
                return sanitizeUnknown(event);
            },
            beforeSendTransaction(event) {
                if (!state.telemetryEnabled) {
                    return null;
                }
                return sanitizeUnknown(event);
            },
        });
        state.initialized = true;
    }
    return {
        sentryConfigured: state.sentryConfigured,
        errorReportingEnabled: state.errorReportingEnabled,
        telemetryEnabled: state.telemetryEnabled,
    };
}
function captureRendererException(error, context) {
    if (!state.initialized || !state.sentryConfigured) {
        return;
    }
    RendererSentry.withScope((scope) => {
        if (context) {
            scope.setExtras(sanitizeUnknown(context));
        }
        RendererSentry.captureException(normalizeError(error));
    });
}
function sanitizeUnknown(value) {
    if (typeof value === 'string') {
        return sanitizeText(value);
    }
    if (Array.isArray(value)) {
        return value.map((entry) => sanitizeUnknown(entry));
    }
    if (value && typeof value === 'object') {
        const result = {};
        for (const [key, entry] of Object.entries(value)) {
            if (SECRET_FIELD_TOKENS.some((token) => key.toLowerCase().includes(token))) {
                result[key] = REDACTED;
                continue;
            }
            result[key] = sanitizeUnknown(entry);
        }
        return result;
    }
    return value;
}
function sanitizeText(value) {
    let sanitized = value;
    for (const pattern of SECRET_PATTERNS) {
        sanitized = sanitized.replace(pattern, (match) => {
            if (match.startsWith('READY:')) {
                const port = match.split(':')[1] ?? 'unknown';
                return `READY:${port}:${REDACTED}`;
            }
            return REDACTED;
        });
    }
    return sanitized;
}
function normalizeError(error) {
    if (error instanceof Error) {
        return error;
    }
    return new Error(String(error));
}
