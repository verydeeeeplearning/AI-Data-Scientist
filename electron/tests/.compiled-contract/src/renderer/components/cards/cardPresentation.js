"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getCardMeta = getCardMeta;
exports.getCardEmphasisProfile = getCardEmphasisProfile;
exports.getString = getString;
exports.getNumber = getNumber;
exports.getRecord = getRecord;
exports.getStringArray = getStringArray;
exports.formatCardTimestamp = formatCardTimestamp;
exports.formatMetricValue = formatMetricValue;
exports.formatDelta = formatDelta;
exports.getCardTitle = getCardTitle;
exports.getCardSummary = getCardSummary;
exports.getCardActionDescriptors = getCardActionDescriptors;
exports.getSeverityTone = getSeverityTone;
const lucide_react_1 = require("lucide-react");
const DEFAULT_TONE = {
    badgeClassName: 'border-ds-border bg-ds-surface text-ds-muted',
    panelClassName: 'border-ds-border bg-ds-surface/80 text-ds-text',
};
const CARD_META = {
    insight: {
        icon: lucide_react_1.Lightbulb,
        label: 'Insight',
        tone: {
            badgeClassName: 'border-sky-400/30 bg-sky-400/10 text-sky-200',
            panelClassName: 'border-sky-400/20 bg-sky-400/5 text-sky-100',
        },
    },
    experiment: {
        icon: lucide_react_1.Beaker,
        label: 'Experiment',
        tone: {
            badgeClassName: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200',
            panelClassName: 'border-emerald-400/20 bg-emerald-400/5 text-emerald-100',
        },
    },
    risk: {
        icon: lucide_react_1.AlertTriangle,
        label: 'Risk',
        tone: {
            badgeClassName: 'border-amber-400/30 bg-amber-400/10 text-amber-200',
            panelClassName: 'border-amber-400/20 bg-amber-400/5 text-amber-100',
        },
    },
    artifact: {
        icon: lucide_react_1.FileBox,
        label: 'Artifact',
        tone: {
            badgeClassName: 'border-violet-400/30 bg-violet-400/10 text-violet-200',
            panelClassName: 'border-violet-400/20 bg-violet-400/5 text-violet-100',
        },
    },
    other: {
        icon: lucide_react_1.Sparkles,
        label: 'Result',
        tone: DEFAULT_TONE,
    },
};
const CARD_EMPHASIS_PROFILES = {
    ds: {
        insight: {
            audience: 'ds',
            summarySource: 'original',
            bodySource: 'original',
            sectionDensity: 'none',
        },
        experiment: {
            audience: 'ds',
            summarySource: 'original',
            bodySource: 'original',
            sectionDensity: 'none',
        },
        risk: {
            audience: 'ds',
            summarySource: 'original',
            bodySource: 'original',
            sectionDensity: 'none',
        },
        artifact: {
            audience: 'ds',
            summarySource: 'original',
            bodySource: 'original',
            sectionDensity: 'none',
        },
        other: {
            audience: 'ds',
            summarySource: 'original',
            bodySource: 'original',
            sectionDensity: 'none',
        },
    },
    exec: {
        insight: {
            audience: 'exec',
            summarySource: 'rendered',
            bodySource: 'rendered',
            sectionDensity: 'compact',
        },
        experiment: {
            audience: 'exec',
            summarySource: 'rendered',
            bodySource: 'rendered',
            sectionDensity: 'compact',
        },
        risk: {
            audience: 'exec',
            summarySource: 'rendered',
            bodySource: 'rendered',
            sectionDensity: 'compact',
        },
        artifact: {
            audience: 'exec',
            summarySource: 'rendered',
            bodySource: 'rendered',
            sectionDensity: 'compact',
        },
        other: {
            audience: 'exec',
            summarySource: 'rendered',
            bodySource: 'rendered',
            sectionDensity: 'compact',
        },
    },
    ml: {
        insight: {
            audience: 'ml',
            summarySource: 'rendered',
            bodySource: 'rendered',
            sectionDensity: 'full',
        },
        experiment: {
            audience: 'ml',
            summarySource: 'rendered',
            bodySource: 'rendered',
            sectionDensity: 'full',
        },
        risk: {
            audience: 'ml',
            summarySource: 'rendered',
            bodySource: 'rendered',
            sectionDensity: 'full',
        },
        artifact: {
            audience: 'ml',
            summarySource: 'rendered',
            bodySource: 'rendered',
            sectionDensity: 'compact',
        },
        other: {
            audience: 'ml',
            summarySource: 'rendered',
            bodySource: 'rendered',
            sectionDensity: 'full',
        },
    },
};
function getCardMeta(card) {
    return CARD_META[card.type] ?? CARD_META.other;
}
function getCardEmphasisProfile(cardType, audience) {
    return CARD_EMPHASIS_PROFILES[audience]?.[cardType] ?? CARD_EMPHASIS_PROFILES.ds.other;
}
function getString(value) {
    if (typeof value !== 'string') {
        return null;
    }
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
}
function getNumber(value) {
    if (typeof value === 'number' && Number.isFinite(value)) {
        return value;
    }
    if (typeof value === 'string' && value.trim().length > 0) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : null;
    }
    return null;
}
function getRecord(value) {
    return typeof value === 'object' && value !== null ? value : null;
}
function getStringArray(value) {
    if (!Array.isArray(value)) {
        return [];
    }
    return value
        .map((item) => getString(item))
        .filter((item) => item !== null);
}
function formatCardTimestamp(createdAt) {
    const timestamp = createdAt > 1000000000000 ? createdAt : createdAt * 1000;
    if (!Number.isFinite(timestamp)) {
        return 'Unknown time';
    }
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) {
        return 'Unknown time';
    }
    return new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
    }).format(date);
}
function formatMetricValue(value) {
    if (typeof value === 'number' && Number.isFinite(value)) {
        if (Math.abs(value) >= 1000) {
            return value.toLocaleString(undefined, {
                maximumFractionDigits: 2,
            });
        }
        return value.toLocaleString(undefined, {
            maximumFractionDigits: 4,
        });
    }
    return getString(value);
}
function formatDelta(value) {
    const numeric = getNumber(value);
    if (numeric === null) {
        return null;
    }
    const sign = numeric > 0 ? '+' : '';
    return `${sign}${numeric.toLocaleString(undefined, {
        maximumFractionDigits: 4,
    })}`;
}
function getCardTitle(card) {
    const explicitTitle = getString(card.title);
    if (explicitTitle) {
        return explicitTitle;
    }
    if (card.type === 'experiment') {
        return getString(card.modelLabel) ?? 'Experiment result';
    }
    if (card.type === 'artifact') {
        return getString(card.fileRef) ?? 'Generated artifact';
    }
    if (card.type === 'risk') {
        return 'Risk detected';
    }
    if (card.type === 'insight') {
        return 'Key insight';
    }
    return 'Additional result';
}
function getCardSummary(card) {
    if (card.type === 'insight') {
        const keyMetric = getRecord(card.keyMetric);
        const label = getString(keyMetric?.label);
        const value = formatMetricValue(keyMetric?.value);
        return label && value ? `${label}: ${value}` : null;
    }
    if (card.type === 'experiment') {
        const metric = getRecord(card.primaryMetric);
        const metricName = getString(metric?.name);
        const metricValue = formatMetricValue(metric?.value);
        if (metricName && metricValue) {
            return `${metricName}: ${metricValue}`;
        }
        return getString(card.dataVersion);
    }
    if (card.type === 'risk') {
        const severity = getString(card.severity);
        const category = getString(card.category);
        return [severity, category].filter(Boolean).join(' / ') || null;
    }
    if (card.type === 'artifact') {
        return [getString(card.artifactKind), getString(card.generatedByTool)]
            .filter(Boolean)
            .join(' / ') || null;
    }
    return null;
}
function getCardActionDescriptors(card) {
    const ordered = new Map();
    ordered.set('pin', {
        id: 'pin',
        label: card.pinned ? 'Pinned' : 'Pin',
    });
    for (const action of getStringArray(card.quickActions)) {
        if (action === 'export_report') {
            ordered.set(action, { id: action, label: 'Export' });
        }
        if (action === 'compare_run') {
            ordered.set(action, { id: action, label: 'Compare' });
        }
        if (action === 'rerun') {
            ordered.set(action, { id: action, label: 'Re-run' });
        }
        if (action === 'request_review') {
            ordered.set(action, { id: action, label: 'Request review' });
        }
    }
    if (card.type === 'artifact' && getString(card.fileRef)) {
        ordered.set('open_artifact', {
            id: 'open_artifact',
            label: 'Open artifact',
        });
    }
    return [...ordered.values()];
}
function getSeverityTone(value) {
    const severity = getString(value);
    if (severity === 'high') {
        return {
            badgeClassName: 'border-rose-400/30 bg-rose-400/10 text-rose-200',
            panelClassName: 'border-rose-400/20 bg-rose-400/5 text-rose-100',
        };
    }
    if (severity === 'medium') {
        return {
            badgeClassName: 'border-amber-400/30 bg-amber-400/10 text-amber-200',
            panelClassName: 'border-amber-400/20 bg-amber-400/5 text-amber-100',
        };
    }
    if (severity === 'low') {
        return {
            badgeClassName: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200',
            panelClassName: 'border-emerald-400/20 bg-emerald-400/5 text-emerald-100',
        };
    }
    return DEFAULT_TONE;
}
