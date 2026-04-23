"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.isHarnessWarningLearningItem = isHarnessWarningLearningItem;
exports.normalizeLearningInboxItem = normalizeLearningInboxItem;
exports.normalizeLearningItemDetail = normalizeLearningItemDetail;
exports.normalizeLearningGovernanceStatus = normalizeLearningGovernanceStatus;
exports.extractHarnessWarningReviewSummary = extractHarnessWarningReviewSummary;
exports.extractFailureTaxonomyCandidateSummary = extractFailureTaxonomyCandidateSummary;
const HARNESS_WARNING_TAG = 'harness.warning';
const HARNESS_WARNING_TITLE_PREFIX = 'Harness warning: ';
const WARNING_CONTENT_SUGGESTION_MARKER = '\n\nSuggestion: ';
function asRecord(value) {
    return value && typeof value === 'object' && !Array.isArray(value)
        ? value
        : null;
}
function readString(value) {
    return typeof value === 'string' && value.trim().length > 0 ? value.trim() : null;
}
function readStringArray(value) {
    if (!Array.isArray(value)) {
        return [];
    }
    return value
        .filter((entry) => typeof entry === 'string')
        .map((entry) => entry.trim())
        .filter((entry) => entry.length > 0);
}
function readNumber(value) {
    return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}
function readNullableNumber(value) {
    return typeof value === 'number' && Number.isFinite(value) ? value : null;
}
function readBoolean(value) {
    return typeof value === 'boolean' ? value : null;
}
function readSeverity(value) {
    const normalized = readString(value)?.toLowerCase();
    if (normalized === 'high' || normalized === 'medium' || normalized === 'low') {
        return normalized;
    }
    return null;
}
function readPositiveInteger(value) {
    if (typeof value !== 'number' || !Number.isFinite(value)) {
        return null;
    }
    const normalized = Math.trunc(value);
    return normalized > 0 ? normalized : null;
}
function readTagValue(tags, prefix) {
    const match = tags.find((tag) => tag.startsWith(prefix));
    if (!match) {
        return null;
    }
    const value = match.slice(prefix.length).trim();
    return value.length > 0 ? value : null;
}
function inferWarningTypeFromTitle(title) {
    if (!title || !title.startsWith(HARNESS_WARNING_TITLE_PREFIX)) {
        return null;
    }
    const value = title.slice(HARNESS_WARNING_TITLE_PREFIX.length).trim();
    return value.length > 0 ? value : null;
}
function inferWarningTypeFromTags(tags) {
    const warningType = tags.find((tag) => tag !== HARNESS_WARNING_TAG &&
        !tag.startsWith('severity:') &&
        !tag.startsWith('surface:') &&
        !tag.startsWith('taxonomy:'));
    return warningType ?? null;
}
function mergeUniqueStrings(...values) {
    const merged = [];
    const seen = new Set();
    values.flat().forEach((value) => {
        const normalized = readString(value);
        if (!normalized) {
            return;
        }
        const key = normalized.toLowerCase();
        if (seen.has(key)) {
            return;
        }
        seen.add(key);
        merged.push(normalized);
    });
    return merged;
}
function parseHarnessWarningContent(content) {
    const normalized = readString(content);
    if (!normalized) {
        return { message: null, suggestion: null };
    }
    const markerIndex = normalized.indexOf(WARNING_CONTENT_SUGGESTION_MARKER);
    if (markerIndex === -1) {
        return { message: normalized, suggestion: null };
    }
    const message = normalized.slice(0, markerIndex).trim();
    const suggestion = normalized
        .slice(markerIndex + WARNING_CONTENT_SUGGESTION_MARKER.length)
        .trim();
    return {
        message: message.length > 0 ? message : null,
        suggestion: suggestion.length > 0 ? suggestion : null,
    };
}
function isHarnessWarningLearningItem(item) {
    return item.type === 'pattern' && item.tags.includes(HARNESS_WARNING_TAG);
}
function extractProvenanceFields(metadata) {
    if (!metadata) {
        return {};
    }
    const result = {};
    const failureSourceKind = readString(metadata.failureSourceKind);
    if (failureSourceKind !== null) {
        result.failureSourceKind = failureSourceKind;
    }
    const failureSignalType = readString(metadata.failureSignalType);
    if (failureSignalType !== null) {
        result.failureSignalType = failureSignalType;
    }
    const sourceKinds = readStringArray(metadata.sourceKinds);
    if (sourceKinds.length > 0) {
        result.sourceKinds = sourceKinds;
    }
    const sessionIds = readStringArray(metadata.sessionIds);
    if (sessionIds.length > 0) {
        result.sessionIds = sessionIds;
    }
    const runIds = readStringArray(metadata.runIds);
    if (runIds.length > 0) {
        result.runIds = runIds;
    }
    return result;
}
/**
 * Normalize a raw backend inbox item payload into a typed LearningItemView,
 * extracting provenance fields from the metadata object.
 */
