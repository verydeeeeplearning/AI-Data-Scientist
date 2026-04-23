"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SAVE_CHECKPOINT_DIALOG_IDS = void 0;
exports.validateSaveCheckpointDraft = validateSaveCheckpointDraft;
exports.SaveCheckpointDialog = SaveCheckpointDialog;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const primitives_1 = require("../../design-system/primitives");
const i18nStore_1 = require("../../stores/i18nStore");
const runtimeDialogA11y_1 = require("./runtimeDialogA11y");
exports.SAVE_CHECKPOINT_DIALOG_IDS = {
    shell: 'run-save-checkpoint-shell',
    title: 'run-save-checkpoint-title',
    description: 'run-save-checkpoint-description',
};
function validateSaveCheckpointDraft(draft) {
    if (!draft.name.trim()) {
        return 'name_required';
    }
    return null;
}
function SaveCheckpointDialog({ open, busy = false, error = null, initialName = '', initialDescription = '', onClose, onSubmit, }) {
    const { t } = (0, i18nStore_1.useI18n)();
    const dialogRef = (0, react_1.useRef)(null);
    const a11yRef = (0, react_1.useRef)(null);
    const [name, setName] = (0, react_1.useState)(initialName);
    const [description, setDescription] = (0, react_1.useState)(initialDescription);
    const [validationError, setValidationError] = (0, react_1.useState)(null);
    (0, react_1.useEffect)(() => {
        if (!open) {
            return;
        }
        setName(initialName);
        setDescription(initialDescription);
        setValidationError(null);
    }, [initialDescription, initialName, open]);
    (0, react_1.useEffect)(() => {
        if (!open) {
            return undefined;
        }
        const element = document.getElementById(exports.SAVE_CHECKPOINT_DIALOG_IDS.shell);
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
            name: name.trim(),
            description: description.trim(),
        };
        const validation = validateSaveCheckpointDraft(nextDraft);
        if (validation === 'name_required') {
            setValidationError(t('run:checkpointDialog.validation.nameRequired'));
            return;
        }
        setValidationError(null);
        void onSubmit(nextDraft);
    };
    const footer = ((0, jsx_runtime_1.jsxs)(jsx_runtime_1.Fragment, { children: [(0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "secondary", onClick: handleClose, disabled: busy, children: t('run:checkpointDialog.cancel') }), (0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "primary", type: "submit", form: "save-checkpoint-dialog-form", disabled: busy, children: busy
                    ? t('run:checkpointDialog.confirmBusy')
                    : t('run:checkpointDialog.confirm') })] }));
    return ((0, jsx_runtime_1.jsx)(primitives_1.DialogShell, { id: exports.SAVE_CHECKPOINT_DIALOG_IDS.shell, open: open, size: "sm", title: (0, jsx_runtime_1.jsx)("span", { id: exports.SAVE_CHECKPOINT_DIALOG_IDS.title, children: t('run:checkpointDialog.title') }), description: (0, jsx_runtime_1.jsx)("span", { id: exports.SAVE_CHECKPOINT_DIALOG_IDS.description, children: t('run:checkpointDialog.description') }), footer: footer, dismissLabel: t('run:checkpointDialog.cancel'), onDismiss: busy ? undefined : handleClose, onKeyDown: handleKeyDown, tabIndex: -1, children: (0, jsx_runtime_1.jsxs)("form", { id: "save-checkpoint-dialog-form", className: "space-y-ds-4", onSubmit: handleSubmit, children: [(0, jsx_runtime_1.jsx)(primitives_1.Input, { value: name, onChange: (event) => {
                        setName(event.target.value);
                        setValidationError(null);
                    }, label: t('run:checkpointDialog.nameLabel'), placeholder: t('run:checkpointDialog.namePlaceholder') }), (0, jsx_runtime_1.jsx)(primitives_1.Textarea, { value: description, onChange: (event) => setDescription(event.target.value), label: t('run:checkpointDialog.descriptionLabel'), placeholder: t('run:checkpointDialog.descriptionPlaceholder'), rows: 3 }), visibleError && ((0, jsx_runtime_1.jsx)("div", { className: "text-ds-sm text-rose-300", role: "alert", children: visibleError }))] }) }));
}
