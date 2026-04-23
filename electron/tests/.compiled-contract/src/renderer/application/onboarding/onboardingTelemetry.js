"use strict";
/**
 * Onboarding telemetry port.
 *
 * Wave 2 W2-E phase 2: define a transport-independent telemetry surface so the
 * wizard can emit step transitions, finalize success, and finalize failure
 * without coupling to a specific observability vendor. Adapters live in the
 * infrastructure layer and the composition root injects the port.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.NOOP_ONBOARDING_TELEMETRY = void 0;
exports.buildConsoleOnboardingTelemetry = buildConsoleOnboardingTelemetry;
const NOOP_ONBOARDING_TELEMETRY = () => { };
exports.NOOP_ONBOARDING_TELEMETRY = NOOP_ONBOARDING_TELEMETRY;
function buildConsoleOnboardingTelemetry(consoleLike) {
    return (event) => {
        consoleLike.info('[onboarding-telemetry]', event.type, event);
    };
}
