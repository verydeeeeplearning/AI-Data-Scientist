"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.EMPTY_LEARNING_GOVERNANCE_STATUS = exports.EMPTY_LEARNING_INBOX = exports.normalizeLearningItemDetail = exports.normalizeLearningInboxItem = exports.normalizeLearningGovernanceStatus = exports.isHarnessWarningLearningItem = exports.extractHarnessWarningReviewSummary = exports.extractFailureTaxonomyCandidateSummary = void 0;
exports.readLearningGovernanceEnabled = readLearningGovernanceEnabled;
exports.createLearningClient = createLearningClient;
exports.useLearning = useLearning;
const react_1 = require("react");
const learning_1 = require("../types/learning");
const WsProvider_1 = require("./WsProvider");
var learning_2 = require("../types/learning");
Object.defineProperty(exports, "extractFailureTaxonomyCandidateSummary", { enumerable: true, get: function () { return learning_2.extractFailureTaxonomyCandidateSummary; } });
Object.defineProperty(exports, "extractHarnessWarningReviewSummary", { enumerable: true, get: function () { return learning_2.extractHarnessWarningReviewSummary; } });
Object.defineProperty(exports, "isHarnessWarningLearningItem", { enumerable: true, get: function () { return learning_2.isHarnessWarningLearningItem; } });
Object.defineProperty(exports, "normalizeLearningGovernanceStatus", { enumerable: true, get: function () { return learning_2.normalizeLearningGovernanceStatus; } });
Object.defineProperty(exports, "normalizeLearningInboxItem", { enumerable: true, get: function () { return learning_2.normalizeLearningInboxItem; } });
Object.defineProperty(exports, "normalizeLearningItemDetail", { enumerable: true, get: function () { return learning_2.normalizeLearningItemDetail; } });
exports.EMPTY_LEARNING_INBOX = { items: [], total: 0 };
exports.EMPTY_LEARNING_GOVERNANCE_STATUS = {
    reviewEnabled: false,
    standingOrder: null,
    backlog: {
        activeWarningItems: 0,
        activeWarningRecurrences: 0,
        promotionCandidateItems: 0,
        promotionCandidateClasses: [],
        warningTypes: [],
        surfaces: [],
        lastGcAt: null,
    },
    latestCompletedRun: null,
    latestReport: null,
    recentHistory: [],
};
function readLearningGovernanceEnabled(payload) {
    if (!payload || typeof payload !== 'object') {
        return false;
    }
    const featureFlags = payload.featureFlags;
    if (!featureFlags || typeof featureFlags !== 'object') {
        return false;
    }
    const rawValue = featureFlags.selfImproveGovernanceV1;
    if (typeof rawValue === 'boolean') {
        return rawValue;
    }
    if (typeof rawValue === 'string') {
        return ['1', 'true', 'yes'].includes(rawValue.trim().toLowerCase());
    }
    return false;
}
function createLearningClient(rpc) {
    let enabledPromise = null;
    const getEnabled = async () => {
        if (enabledPromise === null) {
            enabledPromise = rpc('config.get').then((result) => readLearningGovernanceEnabled(result));
        }
        return enabledPromise;
    };
    return {
        getEnabled,
        async fetchStatus() {
            const enabled = await getEnabled();
            const result = await rpc('learning.status', { historyLimit: 5 });
            return {
                enabled,
                status: (0, learning_1.normalizeLearningGovernanceStatus)({
                    ...result,
                    reviewEnabled: result.reviewEnabled ?? enabled,
                }),
            };
        },
        async fetchInbox(status = 'proposed', itemType = 'all') {
            const enabled = await getEnabled();
            const result = await rpc('learning.inbox', { status, itemType, limit: 30 });
            const rawItems = Array.isArray(result.items) ? result.items : [];
            const items = rawItems
                .map((raw) => (0, learning_1.normalizeLearningInboxItem)(raw))
                .filter((item) => item !== null);
            const total = typeof result.total === 'number' ? result.total : items.length;
            return {
                enabled,
                inbox: { items, total },
            };
        },
        async fetchItemDetail(item) {
            const enabled = await getEnabled();
            const result = await rpc('learning.getItem', { itemId: item.item_id });
            return {
                enabled,
                item: (0, learning_1.normalizeLearningItemDetail)(item, result),
            };
        },
        async reviewItem(itemId, decision, comment = '') {
            if (!(await getEnabled())) {
                return false;
            }
            await rpc('learning.review', { itemId, decision, comment });
            return true;
        },
        async finalizeCandidatePromotion(params) {
            if (!(await getEnabled())) {
                return null;
            }
            const result = await rpc('learning.finalizePromotion', params);
            return result;
        },
    };
}
function useLearning() {
    const { rpc } = (0, WsProvider_1.useWs)();
    const [enabled, setEnabled] = (0, react_1.useState)(false);
    const [inbox, setInbox] = (0, react_1.useState)(exports.EMPTY_LEARNING_INBOX);
    const [status, setStatus] = (0, react_1.useState)(exports.EMPTY_LEARNING_GOVERNANCE_STATUS);
    const [loading, setLoading] = (0, react_1.useState)(false);
    const [error, setError] = (0, react_1.useState)(null);
    const refreshInbox = (0, react_1.useCallback)(async (status = 'proposed', itemType = 'all') => {
        setLoading(true);
        setError(null);
        try {
            const client = createLearningClient(rpc);
            const nextStatus = await client.fetchStatus();
            const result = await client.fetchInbox(status, itemType);
            setEnabled(result.enabled);
            setStatus(nextStatus.status);
            setInbox(result.inbox);
        }
        catch (err) {
            setError(err instanceof Error ? err.message : String(err));
        }
        finally {
            setLoading(false);
        }
    }, [rpc]);
    const fetchItemDetail = (0, react_1.useCallback)(async (item) => {
        const client = createLearningClient(rpc);
        const result = await client.fetchItemDetail(item);
        setEnabled(result.enabled);
        return result.item;
    }, [rpc]);
    const reviewItem = (0, react_1.useCallback)(async (itemId, decision, comment = '') => {
        const client = createLearningClient(rpc);
        const nextEnabled = await client.reviewItem(itemId, decision, comment);
        setEnabled(nextEnabled);
        if (!nextEnabled) {
            return;
        }
        await refreshInbox();
    }, [rpc, refreshInbox]);
    const finalizeCandidatePromotion = (0, react_1.useCallback)(async (params) => {
        const client = createLearningClient(rpc);
        const result = await client.finalizeCandidatePromotion(params);
        setEnabled(Boolean(result));
        if (!result) {
            return null;
        }
        await refreshInbox();
        return result;
    }, [rpc, refreshInbox]);
    return {
        enabled,
        status,
        inbox,
        loading,
        error,
        refreshInbox,
        fetchItemDetail,
        reviewItem,
        finalizeCandidatePromotion,
    };
}
