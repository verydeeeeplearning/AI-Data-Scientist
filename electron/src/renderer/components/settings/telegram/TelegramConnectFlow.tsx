import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import {
  Bot,
  CheckCircle2,
  Clipboard,
  ExternalLink,
  RefreshCcw,
  Send,
  X,
} from 'lucide-react';
import { QRCodeSVG } from 'qrcode.react';

import { Button, Checkbox, Input, Select } from '../../../design-system/primitives';
import { useI18n } from '../../../stores/i18nStore';
import { useTelegramStore } from '../../../stores/telegramStore';
import type { TelegramPairingStatus } from '../../../infrastructure/api/telegramApi';
import type { RpcFn } from '../types';
import {
  TELEGRAM_BOT_OWNERSHIP_CHOICES,
  TELEGRAM_QUICK_POLICY_CHOICES,
  applyTelegramPairedEvent,
  applyTelegramPairingStatus,
  buildTelegramBotDeepLink,
  buildTelegramStartCommand,
  canStartTelegramPairing,
  cancelTelegramConnectFlow,
  chooseTelegramBotOwnership,
  chooseTelegramQuickPolicy,
  createTelegramConnectFlowState,
  finishTelegramConnectFlow,
  getTelegramPairingSecondsRemaining,
  markTelegramPairingStarted,
  markTelegramTokenPersisted,
  resetTelegramConnectFlow,
  resolveTelegramTokenFailureKey,
  touchTelegramTokenEntry,
  updateTelegramTokenEntry,
  type TelegramBotOwnershipChoice,
  type TelegramConnectFlowState,
  type TelegramQuickPolicyChoice,
} from './telegramConnectFlowModel';

interface TelegramConnectFlowProps {
  readonly rpc: RpcFn;
  readonly embedded?: boolean;
  readonly onComplete?: () => void;
  readonly onSkip?: () => void;
  readonly onCancel?: () => void;
}

type FlowAction =
  | { type: 'chooseOwnership'; choice: TelegramBotOwnershipChoice }
  | { type: 'token'; token: string }
  | { type: 'touchToken' }
  | {
      type: 'pairingStarted';
      handle: Parameters<typeof markTelegramPairingStarted>[1];
    }
  | { type: 'pairingStatus'; status: TelegramPairingStatus }
  | { type: 'pairedEvent'; handleId?: string | null; chatId?: string | null }
  | { type: 'tokenPersisted' }
  | { type: 'quickPolicy'; choice: TelegramQuickPolicyChoice }
  | { type: 'finish' }
  | { type: 'cancel' }
  | { type: 'reset' };

function flowReducer(
  state: TelegramConnectFlowState,
  action: FlowAction,
): TelegramConnectFlowState {
  switch (action.type) {
    case 'chooseOwnership':
      return chooseTelegramBotOwnership(state, action.choice);
    case 'token':
      return updateTelegramTokenEntry(state, action.token);
    case 'touchToken':
      return touchTelegramTokenEntry(state);
    case 'pairingStarted':
      return markTelegramPairingStarted(state, action.handle);
    case 'pairingStatus':
      return applyTelegramPairingStatus(state, action.status);
    case 'pairedEvent':
      return applyTelegramPairedEvent(state, action);
    case 'tokenPersisted':
      return markTelegramTokenPersisted(state);
    case 'quickPolicy':
      return chooseTelegramQuickPolicy(state, action.choice);
    case 'finish':
      return finishTelegramConnectFlow(state);
    case 'cancel':
      return cancelTelegramConnectFlow(state);
    case 'reset':
      return resetTelegramConnectFlow();
    default:
      return state;
  }
}

