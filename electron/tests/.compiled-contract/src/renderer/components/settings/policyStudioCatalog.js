"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MATRIX_VERDICT_OPTIONS = exports.MATRIX_AUTHORITY_COLUMNS = exports.POLICY_RISK_TIER_DEFINITIONS = exports.POLICY_STUDIO_PRESETS = exports.AUDIENCE_PREVIEWS = exports.AUDIENCE_OPTIONS = exports.EFFECTIVE_AUTHORITY_CARDS = exports.CONTRACT_AUTHORITY_OPTIONS = void 0;
exports.isContractAuthorityDraft = isContractAuthorityDraft;
exports.isAudienceDraft = isAudienceDraft;
exports.isEffectiveAuthorityMode = isEffectiveAuthorityMode;
exports.formatAuthorityLabel = formatAuthorityLabel;
exports.formatAudienceLabel = formatAudienceLabel;
exports.formatMatrixVerdictLabel = formatMatrixVerdictLabel;
exports.derivePolicyRiskTier = derivePolicyRiskTier;
exports.isLegacyMode = isLegacyMode;
exports.buildLegacyModeMigrationPreview = buildLegacyModeMigrationPreview;
exports.CONTRACT_AUTHORITY_OPTIONS = [
    {
        value: 'inherit',
        label: 'settings.policyStudio.contractAuthority.inherit.label',
        summary: 'settings.policyStudio.contractAuthority.inherit.summary',
    },
    {
        value: 'shadow',
        label: 'settings.policyStudio.contractAuthority.shadow.label',
        summary: 'settings.policyStudio.contractAuthority.shadow.summary',
    },
    {
        value: 'supervised',
        label: 'settings.policyStudio.contractAuthority.supervised.label',
        summary: 'settings.policyStudio.contractAuthority.supervised.summary',
    },
    {
        value: 'delegate',
        label: 'settings.policyStudio.contractAuthority.delegate.label',
        summary: 'settings.policyStudio.contractAuthority.delegate.summary',
    },
    {
        value: 'autopilot',
        label: 'settings.policyStudio.contractAuthority.autopilot.label',
        summary: 'settings.policyStudio.contractAuthority.autopilot.summary',
    },
];
exports.EFFECTIVE_AUTHORITY_CARDS = [
    {
        value: 'shadow',
        label: 'settings.policyStudio.effectiveAuthority.shadow.label',
        summary: 'settings.policyStudio.effectiveAuthority.shadow.summary',
    },
    {
        value: 'supervised',
        label: 'settings.policyStudio.effectiveAuthority.supervised.label',
        summary: 'settings.policyStudio.effectiveAuthority.supervised.summary',
    },
    {
        value: 'delegate',
        label: 'settings.policyStudio.effectiveAuthority.delegate.label',
        summary: 'settings.policyStudio.effectiveAuthority.delegate.summary',
    },
    {
        value: 'autopilot',
        label: 'settings.policyStudio.effectiveAuthority.autopilot.label',
        summary: 'settings.policyStudio.effectiveAuthority.autopilot.summary',
    },
    {
        value: 'incident',
        label: 'settings.policyStudio.effectiveAuthority.incident.label',
        summary: 'settings.policyStudio.effectiveAuthority.incident.summary',
    },
    {
        value: 'freeze',
        label: 'settings.policyStudio.effectiveAuthority.freeze.label',
        summary: 'settings.policyStudio.effectiveAuthority.freeze.summary',
    },
];
exports.AUDIENCE_OPTIONS = [
    { value: 'inherit', label: 'settings.policyStudio.audience.inherit' },
    { value: 'junior_mentor', label: 'settings.policyStudio.audience.juniorMentor' },
    { value: 'peer_ds', label: 'settings.policyStudio.audience.peerDs' },
    { value: 'senior_staff', label: 'settings.policyStudio.audience.seniorStaff' },
    { value: 'executive', label: 'settings.policyStudio.audience.executive' },
    { value: 'auditor', label: 'settings.policyStudio.audience.auditor' },
];
exports.AUDIENCE_PREVIEWS = {
    junior_mentor: {
        label: 'settings.policyStudio.audience.juniorMentor',
        tone: 'settings.policyStudio.audiencePreview.juniorMentor.tone',
        depth: 'settings.policyStudio.audiencePreview.juniorMentor.depth',
        uncertaintyStyle: 'settings.policyStudio.audiencePreview.juniorMentor.uncertaintyStyle',
        defaultArtifacts: ['checklist', 'annotated_notes', 'commented_code'],
        sample: [
            'settings.policyStudio.audiencePreview.juniorMentor.sample1',
            'settings.policyStudio.audiencePreview.juniorMentor.sample2',
            'settings.policyStudio.audiencePreview.juniorMentor.sample3',
        ],
    },
    peer_ds: {
        label: 'settings.policyStudio.audience.peerDs',
        tone: 'settings.policyStudio.audiencePreview.peerDs.tone',
        depth: 'settings.policyStudio.audiencePreview.peerDs.depth',
        uncertaintyStyle: 'settings.policyStudio.audiencePreview.peerDs.uncertaintyStyle',
        defaultArtifacts: ['reproducible_notebook', 'sql', 'analysis_appendix'],
        sample: [
            'settings.policyStudio.audiencePreview.peerDs.sample1',
            'settings.policyStudio.audiencePreview.peerDs.sample2',
            'settings.policyStudio.audiencePreview.peerDs.sample3',
        ],
    },
    senior_staff: {
        label: 'settings.policyStudio.audience.seniorStaff',
        tone: 'settings.policyStudio.audiencePreview.seniorStaff.tone',
        depth: 'settings.policyStudio.audiencePreview.seniorStaff.depth',
        uncertaintyStyle: 'settings.policyStudio.audiencePreview.seniorStaff.uncertaintyStyle',
        defaultArtifacts: ['decision_memo', 'diff', 'risk_summary'],
        sample: [
            'settings.policyStudio.audiencePreview.seniorStaff.sample1',
            'settings.policyStudio.audiencePreview.seniorStaff.sample2',
            'settings.policyStudio.audiencePreview.seniorStaff.sample3',
        ],
    },
    executive: {
        label: 'settings.policyStudio.audience.executive',
        tone: 'settings.policyStudio.audiencePreview.executive.tone',
        depth: 'settings.policyStudio.audiencePreview.executive.depth',
        uncertaintyStyle: 'settings.policyStudio.audiencePreview.executive.uncertaintyStyle',
        defaultArtifacts: ['exec_brief', 'action_card'],
        sample: [
            'settings.policyStudio.audiencePreview.executive.sample1',
            'settings.policyStudio.audiencePreview.executive.sample2',
            'settings.policyStudio.audiencePreview.executive.sample3',
        ],
    },
    auditor: {
        label: 'settings.policyStudio.audience.auditor',
        tone: 'settings.policyStudio.audiencePreview.auditor.tone',
        depth: 'settings.policyStudio.audiencePreview.auditor.depth',
        uncertaintyStyle: 'settings.policyStudio.audiencePreview.auditor.uncertaintyStyle',
        defaultArtifacts: ['audit_trail', 'lineage_report', 'approval_history'],
        sample: [
            'settings.policyStudio.audiencePreview.auditor.sample1',
            'settings.policyStudio.audiencePreview.auditor.sample2',
            'settings.policyStudio.audiencePreview.auditor.sample3',
        ],
    },
};
exports.POLICY_STUDIO_PRESETS = [
    {
        id: 'delegate-peer',
        label: 'settings.policyStudio.preset.delegatePeer.label',
        authority: 'delegate',
        audience: 'peer_ds',
        summary: 'settings.policyStudio.preset.delegatePeer.summary',
    },
    {
        id: 'executive-review',
        label: 'settings.policyStudio.preset.executiveReview.label',
        authority: 'supervised',
        audience: 'executive',
        summary: 'settings.policyStudio.preset.executiveReview.summary',
    },
    {
        id: 'audit-guard',
        label: 'settings.policyStudio.preset.auditGuard.label',
        authority: 'supervised',
        audience: 'auditor',
        summary: 'settings.policyStudio.preset.auditGuard.summary',
    },
    {
        id: 'mentor-walkthrough',
        label: 'settings.policyStudio.preset.mentorWalkthrough.label',
        authority: 'supervised',
        audience: 'junior_mentor',
        summary: 'settings.policyStudio.preset.mentorWalkthrough.summary',
    },
];
exports.POLICY_RISK_TIER_DEFINITIONS = [
    {
        value: 'routine',
        label: 'settings.policyStudio.riskTierDef.routine.label',
        summary: 'settings.policyStudio.riskTierDef.routine.summary',
    },
    {
        value: 'guarded',
        label: 'settings.policyStudio.riskTierDef.guarded.label',
        summary: 'settings.policyStudio.riskTierDef.guarded.summary',
    },
    {
        value: 'sensitive',
        label: 'settings.policyStudio.riskTierDef.sensitive.label',
        summary: 'settings.policyStudio.riskTierDef.sensitive.summary',
    },
    {
        value: 'critical',
        label: 'settings.policyStudio.riskTierDef.critical.label',
        summary: 'settings.policyStudio.riskTierDef.critical.summary',
    },
];
const AUTHORITY_LABEL_KEYS = {
    shadow: 'settings.policyStudio.effectiveAuthority.shadow.label',
    supervised: 'settings.policyStudio.effectiveAuthority.supervised.label',
    delegate: 'settings.policyStudio.effectiveAuthority.delegate.label',
    autopilot: 'settings.policyStudio.effectiveAuthority.autopilot.label',
    incident: 'settings.policyStudio.effectiveAuthority.incident.label',
    freeze: 'settings.policyStudio.effectiveAuthority.freeze.label',
};
const AUDIENCE_LABEL_KEYS = {
    junior_mentor: 'settings.policyStudio.audience.juniorMentor',
    peer_ds: 'settings.policyStudio.audience.peerDs',
    senior_staff: 'settings.policyStudio.audience.seniorStaff',
    executive: 'settings.policyStudio.audience.executive',
    auditor: 'settings.policyStudio.audience.auditor',
};
exports.MATRIX_AUTHORITY_COLUMNS = [
    { value: 'shadow', label: 'settings.policyStudio.matrix.column.shadow' },
    { value: 'supervised', label: 'settings.policyStudio.matrix.column.supervised' },
    { value: 'delegate', label: 'settings.policyStudio.matrix.column.delegate' },
    { value: 'autopilot', label: 'settings.policyStudio.matrix.column.autopilot' },
    { value: 'incident', label: 'settings.policyStudio.matrix.column.incident' },
    { value: 'freeze', label: 'settings.policyStudio.matrix.column.freeze' },
];
exports.MATRIX_VERDICT_OPTIONS = [
    { value: 'auto', label: 'settings.policyStudio.matrix.verdict.auto' },
    { value: 'ask', label: 'settings.policyStudio.matrix.verdict.ask' },
    { value: 'approve', label: 'settings.policyStudio.matrix.verdict.approve' },
    { value: 'dual', label: 'settings.policyStudio.matrix.verdict.dual' },
    { value: 'skip', label: 'settings.policyStudio.matrix.verdict.skip' },
];
function isContractAuthorityDraft(value) {
    return value === 'shadow'
        || value === 'supervised'
        || value === 'delegate'
        || value === 'autopilot';
}
function isAudienceDraft(value) {
    return value === 'junior_mentor'
        || value === 'peer_ds'
        || value === 'senior_staff'
        || value === 'executive'
        || value === 'auditor';
}
function isEffectiveAuthorityMode(value) {
    return value === 'shadow'
        || value === 'supervised'
        || value === 'delegate'
        || value === 'autopilot'
        || value === 'incident'
        || value === 'freeze';
}
/**
 * Returns the i18n KEY for an authority value (or for "inherit" when null/unknown).
 * Callers must wrap with `t(...)` to render. Returning a key keeps this module
 * pure — no i18next coupling at module load time.
 */
