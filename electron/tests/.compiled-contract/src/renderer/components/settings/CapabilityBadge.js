"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CapabilityBadge = CapabilityBadge;
const jsx_runtime_1 = require("react/jsx-runtime");
const i18nStore_1 = require("../../stores/i18nStore");
function badgeClasses(badge) {
    if (badge === 'strong_reasoning' || badge === 'strong_coding') {
        return 'border-ds-accent/30 bg-ds-accent/10 text-ds-accent';
    }
    if (badge === 'offline') {
        return 'border-emerald-400/20 bg-emerald-500/10 text-emerald-300';
    }
    if (badge === 'cheap' || badge === 'fast') {
        return 'border-amber-400/20 bg-amber-400/10 text-amber-200';
    }
    return 'border-ds-border/70 bg-ds-surface text-ds-muted';
}
function CapabilityBadge({ badge }) {
    const { t } = (0, i18nStore_1.useI18n)();
    return ((0, jsx_runtime_1.jsx)("span", { className: `rounded-full border px-2 py-0.5 text-[10px] font-medium ${badgeClasses(badge)}`, children: t(`llm.badge.${badge}`) }));
}
