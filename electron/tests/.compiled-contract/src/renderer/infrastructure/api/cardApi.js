"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.setCardPinned = setCardPinned;
exports.renderCardForAudience = renderCardForAudience;
exports.reportAudienceSwitch = reportAudienceSwitch;
exports.normalizeRenderedCard = normalizeRenderedCard;
exports.hasAudienceRenderedCardContent = hasAudienceRenderedCardContent;
const backendUrl_1 = require("../../utils/backendUrl");
function extractErrorMessage(payload, fallback) {
    if (!payload || typeof payload !== 'object') {
        return fallback;
    }
    const detail = payload.detail;
    if (typeof detail === 'string' && detail.trim().length > 0) {
        return detail;
    }
    return fallback;
}
async function setCardPinned(cardId, pinned) {
    const encodedCardId = encodeURIComponent(cardId);
    const response = await fetch(`${(0, backendUrl_1.getBackendBase)()}/api/cards/${encodedCardId}/pin`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ pinned }),
    });
    if (!response.ok) {
        let payload = null;
        try {
            payload = await response.json();
        }
        catch {
            // Ignore non-JSON error bodies.
        }
        throw new Error(extractErrorMessage(payload, `Card pin request failed with status ${response.status}`));
    }
    return response.json();
}
async function renderCardForAudience(input) {
    const response = await fetch(`${(0, backendUrl_1.getBackendBase)()}/api/cards/render-for-audience`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            cardId: input.cardId,
            audience: input.audience,
        }),
    });
    if (!response.ok) {
        let payload = null;
        try {
            payload = await response.json();
        }
        catch {
            // Ignore non-JSON error bodies.
        }
        throw new Error(extractErrorMessage(payload, `Audience render request failed with status ${response.status}`));
    }
    const payload = (await response.json());
    const renderedCard = normalizeRenderedCard(payload.renderedCard);
    if (!hasAudienceRenderedCardContent(renderedCard)) {
        throw new Error('Audience render response did not include usable content');
    }
    return renderedCard;
}
async function reportAudienceSwitch(input) {
    const response = await fetch(`${(0, backendUrl_1.getBackendBase)()}/api/cards/audience-switch`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            fromAudience: input.fromAudience ?? null,
            toAudience: input.toAudience,
            sessionId: input.sessionId ?? null,
        }),
    });
    if (!response.ok) {
        let payload = null;
        try {
            payload = await response.json();
        }
        catch {
            // Ignore non-JSON error bodies.
        }
        throw new Error(extractErrorMessage(payload, `Audience telemetry request failed with status ${response.status}`));
    }
}
function normalizeRenderedCard(payload) {
    if (!payload || typeof payload !== 'object') {
        return { summary: null, body: null, sections: [] };
    }
    const raw = payload;
    const sections = Array.isArray(raw.sections)
        ? raw.sections
            .map((section) => normalizeSection(section))
            .filter((section) => section !== null)
        : [];
    return {
        summary: typeof raw.summary === 'string' && raw.summary.trim().length > 0 ? raw.summary : null,
        body: typeof raw.body === 'string' && raw.body.trim().length > 0 ? raw.body : null,
        sections,
    };
}
function hasAudienceRenderedCardContent(payload) {
    if (!payload) {
        return false;
    }
    if (typeof payload.summary === 'string' && payload.summary.trim().length > 0) {
        return true;
    }
    if (typeof payload.body === 'string' && payload.body.trim().length > 0) {
        return true;
    }
    return payload.sections.length > 0;
}
function normalizeSection(payload) {
    if (!payload || typeof payload !== 'object') {
        return null;
    }
    const raw = payload;
    const id = typeof raw.id === 'string' && raw.id.trim().length > 0 ? raw.id : null;
    const title = typeof raw.title === 'string' && raw.title.trim().length > 0 ? raw.title : null;
    const body = typeof raw.body === 'string' && raw.body.trim().length > 0 ? raw.body : null;
    if (!id || !title || !body) {
        return null;
    }
    return { id, title, body };
}