function formatAuthorityLabel(value) {
    if (!value) {
        return 'settings.policyStudio.contractAuthority.inherit.label';
    }
    if (isEffectiveAuthorityMode(value)) {
        return AUTHORITY_LABEL_KEYS[value];
    }
    return value;
}
/**
 * Returns the i18n KEY for an audience value (or for "inherit" when null/unknown).
 * Callers must wrap with `t(...)` to render.
 */
function formatAudienceLabel(value) {
    if (!value) {
        return 'settings.policyStudio.audience.inherit';
    }
    if (isAudienceDraft(value)) {
        return AUDIENCE_LABEL_KEYS[value];
    }
    return value;
}
/**
 * Returns the i18n KEY for a matrix verdict. Callers must wrap with `t(...)`.
 */
function formatMatrixVerdictLabel(value) {
    return exports.MATRIX_VERDICT_OPTIONS.find((option) => option.value === value)?.label ?? value;
}
function derivePolicyRiskTier(row) {
    if (row.writeSideEffect === 'irreversible'
        || row.reversibility === 'irreversible') {
        return 'critical';
    }
    if (row.dataSensitivity === 'pii'
        || row.writeSideEffect === 'external'
        || row.auditRequired
        || row.costImpact === 'high') {
        return 'sensitive';
    }
    if (row.dataSensitivity === 'restricted'
        || row.writeSideEffect === 'local'
        || row.costImpact === 'medium'
        || row.reversibility === 'soft_reversible') {
        return 'guarded';
    }
    return 'routine';
}
function isLegacyMode(value) {
    return value === 'auto'
        || value === 'supervised'
        || value === 'step-by-step';
}
function buildLegacyModeMigrationPreview(value) {
    const legacyMode = isLegacyMode(value) ? value : 'auto';
    if (legacyMode === 'auto') {
        return {
            legacyMode,
            authority: 'delegate',
            audience: 'peer_ds',
            exactMatch: true,
            summary: 'settings.policyStudio.legacyMigration.auto.summary',
            notes: [
                'settings.policyStudio.legacyMigration.auto.note1',
                'settings.policyStudio.legacyMigration.auto.note2',
            ],
        };
    }
    if (legacyMode === 'supervised') {
        return {
            legacyMode,
            authority: 'supervised',
            audience: 'peer_ds',
            exactMatch: true,
            summary: 'settings.policyStudio.legacyMigration.supervised.summary',
            notes: [
                'settings.policyStudio.legacyMigration.supervised.note1',
                'settings.policyStudio.legacyMigration.supervised.note2',
            ],
        };
    }
    return {
        legacyMode,
        authority: 'supervised',
        audience: 'junior_mentor',
        exactMatch: false,
        summary: 'settings.policyStudio.legacyMigration.stepByStep.summary',
        notes: [
            'settings.policyStudio.legacyMigration.stepByStep.note1',
            'settings.policyStudio.legacyMigration.stepByStep.note2',
        ],
    };
}