function normalizeLearningInboxItem(raw) {
    const record = asRecord(raw);
    if (record === null) {
        return null;
    }
    const item_id = readString(record.item_id);
    if (item_id === null) {
        return null;
    }
    const tags = readStringArray(record.tags);
    const metadata = asRecord(record.metadata) ?? undefined;
    const priorityScore = readNumber(record.priority_score);
    const evidenceCount = readNumber(record.evidence_count);
    const conflictCount = readNumber(record.conflict_count);
    return {
        item_id,
        type: readString(record.type) ?? 'pattern',
        status: readString(record.status) ?? 'proposed',
        title: readString(record.title) ?? '',
        priority_score: priorityScore ?? 0,
        evidence_count: evidenceCount ?? 0,
        conflict_count: conflictCount ?? 0,
        scope: readString(record.scope) ?? 'project',
        tags,
        created_at: readString(record.created_at) ?? '',
        metadata,
        ...extractProvenanceFields(metadata),
    };
}
function normalizeLearningItemDetail(baseItem, payload) {
    const record = asRecord(payload);
    if (record === null) {
        return { ...baseItem };
    }
    const tags = readStringArray(record.tags);
    const metadata = asRecord(record.metadata) ?? baseItem.metadata;
    return {
        item_id: readString(record.item_id) ?? baseItem.item_id,
        type: readString(record.type) ?? baseItem.type,
        status: readString(record.status) ?? baseItem.status,
        title: readString(record.title) ?? baseItem.title,
        priority_score: readNumber(record.priority_score) ?? baseItem.priority_score,
        evidence_count: readNumber(record.evidence_count) ?? baseItem.evidence_count,
        conflict_count: readNumber(record.conflict_count) ?? baseItem.conflict_count,
        scope: readString(record.scope) ?? baseItem.scope,
        tags: tags.length > 0 ? tags : baseItem.tags,
        created_at: readString(record.created_at) ?? baseItem.created_at,
        metadata,
        ...extractProvenanceFields(metadata),
        content: readString(record.content) ?? undefined,
        review_count: readNumber(record.review_count),
        updated_at: readString(record.updated_at) ?? undefined,
    };
}
function normalizeLearningGovernanceStatus(payload) {
    const record = asRecord(payload);
    const standingOrderRecord = asRecord(record?.standingOrder);
    const backlogRecord = asRecord(record?.backlog);
    const latestCompletedRecord = asRecord(record?.latestCompletedRun);
    const latestReportRecord = asRecord(record?.latestReport);
    const recentHistory = Array.isArray(record?.recentHistory) ? record.recentHistory : [];
    return {
        reviewEnabled: readBoolean(record?.reviewEnabled) ?? false,
        standingOrder: standingOrderRecord === null
            ? null
            : {
                orderId: readString(standingOrderRecord.orderId) ?? '',
                name: readString(standingOrderRecord.name) ?? '',
                enabled: readBoolean(standingOrderRecord.enabled) ?? false,
                cron: readString(standingOrderRecord.cron),
                timezone: readString(standingOrderRecord.timezone),
                nextRunAt: readString(standingOrderRecord.nextRunAt),
                lastRunAt: readString(standingOrderRecord.lastRunAt),
                runCount: readPositiveInteger(standingOrderRecord.runCount) ?? 0,
                failureCount: readNumber(standingOrderRecord.failureCount) ?? 0,
            },
        backlog: {
            activeWarningItems: readPositiveInteger(backlogRecord?.activeWarningItems) ?? 0,
            activeWarningRecurrences: readPositiveInteger(backlogRecord?.activeWarningRecurrences) ?? 0,
            promotionCandidateItems: readPositiveInteger(backlogRecord?.promotionCandidateItems) ?? 0,
            promotionCandidateClasses: readStringArray(backlogRecord?.promotionCandidateClasses),
            warningTypes: readStringArray(backlogRecord?.warningTypes),
            surfaces: readStringArray(backlogRecord?.surfaces),
            lastGcAt: readString(backlogRecord?.lastGcAt),
        },
        latestCompletedRun: normalizeLearningGovernanceHistory(latestCompletedRecord),
        latestReport: latestReportRecord === null
            ? null
            : {
                path: readString(latestReportRecord.path) ?? '',
                name: readString(latestReportRecord.name) ?? '',
            },
        recentHistory: recentHistory
            .map((entry) => normalizeLearningGovernanceHistory(asRecord(entry)))
            .filter((entry) => entry !== null),
    };
}
function normalizeLearningGovernanceHistory(record) {
    if (record === null) {
        return null;
    }
    return {
        status: readString(record.status) ?? '',
        summary: readString(record.summary) ?? '',
        recordedAt: readString(record.recordedAt),
        reportPath: readString(record.reportPath),
        totalItems: readNullableNumber(record.totalItems),
        totalRecurrences: readNullableNumber(record.totalRecurrences),
        promotionThreshold: readNullableNumber(record.promotionThreshold),
        promotionCandidateClasses: readStringArray(record.promotionCandidateClasses),
    };
}
function extractHarnessWarningReviewSummary(item) {
    if (!isHarnessWarningLearningItem(item)) {
        return null;
    }
    const metadata = asRecord(item.metadata);
    const rawPayload = asRecord(metadata?.rawPayload);
    const parsedContent = parseHarnessWarningContent(item.content);
    const surface = readString(metadata?.surface) ?? readTagValue(item.tags, 'surface:');
    const surfaces = mergeUniqueStrings(readStringArray(metadata?.surfaces), [surface]);
    return {
        warningType: readString(metadata?.warningType) ??
            inferWarningTypeFromTitle(readString(item.title)) ??
            inferWarningTypeFromTags(item.tags) ??
            'unknown',
        severity: readSeverity(metadata?.severity) ??
            readSeverity(readTagValue(item.tags, 'severity:')) ??
            'medium',
        surface,
        surfaces,
        sessionId: readString(metadata?.sessionId),
        runId: readString(metadata?.runId),
        message: parsedContent.message ?? readString(rawPayload?.message),
        suggestion: parsedContent.suggestion ?? readString(rawPayload?.suggestion),
        recurrenceCount: readPositiveInteger(metadata?.recurrenceCount) ??
            readPositiveInteger(metadata?.failureTaxonomyRecurrenceCount) ??
            1,
        taxonomyClass: readString(metadata?.failureTaxonomyClass),
        promotionCandidate: readBoolean(metadata?.failureTaxonomyPromotionCandidate) ?? false,
        firstSeenAt: readString(metadata?.firstSeenAt),
        lastSeenAt: readString(metadata?.lastSeenAt),
        rawPayload,
    };
}
function extractFailureTaxonomyCandidateSummary(item) {
    const metadata = asRecord(item.metadata);
    if (metadata === null) {
        return null;
    }
    const candidateId = readString(metadata.failureTaxonomyCandidateId);
    const status = readString(metadata.failureTaxonomyCandidateStatus);
    const pendingPath = readString(metadata.failureTaxonomyCandidatePath);
    const promotedPath = readString(metadata.promotedPath);
    const promotionCandidate = readBoolean(metadata.failureTaxonomyPromotionCandidate) ?? false;
    if (!candidateId && !status && !promotionCandidate) {
        return null;
    }
    return {
        candidateId,
        status,
        pendingPath,
        promotedPath,
        promotionCandidate,
    };
}
