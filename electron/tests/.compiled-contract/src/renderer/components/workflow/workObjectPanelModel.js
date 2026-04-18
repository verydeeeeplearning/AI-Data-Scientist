"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.formatWorkObjectPhaseLabel = formatWorkObjectPhaseLabel;
exports.filterWorkObjectItems = filterWorkObjectItems;
exports.formatExternalReferenceLabel = formatExternalReferenceLabel;
exports.nextPhase = nextPhase;
exports.canAdvance = canAdvance;
exports.canClose = canClose;
exports.getPendingPolicyActionCount = getPendingPolicyActionCount;
function formatWorkObjectPhaseLabel(phase) {
    switch (phase) {
        case 'intake':
            return 'Intake';
        case 'executing':
            return 'Executing';
        case 'review':
            return 'Review';
        case 'documenting':
            return 'Documenting';
        case 'followup':
            return 'Follow-up';
        case 'closed':
            return 'Closed';
        case 'failed':
            return 'Failed';
    }
}
function filterWorkObjectItems(items, searchText) {
    const needle = searchText.trim().toLowerCase();
    if (!needle) {
        return items;
    }
    return items.filter((item) => item.work_object_id.toLowerCase().includes(needle)
        || item.task_contract_id.toLowerCase().includes(needle)
        || item.title.toLowerCase().includes(needle));
}
function formatExternalReferenceLabel(reference) {
    if (!reference) {
        return '-';
    }
    return `${reference.system}:${reference.resource_type}:${reference.resource_id}`;
}
const PHASE_ORDER = [
    'intake',
    'executing',
    'review',
    'documenting',
    'followup',
    'closed',
];
const TERMINAL_PHASES = new Set(['closed', 'failed']);
function nextPhase(current) {
    if (TERMINAL_PHASES.has(current)) {
        return null;
    }
    const idx = PHASE_ORDER.indexOf(current);
    if (idx < 0 || idx >= PHASE_ORDER.length - 1) {
        return null;
    }
    return PHASE_ORDER[idx + 1];
}
function canAdvance(phase) {
    return nextPhase(phase) !== null;
}
function canClose(phase) {
    return !TERMINAL_PHASES.has(phase);
}
function getPendingPolicyActionCount(metadata) {
    const pending = metadata.pending_policy_actions;
    if (!Array.isArray(pending)) {
        return 0;
    }
    return pending.filter((item) => {
        if (!item || typeof item !== 'object') {
            return false;
        }
        return item.status === 'pending';
    }).length;
}
