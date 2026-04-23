"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.BRANCH_RUN_DIALOG_IDS = void 0;
exports.validateBranchRunDraft = validateBranchRunDraft;
exports.BranchRunDialog = BranchRunDialog;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const primitives_1 = require("../../design-system/primitives");
const i18nStore_1 = require("../../stores/i18nStore");
const runtimeDialogA11y_1 = require("./runtimeDialogA11y");
exports.BRANCH_RUN_DIALOG_IDS = {
    shell: 'run-branch-dialog-shell',
    title: 'run-branch-dialog-title',
    description: 'run-branch-dialog-description',
};
function validateBranchRunDraft(draft) {
    if (!draft.message.trim()) {
        return 'message_required';
    }
    return null;
}
function BranchRunDialog({ open, busy = false, error = null, initialMessage = '', initialModel = null, modelOptions, onClose, onSubmit, }) {
    const { t } = (0, i18nStore_1.useI18n)();
    const a11yRef = (0, react_1.useRef)(null);
    const [message, setMessage] = (0, react_1.useState)(initialMessage);
    const [model, setModel] = (0, react_1.useState)(initialModel ?? '');
    const [validationError, setValidationError] = (0, react_1.useState)(null);
    (0, react_1.useEffect)(() => {
        if (!open) {
            return;
        }
        setMessage(initialMessage);
        setModel(initialModel ?? '');
        setValidationError(null);
    }, [initialMessage, initialModel, open]);
    (0, react_1.useEffect)(() => {
        if (!open) {
            return undefined;
        }
        const element = document.getElementById(exports.BRANCH_RUN_DIALOG_IDS.shell);
        if (!(element instanceof HTMLElement)) {
            return undefined;
        }
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
            message: message.trim(),
            model: model.trim() ? model.trim() : null,
        };
        const validation = validateBranchRunDraft(nextDraft);
        if (validation === 'message_required') {
            setValidationError(t('run:branchDialog.validation.messageRequired'));
            return;
        }
        setValidationError(null);
        void onSubmit(nextDraft);
    };
    return ((0, jsx_runtime_1.jsx)(primitives_1.DialogShell, { id: exports.BRANCH_RUN_DIALOG_IDS.shell, open: open, size: "sm", className: "max-w-xl rounded-3xl", title: (0, jsx_runtime_1.jsx)("span", { id: exports.BRANCH_RUN_DIALOG_IDS.title, children: t('run:branchDialog.title') }), description: (0, jsx_runtime_1.jsx)("span", { id: exports.BRANCH_RUN_DIALOG_IDS.description, children: t('run:branchDialog.description') }), onKeyDown: handleKeyDown, tabIndex: -1, "aria-describedby": exports.BRANCH_RUN_DIALOG_IDS.description, footer: ((0, jsx_runtime_1.jsxs)(jsx_runtime_1.Fragment, { children: [(0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "secondary", onClick: handleClose, disabled: busy, children: t('run:branchDialog.cancel') }), (0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "primary", type: "submit", form: "branch-run-dialog-form", disabled: busy, children: busy ? t('run:branchDialog.confirmBusy') : t('run:branchDialog.confirm') })] })), children: (0, jsx_runtime_1.jsxs)("form", { id: "branch-run-dialog-form", className: "space-y-ds-4", onSubmit: handleSubmit, children: [(0, jsx_runtime_1.jsx)(primitives_1.Textarea, { id: "run-branch-dialog-message", value: message, onChange: (event) => {
                        setMessage(event.target.value);
                        setValidationError(null);
                    }, label: t('run:branchDialog.messageLabel'), placeholder: t('run:branchDialog.messagePlaceholder'), rows: 5 }), (0, jsx_runtime_1.jsx)(primitives_1.Select, { id: "run-branch-dialog-model", value: model, onChange: (event) => setModel(event.target.value), label: t('run:branchDialog.modelLabel'), options: [
                        { value: '', label: t('run:branchDialog.modelPlaceholder') },
                        ...modelOptions,
                    ] }), visibleError && ((0, jsx_runtime_1.jsx)("div", { className: "text-ds-sm text-ds-error", role: "alert", children: visibleError }))] }) }));
}
