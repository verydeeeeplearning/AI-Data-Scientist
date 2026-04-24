"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.buildRecoveryTaskContractDraft = buildRecoveryTaskContractDraft;
exports.CreateContractModal = CreateContractModal;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const useCaseMapping_1 = require("../../../shared/useCaseMapping");
const recoveryTaskContractDefaults_1 = require("../../application/onboarding/recoveryTaskContractDefaults");
const i18nStore_1 = require("../../stores/i18nStore");
function getUseCaseLabel(useCaseId, t) {
    const key = {
        data_analysis: 'onboarding.use_case.option.data_analysis.title',
        reporting: 'onboarding.use_case.option.reporting.title',
        prediction: 'onboarding.use_case.option.prediction.title',
        dashboard: 'onboarding.use_case.option.dashboard.title',
        sql_exploration: 'onboarding.use_case.option.sql_exploration.title',
        weekly_kpi_triage: 'onboarding.use_case.option.weekly_kpi_triage.title',
        ab_test_analysis: 'onboarding.use_case.option.ab_test_analysis.title',
        general: 'onboarding.use_case.option.general.title',
    }[useCaseId];
    return t(key);
}
function buildRecoveryTaskContractDraft(args) {
    const businessGoal = args.businessGoal.trim();
    const { useCaseSpec, goalBriefTemplate } = (0, recoveryTaskContractDefaults_1.resolveRecoveryTaskContractDefaults)(args.useCaseId);
    return {
        session_id: args.sessionId.trim(),
        contract_type: useCaseSpec.contractType,
        business_goal: businessGoal,
        goal_brief: {
            business_question: businessGoal,
            ds_problem_statement: goalBriefTemplate.ds_problem_statement,
            comparison_baseline: goalBriefTemplate.comparison_baseline,
            decision_to_make: goalBriefTemplate.decision_to_make,
            hypothesis: null,
            expected_effort: goalBriefTemplate.expected_effort,
        },
        required_deliverables: useCaseSpec.defaultDeliverableSpecs.map((item) => ({ ...item })),
        allowed_data_sources: [],
        forbidden_data_patterns: [],
        budget: {},
        autonomy: {},
        authority: useCaseSpec.defaultAuthority,
        audience: useCaseSpec.defaultAudience,
        mission: useCaseSpec.defaultMission,
        created_by: 'user',
    };
}
function CreateContractModal({ open, sessionId, initialBusinessGoal = '', saving, onClose, onSubmit, }) {
    const { t } = (0, i18nStore_1.useI18n)();
    const [useCaseId, setUseCaseId] = (0, react_1.useState)(useCaseMapping_1.DEFAULT_USE_CASE_ID);
    const [businessGoal, setBusinessGoal] = (0, react_1.useState)('');
    const [validationError, setValidationError] = (0, react_1.useState)(null);
    (0, react_1.useEffect)(() => {
        if (!open) {
            return;
        }
        setUseCaseId(useCaseMapping_1.DEFAULT_USE_CASE_ID);
        setBusinessGoal(initialBusinessGoal.trim());
        setValidationError(null);
    }, [initialBusinessGoal, open, sessionId]);
    const recoveryDefaults = (0, react_1.useMemo)(() => (0, recoveryTaskContractDefaults_1.resolveRecoveryTaskContractDefaults)(useCaseId), [useCaseId]);
    const useCaseSpec = recoveryDefaults.useCaseSpec;
    if (!open) {
        return null;
    }
    return ((0, jsx_runtime_1.jsx)("div", { className: "fixed inset-0 z-40 flex items-center justify-center bg-black/50 px-4", children: (0, jsx_runtime_1.jsxs)("div", { role: "dialog", "aria-modal": "true", "aria-labelledby": "mission-brief-create-title", "aria-describedby": "mission-brief-create-description", className: "w-full max-w-2xl rounded-2xl border border-ds-border bg-ds-surface shadow-2xl", "data-testid": "mission-brief-create-contract-dialog", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-center justify-between border-b border-ds-border px-5 py-4", children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("h2", { id: "mission-brief-create-title", className: "text-base font-semibold text-ds-text", children: t('mission.brief.create.title') }), (0, jsx_runtime_1.jsx)("p", { id: "mission-brief-create-description", className: "mt-1 text-xs text-ds-muted", children: t('mission.brief.create.description') })] }), (0, jsx_runtime_1.jsx)("button", { type: "button", onClick: onClose, disabled: saving, className: "rounded-lg border border-ds-border px-3 py-1.5 text-xs text-ds-muted hover:border-ds-accent hover:text-ds-text disabled:opacity-60", children: t('mission.brief.create.cancel') })] }), (0, jsx_runtime_1.jsxs)("form", { onSubmit: (event) => {
                        event.preventDefault();
                        const normalizedGoal = businessGoal.trim();
                        if (!normalizedGoal) {
                            setValidationError(t('mission.brief.create.goal_required'));
                            return;
                        }
                        setValidationError(null);
                        void onSubmit(buildRecoveryTaskContractDraft({
                            sessionId,
                            useCaseId,
                            businessGoal: normalizedGoal,
                        }));
                    }, children: [(0, jsx_runtime_1.jsxs)("div", { className: "grid gap-4 p-5", children: [(0, jsx_runtime_1.jsxs)("div", { className: "rounded-xl border border-ds-border bg-ds-bg/50 px-3 py-2 text-[11px] text-ds-muted", children: [t('mission.header.session'), ": ", (0, jsx_runtime_1.jsx)("span", { className: "font-mono text-ds-text", children: sessionId })] }), (0, jsx_runtime_1.jsxs)("label", { className: "grid gap-2 text-xs text-ds-muted", children: [t('mission.brief.create.use_case'), (0, jsx_runtime_1.jsx)("select", { value: useCaseId, onChange: (event) => setUseCaseId(event.target.value), "data-testid": "mission-brief-create-contract-use-case", className: "rounded-xl border border-ds-border bg-ds-bg px-3 py-2 text-sm text-ds-text outline-none focus:border-ds-accent", children: useCaseMapping_1.ONBOARDING_USE_CASE_IDS.map((value) => ((0, jsx_runtime_1.jsx)("option", { value: value, children: getUseCaseLabel(value, t) || recoveryTaskContractDefaults_1.RECOVERY_TASK_CONTRACT_USE_CASE_LABELS[value] }, value))) })] }), (0, jsx_runtime_1.jsxs)("label", { className: "grid gap-2 text-xs text-ds-muted", children: [t('mission.brief.create.business_goal'), (0, jsx_runtime_1.jsx)("textarea", { value: businessGoal, onChange: (event) => setBusinessGoal(event.target.value), rows: 4, "data-testid": "mission-brief-create-contract-business-goal", placeholder: t('mission.brief.create.goal_placeholder'), className: "rounded-xl border border-ds-border bg-ds-bg px-3 py-2 text-sm text-ds-text outline-none focus:border-ds-accent" })] }), (0, jsx_runtime_1.jsxs)("div", { className: "rounded-xl border border-ds-border bg-ds-bg/60 px-4 py-3", children: [(0, jsx_runtime_1.jsx)("p", { className: "text-[11px] uppercase tracking-wide text-ds-muted", children: t('mission.brief.create.defaults.title') }), (0, jsx_runtime_1.jsxs)("div", { className: "mt-2 flex flex-wrap gap-2 text-[11px]", children: [(0, jsx_runtime_1.jsx)("span", { className: "rounded-full border border-ds-border bg-ds-surface px-2 py-1 text-ds-text", children: t('mission.brief.create.defaults.contract_type', {
                                                        value: useCaseSpec.contractType,
                                                    }) }), (0, jsx_runtime_1.jsx)("span", { className: "rounded-full border border-ds-border bg-ds-surface px-2 py-1 text-ds-text", children: t('mission.brief.labels.authority', {
                                                        value: useCaseSpec.defaultAuthority,
                                                    }) }), (0, jsx_runtime_1.jsx)("span", { className: "rounded-full border border-ds-border bg-ds-surface px-2 py-1 text-ds-text", children: t('mission.brief.labels.audience', {
                                                        value: useCaseSpec.defaultAudience,
                                                    }) })] }), (0, jsx_runtime_1.jsx)("div", { className: "mt-3 grid gap-2", children: useCaseSpec.defaultDeliverableSpecs.map((item) => ((0, jsx_runtime_1.jsxs)("div", { className: "rounded-lg border border-ds-border bg-ds-surface px-3 py-2 text-[11px] text-ds-muted", children: [(0, jsx_runtime_1.jsx)("span", { className: "font-medium text-ds-text", children: item.type }), ` -> ${item.audience} (${item.format})`] }, `${item.type}-${item.audience}-${item.format}`))) })] }), validationError && ((0, jsx_runtime_1.jsx)("div", { className: "rounded-xl border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200", children: validationError }))] }), (0, jsx_runtime_1.jsx)("div", { className: "flex items-center justify-end border-t border-ds-border px-5 py-4", children: (0, jsx_runtime_1.jsx)("button", { type: "submit", disabled: saving, "data-testid": "mission-brief-create-contract-submit", className: "rounded-xl bg-ds-accent px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60", children: saving ? t('mission.brief.create.drafting') : t('mission.brief.create.submit') }) })] })] }) }));
}
