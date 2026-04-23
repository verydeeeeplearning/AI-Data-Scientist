"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ModelSelector = ModelSelector;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const lucide_react_1 = require("lucide-react");
const recommendModel_1 = require("../../application/llm/recommendModel");
const primitives_1 = require("../../design-system/primitives");
const modelCapability_1 = require("../../domain/llm/modelCapability");
const agentStore_1 = require("../../stores/agentStore");
const authStore_1 = require("../../stores/authStore");
const i18nStore_1 = require("../../stores/i18nStore");
const modelAuth_1 = require("../../utils/modelAuth");
const qualityPreset_1 = require("../../utils/qualityPreset");
const CapabilityBadge_1 = require("../settings/CapabilityBadge");
function statusBadgeTone(tone) {
    if (tone === 'success') {
        return 'success';
    }
    if (tone === 'warning') {
        return 'warning';
    }
    return 'neutral';
}
function ModelSelector({ onChangeModel, onChangeQualityPreset, groups }) {
    const model = (0, agentStore_1.useAgentStore)((s) => s.model);
    const qualityPreset = (0, agentStore_1.useAgentStore)((s) => s.qualityPreset);
    const providerStatuses = (0, authStore_1.useAuthStore)((s) => s.providerStatuses);
    const oauthStatuses = (0, authStore_1.useAuthStore)((s) => s.oauthStatuses);
    const { locale, t } = (0, i18nStore_1.useI18n)();
    const [open, setOpen] = (0, react_1.useState)(false);
    const generatedId = (0, react_1.useId)().replace(/:/g, '');
    const panelId = `sidebar-model-selector-panel-${generatedId}`;
    const allModels = (0, react_1.useMemo)(() => groups.flatMap((group) => group.models), [groups]);
    const currentModel = allModels.find((entry) => entry.id === model) ?? null;
    const currentAccess = (0, modelAuth_1.describeModelAccess)({
        modelId: model,
        modelEntry: currentModel,
        providerStatuses,
        oauthStatuses,
    });
    const presetDefinition = (0, qualityPreset_1.getQualityPresetDefinition)(qualityPreset);
    const customLabel = currentModel?.displayName ?? (model.includes('/') ? model.split('/')[1] : model);
    const currentGroupDefinition = currentModel
        ? (0, modelCapability_1.getCapabilityGroupDefinition)(currentModel.capabilityGroup)
        : null;
    const readyModelIds = (0, react_1.useMemo)(() => new Set(allModels
        .filter((entry) => (0, modelAuth_1.describeModelAccess)({
        modelId: entry.id,
        modelEntry: entry,
        providerStatuses,
        oauthStatuses,
    }).ready)
        .map((entry) => entry.id)), [allModels, oauthStatuses, providerStatuses]);
    const recommendation = (0, react_1.useMemo)(() => (0, recommendModel_1.recommendModel)(allModels, {
        locale,
        qualityPreset,
        readyModelIds,
    }), [allModels, locale, qualityPreset, readyModelIds]);
    const recommendationReason = recommendation?.reasons.map((reason) => t(`llm.recommend.reason.${reason}`)).join(' · ') ?? '';
    const currentLabel = qualityPreset === 'custom' ? customLabel : presetDefinition.label;
    const currentSummary = qualityPreset === 'custom'
        ? currentGroupDefinition
            ? t(currentGroupDefinition.descriptionKey)
            : t('llm.current.customDescription')
        : presetDefinition.summary;
    const handleSelectModel = (modelId) => {
        onChangeModel(modelId);
        setOpen(false);
    };
    const handleSelectPreset = (preset) => {
        onChangeQualityPreset(preset);
        setOpen(false);
    };
    return ((0, jsx_runtime_1.jsxs)("div", { className: "relative px-3 py-1.5", children: [(0, jsx_runtime_1.jsxs)("div", { className: "mb-1 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-ds-muted", children: [(0, jsx_runtime_1.jsx)(lucide_react_1.Sparkles, { size: 12, "aria-hidden": "true" }), t('sidebar.model')] }), (0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "secondary", size: "md", "aria-controls": panelId, "aria-expanded": open, "aria-haspopup": "dialog", className: "w-full justify-between rounded-ds-lg px-ds-3 py-ds-3 text-left", onClick: () => setOpen(!open), children: (0, jsx_runtime_1.jsxs)("div", { className: "flex items-start justify-between gap-2", children: [(0, jsx_runtime_1.jsxs)("div", { className: "min-w-0", children: [(0, jsx_runtime_1.jsx)("div", { className: "truncate text-xs text-ds-text", children: currentLabel }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1 text-[10px] text-ds-muted", children: currentSummary }), (0, jsx_runtime_1.jsxs)("div", { className: "mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px] text-ds-muted", children: [currentGroupDefinition ? (0, jsx_runtime_1.jsx)("span", { children: t(currentGroupDefinition.titleKey) }) : null, (0, jsx_runtime_1.jsx)(primitives_1.Badge, { compact: true, tone: statusBadgeTone(currentAccess.tone), children: currentAccess.shortLabel })] }), currentModel ? ((0, jsx_runtime_1.jsx)("div", { className: "mt-1.5 flex flex-wrap gap-1", children: currentModel.badges.slice(0, 3).map((badge) => ((0, jsx_runtime_1.jsx)(CapabilityBadge_1.CapabilityBadge, { badge: badge }, `${currentModel.id}-${badge}`))) })) : null] }), (0, jsx_runtime_1.jsx)(lucide_react_1.ChevronDown, { size: 12, "aria-hidden": "true", className: `mt-0.5 text-ds-muted transition-transform ${open ? 'rotate-180' : ''}` })] }) }), open ? ((0, jsx_runtime_1.jsxs)(primitives_1.Card, { id: panelId, role: "dialog", "aria-modal": "false", "aria-label": t('sidebar.model'), className: "absolute left-3 right-3 top-full z-20 mt-1 max-h-96 overflow-y-auto border-ds-border bg-ds-surface p-0 shadow-xl", children: [(0, jsx_runtime_1.jsx)("div", { className: "border-b border-ds-border bg-ds-bg/50 px-3 py-2 text-[10px] uppercase tracking-wider text-ds-muted/70", children: t('llm.section.simplePresets') }), (0, jsx_runtime_1.jsx)("div", { className: "space-y-2 p-2", children: qualityPreset_1.SIMPLE_QUALITY_PRESETS.map((preset) => {
                            const definition = (0, qualityPreset_1.getQualityPresetDefinition)(preset);
                            const active = qualityPreset === preset;
                            return ((0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: active ? 'primary' : 'secondary', size: "md", className: "w-full justify-start rounded-ds-lg px-ds-3 py-ds-3 text-left", onClick: () => handleSelectPreset(preset), children: (0, jsx_runtime_1.jsxs)("div", { className: "min-w-0", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-xs font-medium", children: definition.label }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1 text-[10px] leading-5 text-ds-muted", children: definition.summary })] }) }, preset));
                        }) }), (0, jsx_runtime_1.jsx)("div", { className: "border-t border-ds-border bg-ds-bg/50 px-3 py-2 text-[10px] uppercase tracking-wider text-ds-muted/70", children: t('llm.section.capabilityGroups') }), (0, jsx_runtime_1.jsxs)("div", { className: "space-y-3 p-2", children: [groups.map((group) => ((0, jsx_runtime_1.jsxs)(primitives_1.Card, { role: "group", "aria-label": t(group.titleKey), className: "overflow-hidden border-ds-border bg-ds-bg p-0 shadow-none", children: [(0, jsx_runtime_1.jsxs)("div", { className: "border-b border-ds-border/60 px-3 py-2", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[11px] font-medium uppercase tracking-[0.18em] text-ds-muted", children: t(group.titleKey) }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1 text-[10px] leading-5 text-ds-muted/90", children: t(group.descriptionKey) })] }), group.models.length === 0 ? ((0, jsx_runtime_1.jsxs)("div", { className: "px-3 py-3 text-[11px] text-ds-muted", children: [(0, jsx_runtime_1.jsx)("div", { className: "font-medium text-ds-text", children: t(group.emptyTitleKey) }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1", children: t(group.emptyDescriptionKey) })] })) : (group.models.map((entry) => {
                                        const access = (0, modelAuth_1.describeModelAccess)({
                                            modelId: entry.id,
                                            modelEntry: entry,
                                            providerStatuses,
                                            oauthStatuses,
                                        });
                                        const isRecommended = recommendation?.model.id === entry.id;
                                        return ((0, jsx_runtime_1.jsx)("button", { type: "button", "aria-pressed": entry.id === model, className: `
                          w-full border-t border-ds-border/40 px-3 py-3 text-left transition-colors
                          first:border-t-0 hover:bg-ds-accent/10
                          ${entry.id === model ? 'bg-ds-accent/5' : ''}
                        `, onClick: () => handleSelectModel(entry.id), children: (0, jsx_runtime_1.jsxs)("div", { className: "flex items-start justify-between gap-2", children: [(0, jsx_runtime_1.jsxs)("div", { className: "min-w-0", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex flex-wrap items-center gap-2", children: [(0, jsx_runtime_1.jsx)("div", { className: `text-xs font-medium ${entry.id === model ? 'text-ds-accent' : 'text-ds-text'}`, children: entry.displayName }), isRecommended ? ((0, jsx_runtime_1.jsx)(primitives_1.Badge, { compact: true, tone: "accent", children: t('llm.recommend.badge') })) : null] }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1 flex flex-wrap gap-1", children: entry.badges.map((badge) => ((0, jsx_runtime_1.jsx)(CapabilityBadge_1.CapabilityBadge, { badge: badge }, `${entry.id}-${badge}`))) }), isRecommended && recommendationReason ? ((0, jsx_runtime_1.jsx)("div", { className: "mt-1.5 text-[10px] text-ds-accent", children: recommendationReason })) : null, (0, jsx_runtime_1.jsxs)("div", { className: "mt-1.5 text-[10px] text-ds-muted", children: [access.providerLabel, " \u00B7 ", access.authTypeLabel] }), (0, jsx_runtime_1.jsx)("div", { className: "mt-0.5 text-[10px] text-ds-muted/80", children: access.detail })] }), (0, jsx_runtime_1.jsx)(primitives_1.Badge, { compact: true, tone: statusBadgeTone(access.tone), className: "mt-0.5", children: access.shortLabel })] }) }, entry.id));
                                    }))] }, group.id))), allModels.length === 0 ? ((0, jsx_runtime_1.jsx)("div", { className: "px-3 py-2 text-xs text-ds-muted", children: t('onboarding.connect.loading') })) : null] })] })) : null] }));
}
