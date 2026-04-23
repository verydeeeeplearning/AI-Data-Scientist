"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.PROMOTE_DIALOG_IDS = void 0;
exports.validatePromoteDialogDraft = validatePromoteDialogDraft;
exports.PromoteDialog = PromoteDialog;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const promoteToArtifactPort_1 = require("../../application/run/promoteToArtifactPort");
const primitives_1 = require("../../design-system/primitives");
const i18nStore_1 = require("../../stores/i18nStore");
const runtimeDialogA11y_1 = require("./runtimeDialogA11y");
exports.PROMOTE_DIALOG_IDS = {
    shell: 'cards-promote-dialog-shell',
    title: 'cards-promote-dialog-title',
    description: 'cards-promote-dialog-description',
};
function validatePromoteDialogDraft(draft) {
    if (!promoteToArtifactPort_1.PROMOTE_AUDIENCES.includes(draft.audience.trim().toLowerCase())) {
        return 'audience_required';
    }
    return null;
}
function PromoteDialog({ open, busy = false, error = null, initialAudience = 'ds', initialTitle = '', onClose, onSubmit, }) {
    const { t } = (0, i18nStore_1.useI18n)();
    const dialogRef = (0, react_1.useRef)(null);
    const a11yRef = (0, react_1.useRef)(null);
    const [audience, setAudience] = (0, react_1.useState)(initialAudience);
    const [title, setTitle] = (0, react_1.useState)(initialTitle);
    const [validationError, setValidationError] = (0, react_1.useState)(null);
    (0, react_1.useEffect)(() => {
        if (!open) {
            return;
        }
        setAudience(initialAudience);
        setTitle(initialTitle);
        setValidationError(null);
    }, [initialAudience, initialTitle, open]);
    (0, react_1.useEffect)(() => {
        if (!open) {
            return undefined;
        }
        const element = document.getElementById(exports.PROMOTE_DIALOG_IDS.shell);
        if (!(element instanceof HTMLElement)) {
            return undefined;
        }
        dialogRef.current = element;
        const controller = (0, runtimeDialogA11y_1.createRuntimeDialogA11yController)(element);
        a11yRef.current = controller;
        controller.activate();
        return () => {
            controller.deactivate();
            a11yRef.current = null;
        };
    }, [open]);
    if (!open) {
        return null;
    }
    const visibleError = validationError ?? error;
    const handleClose = () => {
        if (!busy) {
            onClose();
        }
    };
    const handleKeyDown = (event) => {
        const action = a11yRef.current?.handleKeyDown(event.nativeEvent);
        if (action === 'escape') {
            handleClose();
        }
    };
    const handleSubmit = (event) => {
        event.preventDefault();
        const nextDraft = {
            audience,
            title: title.trim(),
        };
        const validation = validatePromoteDialogDraft(nextDraft);
        if (validation === 'audience_required') {
            setValidationError(t('cards:promoteDialog.validation.audienceRequired'));
            return;
        }
        setValidationError(null);
        void onSubmit(nextDraft);
    };
    const footer = ((0, jsx_runtime_1.jsxs)(jsx_runtime_1.Fragment, { children: [(0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "secondary", onClick: handleClose, disabled: busy, children: t('cards:promoteDialog.cancel') }), (0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "primary", type: "submit", form: "promote-dialog-form", disabled: busy, children: busy ? t('cards:promoteDialog.confirmBusy') : t('cards:promoteDialog.confirm') })] }));
    return ((0, jsx_runtime_1.jsx)(primitives_1.DialogShell, { id: exports.PROMOTE_DIALOG_IDS.shell, open: open, size: "sm", title: (0, jsx_runtime_1.jsx)("span", { id: exports.PROMOTE_DIALOG_IDS.title, children: t('cards:promoteDialog.title') }), description: (0, jsx_runtime_1.jsx)("span", { id: exports.PROMOTE_DIALOG_IDS.description, children: t('cards:promoteDialog.description') }), footer: footer, dismissLabel: t('cards:promoteDialog.cancel'), onDismiss: busy ? undefined : handleClose, onKeyDown: handleKeyDown, tabIndex: -1, children: (0, jsx_runtime_1.jsxs)("form", { id: "promote-dialog-form", className: "space-y-ds-4", onSubmit: handleSubmit, children: [(0, jsx_runtime_1.jsxs)("fieldset", { children: [(0, jsx_runtime_1.jsx)("legend", { className: "text-ds-xs font-medium uppercase tracking-widest text-ds-muted", children: t('cards:promoteDialog.audienceLabel') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-ds-2 grid gap-ds-2 sm:grid-cols-3", children: promoteToArtifactPort_1.PROMOTE_AUDIENCES.map((value) => ((0, jsx_runtime_1.jsx)(primitives_1.Radio, { name: "promote-audience", value: value, checked: audience === value, onChange: () => {
                                    setAudience(value);
                                    setValidationError(null);
                                }, label: t(`cards:promoteDialog.audience.${value}`), className: "rounded-ds-lg border border-ds-border bg-ds-bg px-ds-3 py-ds-2" }, value))) })] }), (0, jsx_runtime_1.jsx)(primitives_1.Input, { value: title, onChange: (event) => setTitle(event.target.value), label: t('cards:promoteDialog.titleLabel'), placeholder: t('cards:promoteDialog.titlePlaceholder') }), visibleError && ((0, jsx_runtime_1.jsx)("div", { className: "text-ds-sm text-rose-300", role: "alert", children: visibleError }))] }) }));
}
