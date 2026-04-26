"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TelegramConnectFlow = TelegramConnectFlow;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const lucide_react_1 = require("lucide-react");
const qrcode_react_1 = require("qrcode.react");
const primitives_1 = require("../../../design-system/primitives");
const i18nStore_1 = require("../../../stores/i18nStore");
const telegramStore_1 = require("../../../stores/telegramStore");
const telegramConnectFlowModel_1 = require("./telegramConnectFlowModel");
function flowReducer(state, action) {
    switch (action.type) {
        case 'chooseOwnership':
            return (0, telegramConnectFlowModel_1.chooseTelegramBotOwnership)(state, action.choice);
        case 'token':
            return (0, telegramConnectFlowModel_1.updateTelegramTokenEntry)(state, action.token);
        case 'touchToken':
            return (0, telegramConnectFlowModel_1.touchTelegramTokenEntry)(state);
        case 'pairingStarted':
            return (0, telegramConnectFlowModel_1.markTelegramPairingStarted)(state, action.handle);
        case 'pairingStatus':
            return (0, telegramConnectFlowModel_1.applyTelegramPairingStatus)(state, action.status);
        case 'pairedEvent':
            return (0, telegramConnectFlowModel_1.applyTelegramPairedEvent)(state, action);
        case 'tokenPersisted':
            return (0, telegramConnectFlowModel_1.markTelegramTokenPersisted)(state);
        case 'quickPolicy':
            return (0, telegramConnectFlowModel_1.chooseTelegramQuickPolicy)(state, action.choice);
        case 'finish':
            return (0, telegramConnectFlowModel_1.finishTelegramConnectFlow)(state);
        case 'cancel':
            return (0, telegramConnectFlowModel_1.cancelTelegramConnectFlow)(state);
        case 'reset':
            return (0, telegramConnectFlowModel_1.resetTelegramConnectFlow)();
        default:
            return state;
    }
}
function TelegramConnectFlow({ rpc, embedded = false, onComplete, onSkip, onCancel, }) {
    const { t } = (0, i18nStore_1.useI18n)();
    const [flow, dispatch] = (0, react_1.useReducer)(flowReducer, undefined, () => (0, telegramConnectFlowModel_1.createTelegramConnectFlowState)());
    const [secondsRemaining, setSecondsRemaining] = (0, react_1.useState)(null);
    const [localError, setLocalError] = (0, react_1.useState)(null);
    const [copyState, setCopyState] = (0, react_1.useState)('idle');
    const [sendTestOnFinish, setSendTestOnFinish] = (0, react_1.useState)(true);
    const persistInFlightRef = (0, react_1.useRef)(false);
    const loading = (0, telegramStore_1.useTelegramStore)((state) => state.loading);
    const telegramStatus = (0, telegramStore_1.useTelegramStore)((state) => state.status);
    const telegramError = (0, telegramStore_1.useTelegramStore)((state) => state.error);
    const pairing = (0, telegramStore_1.useTelegramStore)((state) => state.pairing);
    const pairedChat = (0, telegramStore_1.useTelegramStore)((state) => state.pairedChat);
    const botIdentity = (0, telegramStore_1.useTelegramStore)((state) => state.botIdentity);
    const testToken = (0, telegramStore_1.useTelegramStore)((state) => state.testToken);
    const startPairing = (0, telegramStore_1.useTelegramStore)((state) => state.startPairing);
    const refreshPairingStatus = (0, telegramStore_1.useTelegramStore)((state) => state.refreshPairingStatus);
    const cancelPairing = (0, telegramStore_1.useTelegramStore)((state) => state.cancelPairing);
    const disconnect = (0, telegramStore_1.useTelegramStore)((state) => state.disconnect);
    const reconnect = (0, telegramStore_1.useTelegramStore)((state) => state.reconnect);
    const refreshStatus = (0, telegramStore_1.useTelegramStore)((state) => state.refreshStatus);
    const sendTestMessage = (0, telegramStore_1.useTelegramStore)((state) => state.sendTestMessage);
    const clearTelegramError = (0, telegramStore_1.useTelegramStore)((state) => state.clearError);
    const command = (0, react_1.useMemo)(() => (0, telegramConnectFlowModel_1.buildTelegramStartCommand)(flow.pairingCode), [flow.pairingCode]);
    const botUsername = flow.botUsername ?? botIdentity?.username ?? null;
    const deepLink = (0, react_1.useMemo)(() => (0, telegramConnectFlowModel_1.buildTelegramBotDeepLink)(botUsername, flow.pairingCode), [botUsername, flow.pairingCode]);
    (0, react_1.useEffect)(() => {
        if (!flow.pairingExpiresAtMs || flow.substep !== 'pairing') {
            setSecondsRemaining(null);
            return;
        }
        const tick = () => {
            setSecondsRemaining((0, telegramConnectFlowModel_1.getTelegramPairingSecondsRemaining)(flow));
        };
        tick();
        const timer = window.setInterval(tick, 1000);
        return () => window.clearInterval(timer);
    }, [flow, flow.pairingExpiresAtMs, flow.substep]);
    (0, react_1.useEffect)(() => {
        if (!flow.handleId || flow.substep !== 'pairing') {
            return;
        }
        const timer = window.setInterval(() => {
            void refreshPairingStatus(rpc, flow.handleId).catch(() => undefined);
        }, 3000);
        return () => window.clearInterval(timer);
    }, [flow.handleId, flow.substep, refreshPairingStatus, rpc]);
    (0, react_1.useEffect)(() => {
        if (!pairing?.state) {
            return;
        }
        dispatch({ type: 'pairingStatus', status: pairing.state });
    }, [pairing?.state]);
    (0, react_1.useEffect)(() => {
        if (!pairedChat) {
            return;
        }
        dispatch({
            type: 'pairedEvent',
            handleId: pairing?.handleId ?? flow.handleId,
            chatId: pairedChat.chatId,
        });
    }, [flow.handleId, pairedChat, pairing?.handleId]);
    (0, react_1.useEffect)(() => {
        if (!flow.persistTokenRequested
            || flow.tokenPersisted
            || persistInFlightRef.current) {
            return;
        }
        const token = flow.token.trim();
        if (!token || !window.electronAPI?.setConfigSecret) {
            return;
        }
        persistInFlightRef.current = true;
        void window.electronAPI
            .setConfigSecret('channels.telegram.bot_token', token)
            .then((result) => {
            if (result.ok) {
                dispatch({ type: 'tokenPersisted' });
                setLocalError(null);
                return;
            }
            setLocalError(result.error ?? t('settings.telegramConnect.error.persist'));
        })
            .catch((error) => {
            setLocalError(error instanceof Error
                ? error.message
                : t('settings.telegramConnect.error.persist'));
        })
            .finally(() => {
            persistInFlightRef.current = false;
        });
    }, [flow.persistTokenRequested, flow.token, flow.tokenPersisted, t]);
    const beginPairing = (0, react_1.useCallback)(async () => {
        clearTelegramError();
        setLocalError(null);
        dispatch({ type: 'touchToken' });
        const touched = (0, telegramConnectFlowModel_1.touchTelegramTokenEntry)(flow);
        if (!(0, telegramConnectFlowModel_1.canStartTelegramPairing)(touched)) {
            return;
        }
        try {
            const token = touched.token.trim();
            const validation = await testToken(rpc, token);
            if (!validation.ok) {
                setLocalError(t((0, telegramConnectFlowModel_1.resolveTelegramTokenFailureKey)(validation.reason)));
                return;
            }
            const handle = await startPairing(rpc, token);
            dispatch({ type: 'pairingStarted', handle });
        }
        catch (error) {
            setLocalError(error instanceof Error
                ? error.message
                : t('settings.telegramConnect.error.startPairing'));
        }
    }, [clearTelegramError, flow, rpc, startPairing, t, testToken]);
    const cancelFlow = (0, react_1.useCallback)(async () => {
        if (flow.handleId && flow.pairingStatus === 'pending') {
            await cancelPairing(rpc, flow.handleId).catch(() => undefined);
        }
        dispatch({ type: 'cancel' });
        onCancel?.();
    }, [cancelPairing, flow.handleId, flow.pairingStatus, onCancel, rpc]);
    const copyCommand = (0, react_1.useCallback)(async () => {
        try {
            await navigator.clipboard.writeText(command);
            setCopyState('copied');
        }
        catch {
            setCopyState('failed');
        }
    }, [command]);
    const finish = (0, react_1.useCallback)(async () => {
        if (sendTestOnFinish && pairedChat?.chatId) {
            await sendTestMessage(rpc, pairedChat.chatId).catch(() => undefined);
        }
        dispatch({ type: 'finish' });
        onComplete?.();
    }, [onComplete, pairedChat?.chatId, rpc, sendTestMessage, sendTestOnFinish]);
    const disconnectCurrentBot = (0, react_1.useCallback)(async () => {
        setLocalError(null);
        try {
            await disconnect(rpc);
            if (window.electronAPI?.clearConfigSecret) {
                await window.electronAPI.clearConfigSecret('channels.telegram.bot_token');
            }
            dispatch({ type: 'reset' });
        }
        catch (error) {
            setLocalError(error instanceof Error
                ? error.message
                : t('settings.telegramConnect.error.disconnect'));
        }
    }, [disconnect, rpc, t]);
    const reconnectCurrentBot = (0, react_1.useCallback)(async () => {
        setLocalError(null);
        try {
            await reconnect(rpc);
            await refreshStatus(rpc);
        }
        catch (error) {
            setLocalError(error instanceof Error
                ? error.message
                : t('settings.telegramConnect.error.reconnect'));
        }
    }, [reconnect, refreshStatus, rpc, t]);
    const tokenErrorMessage = flow.tokenError === 'required'
        ? t('settings.telegramConnect.token.errorRequired')
        : flow.tokenError === 'format'
            ? t('settings.telegramConnect.token.errorFormat')
            : undefined;
    const currentError = localError ?? telegramError;
    const showConnectedSummary = Boolean(pairedChat) && flow.substep === 'ownership';
    return ((0, jsx_runtime_1.jsxs)("section", { className: embedded
            ? 'space-y-4'
            : 'space-y-4 rounded-lg border border-ds-border bg-ds-surface p-4', "aria-label": t('settings.telegramConnect.ariaLabel'), children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex flex-wrap items-start justify-between gap-3", children: [(0, jsx_runtime_1.jsxs)("div", { className: "min-w-0 space-y-1", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-center gap-2 text-sm font-semibold text-ds-text", children: [(0, jsx_runtime_1.jsx)(lucide_react_1.Bot, { size: 16, "aria-hidden": "true" }), (0, jsx_runtime_1.jsx)("span", { children: t('settings.telegramConnect.title') })] }), (0, jsx_runtime_1.jsx)("p", { className: "text-xs leading-5 text-ds-muted", children: t('settings.telegramConnect.description') })] }), (0, jsx_runtime_1.jsxs)("div", { className: "flex items-center gap-2", children: [onSkip ? ((0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "ghost", size: "sm", onClick: onSkip, children: t('onboarding.notify.skip') })) : null, onCancel ? ((0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "ghost", size: "sm", leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.X, { size: 14, "aria-hidden": "true" }), onClick: () => void cancelFlow(), children: t('settings.telegramConnect.cancel') })) : null] })] }), showConnectedSummary ? ((0, jsx_runtime_1.jsxs)("div", { className: "space-y-3 rounded-lg border border-ds-border bg-ds-bg p-3", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex flex-wrap items-start justify-between gap-3", children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-xs font-semibold text-ds-text", children: t('settings.telegramConnect.connected.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1 text-[11px] leading-5 text-ds-muted", children: t('settings.telegramConnect.connected.description', {
                                            chatId: pairedChat?.chatId ?? '',
                                        }) }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1 text-[11px] text-ds-muted", children: t(`settings.telegramConnect.status.${telegramStatus}`) })] }), (0, jsx_runtime_1.jsx)("span", { className: "rounded-full bg-ds-success/15 px-2 py-1 text-[10px] font-medium text-ds-success", children: t('settings.telegramConnect.status.connected') })] }), (0, jsx_runtime_1.jsxs)("div", { className: "flex flex-wrap gap-2", children: [(0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "secondary", size: "sm", loading: loading, onClick: () => void sendTestMessage(rpc, pairedChat?.chatId), children: t('settings.telegramConnect.connected.sendTest') }), (0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "secondary", size: "sm", loading: loading, onClick: () => void reconnectCurrentBot(), children: t('settings.telegramConnect.connected.reconnect') }), (0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "danger", size: "sm", loading: loading, onClick: () => void disconnectCurrentBot(), children: t('settings.telegramConnect.connected.disconnect') })] })] })) : ((0, jsx_runtime_1.jsx)(StepRail, { activeStep: flow.substep })), flow.substep === 'ownership' && !showConnectedSummary ? ((0, jsx_runtime_1.jsx)("div", { className: "grid gap-2 sm:grid-cols-2", children: telegramConnectFlowModel_1.TELEGRAM_BOT_OWNERSHIP_CHOICES.map((choice) => ((0, jsx_runtime_1.jsxs)("button", { type: "button", className: "min-h-20 rounded-lg border border-ds-border bg-ds-bg p-3 text-left shadow-ds-sm transition hover:border-ds-accent/50", onClick: () => dispatch({ type: 'chooseOwnership', choice }), children: [(0, jsx_runtime_1.jsx)("span", { className: "block text-xs font-semibold text-ds-text", children: t(`settings.telegramConnect.ownership.${choice}.title`) }), (0, jsx_runtime_1.jsx)("span", { className: "mt-1 block text-[11px] leading-5 text-ds-muted", children: t(`settings.telegramConnect.ownership.${choice}.description`) })] }, choice))) })) : null, flow.substep === 'token' ? ((0, jsx_runtime_1.jsxs)("div", { className: "space-y-3", children: [(0, jsx_runtime_1.jsxs)("div", { className: "rounded-lg border border-ds-border bg-ds-bg p-3", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-xs font-semibold text-ds-text", children: t('settings.telegramConnect.botFather.title') }), (0, jsx_runtime_1.jsxs)("ol", { className: "mt-2 list-decimal space-y-1 pl-4 text-[11px] leading-5 text-ds-muted", children: [(0, jsx_runtime_1.jsx)("li", { children: t('settings.telegramConnect.botFather.step1') }), (0, jsx_runtime_1.jsx)("li", { children: t('settings.telegramConnect.botFather.step2') }), (0, jsx_runtime_1.jsx)("li", { children: t('settings.telegramConnect.botFather.step3') })] })] }), (0, jsx_runtime_1.jsx)(primitives_1.Input, { type: "password", label: t('settings.telegramConnect.token.label'), description: t('settings.telegramConnect.token.description'), value: flow.token, errorMessage: tokenErrorMessage, onBlur: () => dispatch({ type: 'touchToken' }), onChange: (event) => dispatch({ type: 'token', token: event.currentTarget.value }) }), (0, jsx_runtime_1.jsxs)("div", { className: "flex flex-wrap justify-end gap-2", children: [(0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "ghost", size: "sm", onClick: () => dispatch({ type: 'reset' }), children: t('settings.telegramConnect.back') }), (0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "primary", size: "sm", leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.Send, { size: 14, "aria-hidden": "true" }), loading: loading, onClick: () => void beginPairing(), children: t('settings.telegramConnect.token.startPairing') })] })] })) : null, flow.substep === 'pairing' ? ((0, jsx_runtime_1.jsx)("div", { className: "space-y-3", children: (0, jsx_runtime_1.jsxs)("div", { className: "rounded-lg border border-ds-border bg-ds-bg p-3", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex flex-wrap items-center justify-between gap-2", children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-xs font-semibold text-ds-text", children: t('settings.telegramConnect.pairing.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1 text-[11px] leading-5 text-ds-muted", children: secondsRemaining === null
                                                ? t('settings.telegramConnect.pairing.pending')
                                                : t('settings.telegramConnect.pairing.countdown', {
                                                    seconds: secondsRemaining,
                                                }) })] }), (0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "ghost", size: "sm", leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.RefreshCcw, { size: 14, "aria-hidden": "true" }), onClick: () => void refreshPairingStatus(rpc, flow.handleId).catch(() => undefined), children: t('settings.telegramConnect.pairing.refresh') })] }), (0, jsx_runtime_1.jsx)("code", { className: "mt-3 block select-all rounded-md border border-ds-border bg-ds-surface px-3 py-2 text-xs text-ds-text", children: command }), deepLink ? ((0, jsx_runtime_1.jsxs)("div", { className: "mt-3 flex flex-col items-center gap-2 rounded-md border border-ds-border bg-ds-surface px-3 py-3", children: [(0, jsx_runtime_1.jsx)(qrcode_react_1.QRCodeSVG, { value: deepLink, size: 140, level: "M", includeMargin: true, bgColor: "#ffffff", fgColor: "#0f172a", role: "img", "aria-label": t('settings.telegramConnect.pairing.qrAlt', {
                                        bot: botUsername ?? '',
                                    }) }), (0, jsx_runtime_1.jsx)("p", { className: "max-w-[220px] text-center text-[11px] leading-5 text-ds-muted", children: t('settings.telegramConnect.pairing.qrCaption') })] })) : null, (0, jsx_runtime_1.jsxs)("div", { className: "mt-3 flex flex-wrap gap-2", children: [(0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "secondary", size: "sm", leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.Clipboard, { size: 14, "aria-hidden": "true" }), onClick: () => void copyCommand(), children: copyState === 'copied'
                                        ? t('settings.telegramConnect.pairing.copied')
                                        : copyState === 'failed'
                                            ? t('settings.telegramConnect.pairing.copyFailed')
                                            : t('settings.telegramConnect.pairing.copy') }), deepLink ? ((0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "secondary", size: "sm", leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.ExternalLink, { size: 14, "aria-hidden": "true" }), onClick: () => window.open(deepLink, '_blank', 'noopener,noreferrer'), children: t('settings.telegramConnect.pairing.open') })) : null, (0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "ghost", size: "sm", onClick: () => void cancelFlow(), children: t('settings.telegramConnect.cancel') })] })] }) })) : null, flow.substep === 'policy' ? ((0, jsx_runtime_1.jsxs)("div", { className: "space-y-3", children: [(0, jsx_runtime_1.jsxs)("div", { className: "rounded-lg border border-ds-border bg-ds-bg p-3", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-center gap-2 text-xs font-semibold text-ds-text", children: [(0, jsx_runtime_1.jsx)(lucide_react_1.CheckCircle2, { size: 15, "aria-hidden": "true" }), (0, jsx_runtime_1.jsx)("span", { children: t('settings.telegramConnect.policy.title') })] }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1 text-[11px] leading-5 text-ds-muted", children: t('settings.telegramConnect.policy.description') })] }), (0, jsx_runtime_1.jsx)(primitives_1.Select, { label: t('settings.telegramConnect.policy.choiceLabel'), value: flow.quickPolicy, onChange: (event) => dispatch({
                            type: 'quickPolicy',
                            choice: event.currentTarget.value,
                        }), options: telegramConnectFlowModel_1.TELEGRAM_QUICK_POLICY_CHOICES.map((choice) => ({
                            value: choice,
                            label: t(`settings.telegramConnect.policy.${choice}`),
                        })) }), (0, jsx_runtime_1.jsx)(primitives_1.Checkbox, { checked: sendTestOnFinish, label: t('settings.telegramConnect.policy.sendTest'), description: t('settings.telegramConnect.policy.sendTestDescription'), onChange: (event) => setSendTestOnFinish(event.currentTarget.checked) }), (0, jsx_runtime_1.jsxs)("div", { className: "flex flex-wrap justify-end gap-2", children: [(0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "ghost", size: "sm", onClick: () => dispatch({ type: 'reset' }), children: t('settings.telegramConnect.restart') }), (0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "primary", size: "sm", loading: loading, onClick: () => void finish(), children: t('settings.telegramConnect.finish') })] })] })) : null, flow.substep === 'complete' ? ((0, jsx_runtime_1.jsx)("div", { className: "rounded-lg border border-ds-border bg-ds-bg p-3 text-xs text-ds-text", children: t('settings.telegramConnect.complete') })) : null, currentError ? ((0, jsx_runtime_1.jsx)("div", { className: "rounded-lg border border-ds-error/30 bg-ds-error/10 px-3 py-2 text-[11px] text-ds-error", children: t('settings.telegramConnect.error.current', { message: currentError }) })) : null] }));
}
function StepRail({ activeStep }) {
    const { t } = (0, i18nStore_1.useI18n)();
    const steps = ['ownership', 'token', 'pairing', 'policy'];
    const activeIndex = Math.max(0, steps.indexOf(activeStep));
    return ((0, jsx_runtime_1.jsx)("div", { className: "grid grid-cols-4 gap-1", "aria-hidden": "true", children: steps.map((step, index) => ((0, jsx_runtime_1.jsx)("div", { className: index <= activeIndex
                ? 'h-1 rounded-full bg-ds-accent'
                : 'h-1 rounded-full bg-ds-border', title: t(`settings.telegramConnect.steps.${step}`) }, step))) }));
}
