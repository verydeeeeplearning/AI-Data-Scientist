import {
  AlertTriangle,
  ClipboardCopy,
  Download,
  FolderOpen,
  RefreshCw,
  ShieldAlert,
  Wrench,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { useI18n } from '../../stores/i18nStore';
import { resolveMainIpcErrorMessage } from '../../utils/mainIpcErrors';

type StartupFailureReason =
  | 'binary_not_found'
  | 'binary_permission_denied'
  | 'port_in_use'
  | 'python_error'
  | 'startup_timeout'
  | 'antivirus_blocked'
  | 'crash_loop'
  | 'health_check_failed';

interface StartupDiagnostics {
  timestamp?: string;
  appVersion?: string;
  platform?: string;
  arch?: string;
  packaged?: boolean;
  appPath?: string;
  logsPath?: string;
  cwd?: string;
  command?: string;
  args?: string[];
  binaryPath?: string;
  binaryExists?: boolean;
  requestedPort?: number;
  resolvedPort?: number;
  attempts?: number;
  exitCode?: number | null;
  stderrSummary?: string;
  detail?: string;
}

interface StartupPayload {
  ok?: false;
  reason?: StartupFailureReason;
  diagnostics?: StartupDiagnostics;
}

interface Props {
  payload: Record<string, unknown> | null;
}

interface ReasonCopy {
  title: string;
  description: string;
  nextStep: string;
}

interface RecoveryPlan {
  heading: string;
  steps: string[];
  note?: string;
}

interface RecoveryAction {
  id: 'reveal_binary' | 'reveal_logs' | 'copy_steps';
  label: string;
}

type TranslateFn = (
  key: string,
  vars?: Record<string, string | number | undefined | null>
) => string;

function normalizePayload(payload: Record<string, unknown> | null): StartupPayload {
  if (!payload) {
    return {};
  }

  const diagnosticsValue = payload.diagnostics;
  return {
    ok: payload.ok === false ? false : undefined,
    reason: typeof payload.reason === 'string' ? payload.reason as StartupFailureReason : undefined,
    diagnostics:
      diagnosticsValue && typeof diagnosticsValue === 'object'
        ? diagnosticsValue as StartupDiagnostics
        : undefined,
  };
}

function getReasonCopy(
  t: TranslateFn,
  reason: StartupFailureReason | undefined
): ReasonCopy {
  const baseKey = reason
    ? `common.diagnostic.reason.${reason}`
    : 'common.diagnostic.reason.fallback';

  return {
    title: t(`${baseKey}.title`),
    description: t(`${baseKey}.description`),
    nextStep: t(`${baseKey}.nextStep`),
  };
}

function buildRecoveryPlan(
  t: TranslateFn,
  reason: StartupFailureReason | undefined,
  diagnostics: StartupDiagnostics | undefined
): RecoveryPlan {
  const recoveryKey = 'common.diagnostic.recovery';
  const platform = diagnostics?.platform?.toLowerCase() ?? '';
  const isWindows = platform.includes('win32') || platform.includes('windows');
  const resolvedPort = diagnostics?.resolvedPort ?? diagnostics?.requestedPort;

  switch (reason) {
    case 'antivirus_blocked': {
      const antivirusStepsKey = isWindows
        ? `${recoveryKey}.antivirus_blocked.windows`
        : `${recoveryKey}.antivirus_blocked.generic`;
      return {
        heading: t(`${recoveryKey}.antivirus_blocked.heading`),
        steps: [
          t(`${antivirusStepsKey}.step1`),
          t(`${antivirusStepsKey}.step2`),
          t(`${antivirusStepsKey}.step3`),
        ],
        note: t(`${recoveryKey}.antivirus_blocked.note`),
      };
    }
    case 'binary_not_found':
      return {
        heading: t(`${recoveryKey}.binary_not_found.heading`),
        steps: [
          t(`${recoveryKey}.binary_not_found.step1`),
          t(`${recoveryKey}.binary_not_found.step2`),
          t(`${recoveryKey}.binary_not_found.step3`),
        ],
        note: t(`${recoveryKey}.binary_not_found.note`),
      };
    case 'binary_permission_denied':
      return {
        heading: t(`${recoveryKey}.binary_permission_denied.heading`),
        steps: [
          t(`${recoveryKey}.binary_permission_denied.step1`),
          t(`${recoveryKey}.binary_permission_denied.step2`),
          t(`${recoveryKey}.binary_permission_denied.step3`),
        ],
      };
    case 'port_in_use':
      return {
        heading: t(`${recoveryKey}.port_in_use.heading`),
        steps: [
          t(`${recoveryKey}.port_in_use.step1`),
          t(`${recoveryKey}.port_in_use.step2`, { port: resolvedPort ?? DEFAULT_PORT_LABEL }),
          t(`${recoveryKey}.port_in_use.step3`),
        ],
      };
    case 'health_check_failed':
      return {
        heading: t(`${recoveryKey}.health_check_failed.heading`),
        steps: [
          t(`${recoveryKey}.health_check_failed.step1`),
          t(`${recoveryKey}.health_check_failed.step2`),
          t(`${recoveryKey}.health_check_failed.step3`),
        ],
      };
    case 'startup_timeout':
      return {
        heading: t(`${recoveryKey}.startup_timeout.heading`),
        steps: [
          t(`${recoveryKey}.startup_timeout.step1`),
          t(`${recoveryKey}.startup_timeout.step2`),
          t(`${recoveryKey}.startup_timeout.step3`),
        ],
      };
    case 'python_error':
      return {
        heading: t(`${recoveryKey}.python_error.heading`),
        steps: [
          t(`${recoveryKey}.python_error.step1`),
          t(`${recoveryKey}.python_error.step2`),
          t(`${recoveryKey}.python_error.step3`),
        ],
      };
    case 'crash_loop':
      return {
        heading: t(`${recoveryKey}.crash_loop.heading`),
        steps: [
          t(`${recoveryKey}.crash_loop.step1`),
          t(`${recoveryKey}.crash_loop.step2`),
          t(`${recoveryKey}.crash_loop.step3`),
        ],
      };
    default:
      return {
        heading: t(`${recoveryKey}.fallback.heading`),
        steps: [
          t(`${recoveryKey}.fallback.step1`),
          t(`${recoveryKey}.fallback.step2`),
          t(`${recoveryKey}.fallback.step3`),
        ],
      };
  }
}

function buildRecoveryActions(
  t: TranslateFn,
  diagnostics: StartupDiagnostics | undefined
): RecoveryAction[] {
  const actions: RecoveryAction[] = [
    { id: 'copy_steps', label: t('common.diagnostic.actions.copySteps') },
  ];

  if (diagnostics?.binaryPath) {
    actions.unshift({
      id: 'reveal_binary',
      label: t('common.diagnostic.actions.revealBackend'),
    });
  }

  if (diagnostics?.logsPath) {
    actions.push({
      id: 'reveal_logs',
      label: t('common.diagnostic.actions.openLogsFolder'),
    });
  }

  return actions;
}

const DEFAULT_PORT_LABEL = '18790';

export function DiagnosticPanel({ payload }: Props) {
  const { t } = useI18n();
  const normalized = useMemo(() => normalizePayload(payload), [payload]);
  const [copied, setCopied] = useState(false);
  const [actionState, setActionState] = useState<string | null>(null);
  const reason = normalized.reason;
  const diagnostics = normalized.diagnostics;
  const copy = useMemo(() => getReasonCopy(t, reason), [reason, t]);
  const recoveryPlan = useMemo(
    () => buildRecoveryPlan(t, reason, diagnostics),
    [diagnostics, reason, t]
  );
  const recoveryActions = useMemo(
    () => buildRecoveryActions(t, diagnostics),
    [diagnostics, t]
  );
  const diagnosticsText = useMemo(
    () => JSON.stringify({ reason: normalized.reason, diagnostics }, null, 2),
    [diagnostics, normalized.reason]
  );
  const supportBundlePayload = useMemo(
    () => ({
      ok: false,
      reason: normalized.reason ?? 'unknown',
      diagnostics: diagnostics ?? {},
    }),
    [diagnostics, normalized.reason]
  );
  const recoveryText = useMemo(
    () => recoveryPlan.steps.map((step, index) => `${index + 1}. ${step}`).join('\n'),
    [recoveryPlan.steps]
  );

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(diagnosticsText);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('[diagnostic] failed to copy diagnostics:', error);
    }
  };

  const handleReload = () => {
    window.location.reload();
  };

  const handleExport = async () => {
    if (!window.electronAPI?.saveDiagnosticBundle) {
      setActionState(t('common.diagnostic.actionState.exportUnavailable'));
      return;
    }

    const timestamp = diagnostics?.timestamp ?? new Date().toISOString();
    const safeTimestamp = timestamp.replace(/[:]/g, '-');
    try {
      const result = await window.electronAPI.saveDiagnosticBundle(
        `ds-agent-support-bundle-${safeTimestamp}.json`,
        supportBundlePayload
      );
      if (result.canceled) {
        setActionState(t('common.diagnostic.actionState.exportCanceled'));
        return;
      }
      setActionState(
        result.path
          ? t('common.diagnostic.actionState.exportSavedAt', { path: result.path })
          : t('common.diagnostic.actionState.exportSaved')
      );
    } catch (error) {
      console.error('[diagnostic] failed to export diagnostics:', error);
      setActionState(t('common.diagnostic.actionState.exportFailed'));
    }
  };

  const handleRevealPath = async (targetPath: string | undefined, label: string) => {
    if (!targetPath) {
      setActionState(t('common.diagnostic.actionState.pathUnavailable', { label }));
      return;
    }
    if (!window.electronAPI?.revealPath) {
      setActionState(t('common.diagnostic.actionState.revealUnavailable'));
      return;
    }

    try {
      const result = await window.electronAPI.revealPath(targetPath);
      if (!result.ok) {
        setActionState(
          resolveMainIpcErrorMessage(
            result,
            'common.diagnostic.actionState.revealError',
            { label },
          )
        );
        return;
      }
      setActionState(t('common.diagnostic.actionState.pathOpened', { label }));
    } catch (error) {
      console.error('[diagnostic] failed to reveal path:', error);
      setActionState(t('common.diagnostic.actionState.pathOpenFailed', { label }));
    }
  };

  const handleCopyRecoverySteps = async () => {
    try {
      await navigator.clipboard.writeText(recoveryText);
      setActionState(t('common.diagnostic.actionState.recoveryCopied'));
    } catch (error) {
      console.error('[diagnostic] failed to copy recovery steps:', error);
      setActionState(t('common.diagnostic.actionState.recoveryCopyFailed'));
    }
  };

  const handleRecoveryAction = async (action: RecoveryAction) => {
    if (action.id === 'reveal_binary') {
      await handleRevealPath(
        diagnostics?.binaryPath,
        t('common.diagnostic.labels.backendLocation')
      );
      return;
    }
    if (action.id === 'reveal_logs') {
      await handleRevealPath(diagnostics?.logsPath, t('common.diagnostic.labels.logsFolder'));
      return;
    }
    await handleCopyRecoverySteps();
  };

  return (
    <main role="main" aria-labelledby="diagnostic-title" className="min-h-screen bg-ds-bg text-ds-text px-6 py-10">
      <div className="mx-auto max-w-5xl rounded-3xl border border-ds-border bg-ds-surface shadow-2xl overflow-hidden">
        <div className="border-b border-ds-border bg-gradient-to-r from-red-500/10 via-amber-500/10 to-transparent px-8 py-8">
          <div className="flex items-start gap-4">
            <div className="rounded-2xl bg-red-500/15 p-3 text-red-400" aria-hidden="true">
              <AlertTriangle size={28} />
            </div>
            <div className="min-w-0">
              <div className="text-xs uppercase tracking-[0.3em] text-ds-muted">
                {t('common.diagnostic.title')}
              </div>
              <h1 id="diagnostic-title" className="mt-2 text-2xl font-semibold text-ds-text">{copy.title}</h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-ds-muted">{copy.description}</p>
              <p className="mt-4 text-sm text-ds-text">
                <span className="text-ds-muted">{t('common.diagnostic.nextStep')}</span> {copy.nextStep}
              </p>
            </div>
          </div>
        </div>

        <div className="grid gap-6 px-8 py-8 lg:grid-cols-[1.15fr,0.85fr]">
          <section className="space-y-4">
            <div className="rounded-2xl border border-ds-border bg-ds-bg/60 p-5">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.25em] text-ds-muted">
                {reason === 'antivirus_blocked' ? <ShieldAlert size={14} /> : <Wrench size={14} />}
                {t('common.diagnostic.guidedRecovery')}
              </div>
              <h2 className="mt-3 text-lg font-semibold text-ds-text">{recoveryPlan.heading}</h2>
              <div className="mt-4 space-y-3">
                {recoveryPlan.steps.map((step, index) => (
                  <div key={step} className="flex items-start gap-3 text-sm">
                    <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ds-accent/15 text-xs font-semibold text-ds-accent">
                      {index + 1}
                    </div>
                    <p className="leading-6 text-ds-text">{step}</p>
                  </div>
                ))}
              </div>
              {recoveryPlan.note && (
                <p className="mt-4 text-xs leading-6 text-ds-muted">{recoveryPlan.note}</p>
              )}
              <div className="mt-5 flex flex-wrap gap-2">
                {recoveryActions.map((action) => (
                  <button
                    key={action.id}
                    type="button"
                    onClick={() => void handleRecoveryAction(action)}
                    className="inline-flex items-center gap-2 rounded-full border border-ds-border px-3 py-1.5 text-xs text-ds-muted transition-colors hover:text-ds-text"
                  >
                    {action.id === 'copy_steps' ? <ClipboardCopy size={14} /> : <FolderOpen size={14} />}
                    {action.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-ds-border bg-ds-bg/60 p-5">
              <div className="text-xs font-semibold uppercase tracking-[0.25em] text-ds-muted">
                {t('common.diagnostic.failureSummary')}
              </div>
              <dl className="mt-4 space-y-3 text-sm">
                <SummaryRow
                  label={t('common.diagnostic.summary.reason')}
                  value={reason ?? t('common.diagnostic.values.unknown')}
                  mono
                />
                <SummaryRow
                  label={t('common.diagnostic.summary.detail')}
                  value={diagnostics?.detail ?? t('common.diagnostic.values.noDetail')}
                />
                <SummaryRow
                  label={t('common.diagnostic.summary.attempts')}
                  value={diagnostics?.attempts !== undefined ? String(diagnostics.attempts) : '-'}
                />
                <SummaryRow
                  label={t('common.diagnostic.summary.port')}
                  value={
                    diagnostics?.resolvedPort !== undefined
                      ? `${diagnostics.resolvedPort}`
                      : '-'
                  }
                />
                <SummaryRow
                  label={t('common.diagnostic.summary.exitCode')}
                  value={
                    diagnostics?.exitCode !== undefined && diagnostics.exitCode !== null
                      ? String(diagnostics.exitCode)
                      : '-'
                  }
                />
              </dl>
            </div>

            <div className="rounded-2xl border border-ds-border bg-ds-bg/60 p-5">
              <div className="flex items-center justify-between gap-3">
                <div className="text-xs font-semibold uppercase tracking-[0.25em] text-ds-muted">
                  {t('common.diagnostic.technicalDetails')}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleExport}
                    className="inline-flex items-center gap-2 rounded-full border border-ds-border px-3 py-1.5 text-xs text-ds-muted transition-colors hover:text-ds-text"
                  >
                    <Download size={14} />
                    {t('common.diagnostic.buttons.exportBundle')}
                  </button>
                  <button
                    type="button"
                    onClick={handleCopy}
                    className="inline-flex items-center gap-2 rounded-full border border-ds-border px-3 py-1.5 text-xs text-ds-muted transition-colors hover:text-ds-text"
                  >
                    <ClipboardCopy size={14} />
                    {copied
                      ? t('common.diagnostic.buttons.copied')
                      : t('common.diagnostic.buttons.copy')}
                  </button>
                </div>
              </div>
              {actionState && (
                <div className="mt-3 text-xs text-ds-muted">{actionState}</div>
              )}
              <pre className="mt-4 max-h-[28rem] overflow-auto rounded-2xl bg-black/30 p-4 text-xs leading-6 text-ds-text whitespace-pre-wrap break-words">
                {diagnosticsText}
              </pre>
            </div>
          </section>

          <section className="space-y-4">
            <div className="rounded-2xl border border-ds-border bg-ds-bg/60 p-5">
              <div className="text-xs font-semibold uppercase tracking-[0.25em] text-ds-muted">
                {t('common.diagnostic.environment')}
              </div>
              <dl className="mt-4 space-y-3 text-sm">
                <SummaryRow
                  label={t('common.diagnostic.summary.appVersion')}
                  value={diagnostics?.appVersion ?? '-'}
                  mono
                />
                <SummaryRow
                  label={t('common.diagnostic.summary.platform')}
                  value={diagnostics?.platform ?? '-'}
                />
                <SummaryRow
                  label={t('common.diagnostic.summary.architecture')}
                  value={diagnostics?.arch ?? '-'}
                />
                <SummaryRow
                  label={t('common.diagnostic.summary.appPath')}
                  value={diagnostics?.appPath ?? '-'}
                  mono
                />
                <SummaryRow
                  label={t('common.diagnostic.summary.binary')}
                  value={diagnostics?.binaryPath ?? diagnostics?.command ?? '-'}
                  mono
                />
                <SummaryRow
                  label={t('common.diagnostic.summary.logsPath')}
                  value={diagnostics?.logsPath ?? '-'}
                  mono
                />
                <SummaryRow
                  label={t('common.diagnostic.summary.binaryExists')}
                  value={
                    diagnostics?.binaryExists === undefined
                      ? '-'
                      : diagnostics.binaryExists
                        ? t('common.diagnostic.values.yes')
                        : t('common.diagnostic.values.no')
                  }
                />
                <SummaryRow
                  label={t('common.diagnostic.summary.timestamp')}
                  value={diagnostics?.timestamp ?? '-'}
                  mono
                />
              </dl>
            </div>

            <div className="rounded-2xl border border-ds-border bg-ds-bg/60 p-5">
              <div className="text-xs font-semibold uppercase tracking-[0.25em] text-ds-muted">
                {t('common.diagnostic.quickActions')}
              </div>
              <div className="mt-4 space-y-3">
                <button
                  type="button"
                  onClick={handleReload}
                  className="flex w-full items-center justify-center gap-2 rounded-2xl bg-ds-accent px-4 py-3 text-sm font-medium text-white transition-opacity hover:opacity-90"
                >
                  <RefreshCw size={16} />
                  {t('common.diagnostic.buttons.reloadWindow')}
                </button>
                <p className="text-xs leading-6 text-ds-muted">
                  {t('common.diagnostic.reloadHelp')}
                </p>
                {diagnostics?.stderrSummary && (
                  <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4 text-xs leading-6 text-amber-100">
                    <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.25em] text-amber-300">
                      {t('common.diagnostic.stderrSummary')}
                    </div>
                    <div className="whitespace-pre-wrap break-words">{diagnostics.stderrSummary}</div>
                  </div>
                )}
              </div>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}

function SummaryRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="text-ds-muted">{label}</dt>
      <dd className={`text-right text-ds-text ${mono ? 'font-mono break-all' : ''}`}>{value}</dd>
    </div>
  );
}
