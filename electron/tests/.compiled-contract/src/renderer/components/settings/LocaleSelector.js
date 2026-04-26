"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.LocaleSelector = LocaleSelector;
const jsx_runtime_1 = require("react/jsx-runtime");
const lucide_react_1 = require("lucide-react");
const react_1 = require("react");
const primitives_1 = require("../../design-system/primitives");
const i18nStore_1 = require("../../stores/i18nStore");
const i18nStore_2 = require("../../stores/i18nStore");
function LocaleSelector({ value, onChange, id = 'locale-selector', labelKey = 'settings.language.label', descriptionKey = 'settings.language.description', compact = false, }) {
    const { t } = (0, i18nStore_2.useI18n)();
    const [errorMessage, setErrorMessage] = (0, react_1.useState)(null);
    const descriptionId = descriptionKey ? `${id}-description` : undefined;
    const handleChange = async (next) => {
        setErrorMessage(null);
        try {
            await onChange(next);
        }
        catch (error) {
            console.warn('[LocaleSelector] language update failed:', error);
            setErrorMessage(t('settings.language.errorSyncFailed', {
                message: error instanceof Error ? error.message : String(error),
            }));
        }
    };
    return ((0, jsx_runtime_1.jsxs)("div", { className: compact ? 'flex items-start justify-between gap-4' : 'space-y-2', children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex min-w-0 items-start gap-2", children: [(0, jsx_runtime_1.jsx)(lucide_react_1.Globe, { size: 14, className: "mt-0.5 shrink-0 text-ds-muted", "aria-hidden": "true" }), (0, jsx_runtime_1.jsxs)("div", { className: "min-w-0", children: [(0, jsx_runtime_1.jsx)("label", { htmlFor: id, className: "block text-xs font-medium text-ds-text", children: t(labelKey) }), descriptionKey && ((0, jsx_runtime_1.jsx)("p", { id: descriptionId, className: "mt-1 text-[11px] leading-5 text-ds-muted", children: t(descriptionKey) }))] })] }), (0, jsx_runtime_1.jsx)("div", { className: compact ? 'shrink-0' : '', children: (0, jsx_runtime_1.jsx)(primitives_1.Select, { id: id, value: value, onChange: (event) => void handleChange(event.target.value), "aria-describedby": descriptionId, options: i18nStore_1.LOCALE_OPTIONS.map((option) => ({
                        value: option.code,
                        label: `${option.nativeLabel} (${option.englishLabel})`,
                    })), className: "min-w-[160px]" }) }), errorMessage ? ((0, jsx_runtime_1.jsx)("p", { role: "alert", className: "text-[11px] text-ds-error", children: errorMessage })) : null] }));
}
