"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.normalizeVapidSubject = normalizeVapidSubject;
exports.isValidVapidSubject = isValidVapidSubject;
exports.VapidSubjectField = VapidSubjectField;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const react_i18next_1 = require("react-i18next");
const mobileError_1 = require("../errors/mobileError");
function normalizeVapidSubject(value) {
    return value.trim();
}
function isValidVapidSubject(value) {
    const normalized = normalizeVapidSubject(value);
    return normalized.startsWith('mailto:') || normalized.startsWith('https://');
}
function getBridge() {
    return window.electronAPI?.webPush;
}
function getSourceLabelKey(source) {
    if (source === 'config')
        return 'mobile.push.subject.source.config';
    if (source === 'env')
        return 'mobile.push.subject.source.env';
    return 'mobile.push.subject.source.unset';
}
function VapidSubjectField() {
    const { t } = (0, react_i18next_1.useTranslation)('mobile');
    const bridge = (0, react_1.useMemo)(() => getBridge(), []);
    const [subject, setSubject] = (0, react_1.useState)('');
    const [source, setSource] = (0, react_1.useState)(null);
    const [isLoading, setIsLoading] = (0, react_1.useState)(true);
    const [isSaving, setIsSaving] = (0, react_1.useState)(false);
    const [errorKey, setErrorKey] = (0, react_1.useState)(null);
    const [savedMessage, setSavedMessage] = (0, react_1.useState)(null);
    (0, react_1.useEffect)(() => {
        let cancelled = false;
        if (!bridge) {
            setIsLoading(false);
            setErrorKey('mobile.push.error.bridgeMissing');
            return () => {
                cancelled = true;
            };
        }
        (async () => {
            try {
                const response = await bridge.getSubject();
                if (cancelled)
                    return;
                if (!response.ok) {
                    setErrorKey((0, mobileError_1.getPushSubjectErrorKey)((0, mobileError_1.resolvePushErrorCode)(response.reason), 'load'));
                    setIsLoading(false);
                    return;
                }
                setSubject(response.subject ?? '');
                setSource(response.source ?? null);
                setErrorKey(null);
                setSavedMessage(null);
                setIsLoading(false);
            }
            catch (error) {
                if (cancelled)
                    return;
                setErrorKey((0, mobileError_1.getPushSubjectErrorKey)((0, mobileError_1.resolvePushErrorCode)(error), 'load'));
                setIsLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [bridge, t]);
    const normalizedSubject = normalizeVapidSubject(subject);
    const canSave = Boolean(bridge) && !isLoading && !isSaving && isValidVapidSubject(normalizedSubject);
    const handleSave = async () => {
        if (!bridge) {
            setErrorKey('mobile.push.error.bridgeMissing');
            return;
        }
        const trimmed = normalizeVapidSubject(subject);
        if (!isValidVapidSubject(trimmed)) {
            setErrorKey('mobile.push.subject.error.format');
            setSavedMessage(null);
            return;
        }
        setIsSaving(true);
        setErrorKey(null);
        setSavedMessage(null);
        try {
            const response = await bridge.setSubject({ subject: trimmed });
            if (!response.ok) {
                setErrorKey((0, mobileError_1.getPushSubjectErrorKey)((0, mobileError_1.resolvePushErrorCode)(response.error), 'save'));
                return;
            }
            setSubject(response.subject ?? trimmed);
            setSource(response.source ?? 'config');
            setSavedMessage(t('mobile.push.subject.status.saved'));
        }
        catch (error) {
            setErrorKey((0, mobileError_1.getPushSubjectErrorKey)((0, mobileError_1.resolvePushErrorCode)(error), 'save'));
        }
        finally {
            setIsSaving(false);
        }
    };
    return ((0, jsx_runtime_1.jsxs)("section", { className: "rounded-2xl border border-ds-border bg-ds-surface/70 p-4", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-start justify-between gap-3", children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("h3", { className: "text-sm font-semibold text-ds-text", children: t('mobile.push.subject.label') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1 text-xs leading-5 text-ds-muted", children: t('mobile.push.subject.help') })] }), (0, jsx_runtime_1.jsx)("span", { className: "rounded-full border border-ds-border/70 px-2 py-1 text-[11px] uppercase tracking-[0.16em] text-ds-muted", children: t(getSourceLabelKey(source)) })] }), (0, jsx_runtime_1.jsxs)("label", { className: "mt-3 block", children: [(0, jsx_runtime_1.jsx)("span", { className: "sr-only", children: t('mobile.push.subject.label') }), (0, jsx_runtime_1.jsx)("input", { type: "text", value: subject, onChange: (event) => {
                            setSubject(event.target.value);
                            setErrorKey(null);
                            setSavedMessage(null);
                        }, placeholder: t('mobile.push.subject.placeholder'), className: "mt-1 w-full rounded-xl border border-ds-border bg-ds-bg/70 px-3 py-2 text-sm text-ds-text placeholder:text-ds-muted focus:border-ds-accent focus:outline-none", inputMode: "text", autoCapitalize: "off", autoCorrect: "off", spellCheck: false })] }), (0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-xs leading-5 text-ds-muted", children: t('mobile.push.subject.description') }), savedMessage ? ((0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-xs text-emerald-300", role: "status", "aria-live": "polite", children: savedMessage })) : null, errorKey ? ((0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-xs text-rose-300", role: "alert", children: t(errorKey) })) : null, (0, jsx_runtime_1.jsxs)("div", { className: "mt-3 flex items-center justify-between gap-3", children: [(0, jsx_runtime_1.jsx)("p", { className: "text-[11px] leading-5 text-ds-muted", children: normalizedSubject.length > 0 && isValidVapidSubject(normalizedSubject)
                            ? t('mobile.push.subject.validation.ok')
                            : t('mobile.push.subject.validation.hint') }), (0, jsx_runtime_1.jsx)("button", { type: "button", onClick: () => {
                            void handleSave();
                        }, disabled: !canSave, className: "rounded-full border border-ds-border px-3 py-1 text-xs text-ds-text disabled:cursor-not-allowed disabled:opacity-50", children: isSaving ? t('mobile.push.subject.button.saving') : t('mobile.push.subject.button.save') })] })] }));
}