export function TelegramConnectFlow({
  rpc,
  embedded = false,
  onComplete,
  onSkip,
  onCancel,
}: TelegramConnectFlowProps): ReactElement {
  const { t } = useI18n();
  const [flow, dispatch] = useReducer(flowReducer, undefined, () =>
    createTelegramConnectFlowState(),
  );
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const [sendTestOnFinish, setSendTestOnFinish] = useState(true);
  const persistInFlightRef = useRef(false);

  const loading = useTelegramStore((state) => state.loading);
  const telegramStatus = useTelegramStore((state) => state.status);
  const telegramError = useTelegramStore((state) => state.error);
  const pairing = useTelegramStore((state) => state.pairing);
  const pairedChat = useTelegramStore((state) => state.pairedChat);
  const botIdentity = useTelegramStore((state) => state.botIdentity);
  const testToken = useTelegramStore((state) => state.testToken);
  const startPairing = useTelegramStore((state) => state.startPairing);
  const refreshPairingStatus = useTelegramStore((state) => state.refreshPairingStatus);
  const cancelPairing = useTelegramStore((state) => state.cancelPairing);
  const disconnect = useTelegramStore((state) => state.disconnect);
  const reconnect = useTelegramStore((state) => state.reconnect);
  const refreshStatus = useTelegramStore((state) => state.refreshStatus);
  const sendTestMessage = useTelegramStore((state) => state.sendTestMessage);
  const clearTelegramError = useTelegramStore((state) => state.clearError);

  const command = useMemo(
    () => buildTelegramStartCommand(flow.pairingCode),
    [flow.pairingCode],
  );
  const botUsername = flow.botUsername ?? botIdentity?.username ?? null;
  const deepLink = useMemo(
    () => buildTelegramBotDeepLink(botUsername, flow.pairingCode),
    [botUsername, flow.pairingCode],
  );

  useEffect(() => {
    if (!flow.pairingExpiresAtMs || flow.substep !== 'pairing') {
      setSecondsRemaining(null);
      return;
    }

    const tick = () => {
      setSecondsRemaining(getTelegramPairingSecondsRemaining(flow));
    };
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [flow, flow.pairingExpiresAtMs, flow.substep]);

  useEffect(() => {
    if (!flow.handleId || flow.substep !== 'pairing') {
      return;
    }
    const timer = window.setInterval(() => {
      void refreshPairingStatus(rpc, flow.handleId).catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [flow.handleId, flow.substep, refreshPairingStatus, rpc]);

  useEffect(() => {
    if (!pairing?.state) {
      return;
    }
    dispatch({ type: 'pairingStatus', status: pairing.state });
  }, [pairing?.state]);

  useEffect(() => {
    if (!pairedChat) {
      return;
    }
    dispatch({
      type: 'pairedEvent',
      handleId: pairing?.handleId ?? flow.handleId,
      chatId: pairedChat.chatId,
    });
  }, [flow.handleId, pairedChat, pairing?.handleId]);

  useEffect(() => {
    if (
      !flow.persistTokenRequested
      || flow.tokenPersisted
      || persistInFlightRef.current
    ) {
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
      .catch((error: unknown) => {
        setLocalError(
          error instanceof Error
            ? error.message
            : t('settings.telegramConnect.error.persist'),
        );
      })
      .finally(() => {
        persistInFlightRef.current = false;
      });
  }, [flow.persistTokenRequested, flow.token, flow.tokenPersisted, t]);

  const beginPairing = useCallback(async () => {
    clearTelegramError();
    setLocalError(null);
    dispatch({ type: 'touchToken' });
    const touched = touchTelegramTokenEntry(flow);
    if (!canStartTelegramPairing(touched)) {
      return;
    }

    try {
      const token = touched.token.trim();
      const validation = await testToken(rpc, token);
      if (!validation.ok) {
        setLocalError(t(resolveTelegramTokenFailureKey(validation.reason)));
        return;
      }
      const handle = await startPairing(rpc, token);
      dispatch({ type: 'pairingStarted', handle });
    } catch (error) {
      setLocalError(
        error instanceof Error
          ? error.message
          : t('settings.telegramConnect.error.startPairing'),
      );
    }
  }, [clearTelegramError, flow, rpc, startPairing, t, testToken]);

  const cancelFlow = useCallback(async () => {
    if (flow.handleId && flow.pairingStatus === 'pending') {
      await cancelPairing(rpc, flow.handleId).catch(() => undefined);
    }
    dispatch({ type: 'cancel' });
    onCancel?.();
  }, [cancelPairing, flow.handleId, flow.pairingStatus, onCancel, rpc]);

  const copyCommand = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(command);
      setCopyState('copied');
    } catch {
      setCopyState('failed');
    }
  }, [command]);

  const finish = useCallback(async () => {
    if (sendTestOnFinish && pairedChat?.chatId) {
      await sendTestMessage(rpc, pairedChat.chatId).catch(() => undefined);
    }
    dispatch({ type: 'finish' });
    onComplete?.();
  }, [onComplete, pairedChat?.chatId, rpc, sendTestMessage, sendTestOnFinish]);

  const disconnectCurrentBot = useCallback(async () => {
    setLocalError(null);
    try {
      await disconnect(rpc);
      if (window.electronAPI?.clearConfigSecret) {
        await window.electronAPI.clearConfigSecret('channels.telegram.bot_token');
      }
      dispatch({ type: 'reset' });
    } catch (error) {
      setLocalError(
        error instanceof Error
          ? error.message
          : t('settings.telegramConnect.error.disconnect'),
      );
    }
  }, [disconnect, rpc, t]);

  const reconnectCurrentBot = useCallback(async () => {
    setLocalError(null);
    try {
      await reconnect(rpc);
      await refreshStatus(rpc);
    } catch (error) {
      setLocalError(
        error instanceof Error
          ? error.message
          : t('settings.telegramConnect.error.reconnect'),
      );
    }
  }, [reconnect, refreshStatus, rpc, t]);

  const tokenErrorMessage =
    flow.tokenError === 'required'
      ? t('settings.telegramConnect.token.errorRequired')
      : flow.tokenError === 'format'
        ? t('settings.telegramConnect.token.errorFormat')
        : undefined;
  const currentError = localError ?? telegramError;
  const showConnectedSummary = Boolean(pairedChat) && flow.substep === 'ownership';

  return (
    <section
      className={
        embedded
          ? 'space-y-4'
          : 'space-y-4 rounded-lg border border-ds-border bg-ds-surface p-4'
      }
      aria-label={t('settings.telegramConnect.ariaLabel')}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <div className="flex items-center gap-2 text-sm font-semibold text-ds-text">
            <Bot size={16} aria-hidden="true" />
            <span>{t('settings.telegramConnect.title')}</span>
          </div>
          <p className="text-xs leading-5 text-ds-muted">
            {t('settings.telegramConnect.description')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {onSkip ? (
            <Button variant="ghost" size="sm" onClick={onSkip}>
              {t('onboarding.notify.skip')}
            </Button>
          ) : null}
          {onCancel ? (
            <Button
              variant="ghost"
              size="sm"
              leadingIcon={<X size={14} aria-hidden="true" />}
              onClick={() => void cancelFlow()}
            >
              {t('settings.telegramConnect.cancel')}
            </Button>
          ) : null}
        </div>
      </div>

      {showConnectedSummary ? (
        <div className="space-y-3 rounded-lg border border-ds-border bg-ds-bg p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-xs font-semibold text-ds-text">
                {t('settings.telegramConnect.connected.title')}
              </div>
              <p className="mt-1 text-[11px] leading-5 text-ds-muted">
                {t('settings.telegramConnect.connected.description', {
                  chatId: pairedChat?.chatId ?? '',
                })}
              </p>
              <p className="mt-1 text-[11px] text-ds-muted">
                {t(`settings.telegramConnect.status.${telegramStatus}`)}
              </p>
            </div>
            <span className="rounded-full bg-ds-success/15 px-2 py-1 text-[10px] font-medium text-ds-success">
              {t('settings.telegramConnect.status.connected')}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              size="sm"
              loading={loading}
              onClick={() => void sendTestMessage(rpc, pairedChat?.chatId)}
            >
              {t('settings.telegramConnect.connected.sendTest')}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              loading={loading}
              onClick={() => void reconnectCurrentBot()}
            >
              {t('settings.telegramConnect.connected.reconnect')}
            </Button>
            <Button
              variant="danger"
              size="sm"
              loading={loading}
              onClick={() => void disconnectCurrentBot()}
            >
              {t('settings.telegramConnect.connected.disconnect')}
            </Button>
          </div>
        </div>
      ) : (
        <StepRail activeStep={flow.substep} />
      )}

      {flow.substep === 'ownership' && !showConnectedSummary ? (
        <div className="grid gap-2 sm:grid-cols-2">
          {TELEGRAM_BOT_OWNERSHIP_CHOICES.map((choice) => (
            <button
              key={choice}
              type="button"
              className="min-h-20 rounded-lg border border-ds-border bg-ds-bg p-3 text-left shadow-ds-sm transition hover:border-ds-accent/50"
              onClick={() => dispatch({ type: 'chooseOwnership', choice })}
            >
              <span className="block text-xs font-semibold text-ds-text">
                {t(`settings.telegramConnect.ownership.${choice}.title`)}
              </span>
              <span className="mt-1 block text-[11px] leading-5 text-ds-muted">
                {t(`settings.telegramConnect.ownership.${choice}.description`)}
              </span>
            </button>
          ))}
        </div>
      ) : null}

      {flow.substep === 'token' ? (
        <div className="space-y-3">
          <div className="rounded-lg border border-ds-border bg-ds-bg p-3">
            <div className="text-xs font-semibold text-ds-text">
              {t('settings.telegramConnect.botFather.title')}
            </div>
            <ol className="mt-2 list-decimal space-y-1 pl-4 text-[11px] leading-5 text-ds-muted">
              <li>{t('settings.telegramConnect.botFather.step1')}</li>
              <li>{t('settings.telegramConnect.botFather.step2')}</li>
              <li>{t('settings.telegramConnect.botFather.step3')}</li>
            </ol>
          </div>
          <Input
            type="password"
            label={t('settings.telegramConnect.token.label')}
            description={t('settings.telegramConnect.token.description')}
            value={flow.token}
            errorMessage={tokenErrorMessage}
            onBlur={() => dispatch({ type: 'touchToken' })}
            onChange={(event) =>
              dispatch({ type: 'token', token: event.currentTarget.value })
            }
          />
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => dispatch({ type: 'reset' })}>
              {t('settings.telegramConnect.back')}
            </Button>
            <Button
              variant="primary"
              size="sm"
              leadingIcon={<Send size={14} aria-hidden="true" />}
              loading={loading}
              onClick={() => void beginPairing()}
            >
              {t('settings.telegramConnect.token.startPairing')}
            </Button>
          </div>
        </div>
      ) : null}

      {flow.substep === 'pairing' ? (
        <div className="space-y-3">
          <div className="rounded-lg border border-ds-border bg-ds-bg p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="text-xs font-semibold text-ds-text">
                  {t('settings.telegramConnect.pairing.title')}
                </div>
                <p className="mt-1 text-[11px] leading-5 text-ds-muted">
                  {secondsRemaining === null
                    ? t('settings.telegramConnect.pairing.pending')
                    : t('settings.telegramConnect.pairing.countdown', {
                        seconds: secondsRemaining,
                      })}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                leadingIcon={<RefreshCcw size={14} aria-hidden="true" />}
                onClick={() =>
                  void refreshPairingStatus(rpc, flow.handleId).catch(() => undefined)
                }
              >
                {t('settings.telegramConnect.pairing.refresh')}
              </Button>
            </div>
            <code className="mt-3 block select-all rounded-md border border-ds-border bg-ds-surface px-3 py-2 text-xs text-ds-text">
              {command}
            </code>
            {deepLink ? (
              <div className="mt-3 flex flex-col items-center gap-2 rounded-md border border-ds-border bg-ds-surface px-3 py-3">
                <QRCodeSVG
                  value={deepLink}
                  size={140}
                  level="M"
                  includeMargin
                  bgColor="#ffffff"
                  fgColor="#0f172a"
                  role="img"
                  aria-label={t('settings.telegramConnect.pairing.qrAlt', {
                    bot: botUsername ?? '',
                  })}
                />
                <p className="max-w-[220px] text-center text-[11px] leading-5 text-ds-muted">
                  {t('settings.telegramConnect.pairing.qrCaption')}
                </p>
              </div>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                variant="secondary"
                size="sm"
                leadingIcon={<Clipboard size={14} aria-hidden="true" />}
                onClick={() => void copyCommand()}
              >
                {copyState === 'copied'
                  ? t('settings.telegramConnect.pairing.copied')
                  : copyState === 'failed'
                    ? t('settings.telegramConnect.pairing.copyFailed')
                    : t('settings.telegramConnect.pairing.copy')}
              </Button>
              {deepLink ? (
                <Button
                  variant="secondary"
                  size="sm"
                  leadingIcon={<ExternalLink size={14} aria-hidden="true" />}
                  onClick={() => window.open(deepLink, '_blank', 'noopener,noreferrer')}
                >
                  {t('settings.telegramConnect.pairing.open')}
                </Button>
              ) : null}
              <Button variant="ghost" size="sm" onClick={() => void cancelFlow()}>
                {t('settings.telegramConnect.cancel')}
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {flow.substep === 'policy' ? (
        <div className="space-y-3">
          <div className="rounded-lg border border-ds-border bg-ds-bg p-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-ds-text">
              <CheckCircle2 size={15} aria-hidden="true" />
              <span>{t('settings.telegramConnect.policy.title')}</span>
            </div>
            <p className="mt-1 text-[11px] leading-5 text-ds-muted">
              {t('settings.telegramConnect.policy.description')}
            </p>
          </div>
          <Select
            label={t('settings.telegramConnect.policy.choiceLabel')}
            value={flow.quickPolicy}
            onChange={(event) =>
              dispatch({
                type: 'quickPolicy',
                choice: event.currentTarget.value as TelegramQuickPolicyChoice,
              })
            }
            options={TELEGRAM_QUICK_POLICY_CHOICES.map((choice) => ({
              value: choice,
              label: t(`settings.telegramConnect.policy.${choice}`),
            }))}
          />
          <Checkbox
            checked={sendTestOnFinish}
            label={t('settings.telegramConnect.policy.sendTest')}
            description={t('settings.telegramConnect.policy.sendTestDescription')}
            onChange={(event) => setSendTestOnFinish(event.currentTarget.checked)}
          />
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => dispatch({ type: 'reset' })}>
              {t('settings.telegramConnect.restart')}
            </Button>
            <Button
              variant="primary"
              size="sm"
              loading={loading}
              onClick={() => void finish()}
            >
              {t('settings.telegramConnect.finish')}
            </Button>
          </div>
        </div>
      ) : null}

      {flow.substep === 'complete' ? (
        <div className="rounded-lg border border-ds-border bg-ds-bg p-3 text-xs text-ds-text">
          {t('settings.telegramConnect.complete')}
        </div>
      ) : null}

      {currentError ? (
        <div className="rounded-lg border border-ds-error/30 bg-ds-error/10 px-3 py-2 text-[11px] text-ds-error">
          {t('settings.telegramConnect.error.current', { message: currentError })}
        </div>
      ) : null}
    </section>
  );
}

function StepRail({ activeStep }: { readonly activeStep: string }): ReactElement {
  const { t } = useI18n();
  const steps = ['ownership', 'token', 'pairing', 'policy'] as const;
  const activeIndex = Math.max(0, steps.indexOf(activeStep as (typeof steps)[number]));

  return (
    <div className="grid grid-cols-4 gap-1" aria-hidden="true">
      {steps.map((step, index) => (
        <div
          key={step}
          className={
            index <= activeIndex
              ? 'h-1 rounded-full bg-ds-accent'
              : 'h-1 rounded-full bg-ds-border'
          }
          title={t(`settings.telegramConnect.steps.${step}`)}
        />
      ))}
    </div>
  );
}
