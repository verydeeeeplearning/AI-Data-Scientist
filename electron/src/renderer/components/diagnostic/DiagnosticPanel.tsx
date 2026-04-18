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

const REASON_COPY: Record<StartupFailureReason, ReasonCopy> = {
  binary_not_found: {
    title: 'Backend binary was not found',
    description: 'The packaged backend executable is missing or was removed after installation.',
    nextStep: 'Reinstall the app or restore the backend binary from the installer.',
  },
  binary_permission_denied: {
    title: 'Backend could not be executed',
    description: 'The operating system blocked execution permissions for the backend process.',
    nextStep: 'Check file permissions and retry after reinstalling the app.',
  },
  port_in_use: {
    title: 'Preferred startup port was unavailable',
    description: 'Another process is already using the default backend port.',
    nextStep: 'Close the conflicting process or restart the app to retry on a new port.',
  },
  python_error: {
    title: 'Backend crashed during startup',
    description: 'The Python backend exited before it reported readiness.',
    nextStep: 'Review the technical details below and fix the backend error before retrying.',
  },
  startup_timeout: {
    title: 'Backend startup timed out',
    description: 'The backend process did not report readiness within the startup timeout window.',
    nextStep: 'Retry after checking local security software and Python dependency health.',
  },
  antivirus_blocked: {
    title: 'Security software blocked the backend',
    description: 'The backend appears to have been blocked by Windows Defender or another security product.',
    nextStep: 'Allow the DS Agent backend and retry the app.',
  },
  crash_loop: {
    title: 'Backend entered a crash loop',
    description: 'Multiple startup attempts failed before the backend became healthy.',
    nextStep: 'Use the diagnostic details below to identify the repeated startup failure.',
  },
  health_check_failed: {
    title: 'Backend failed health verification',
    description: 'The backend emitted READY but did not answer the health check successfully.',
    nextStep: 'Check for partial startup failures or port binding issues in the diagnostic log.',
  },
};

const FALLBACK_REASON: ReasonCopy = {
  title: 'Backend startup failed',
  description: 'The desktop app could not establish a healthy backend process.',
  nextStep: 'Review the diagnostic details below before retrying.',
};

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

function buildRecoveryPlan(
  reason: StartupFailureReason | undefined,
  diagnostics: StartupDiagnostics | undefined
): RecoveryPlan {
  const platform = diagnostics?.platform?.toLowerCase() ?? '';
  const isWindows = platform.includes('win32') || platform.includes('windows');
  const resolvedPort = diagnostics?.resolvedPort ?? diagnostics?.requestedPort;

  switch (reason) {
    case 'antivirus_blocked':
      return {
        heading: 'Restore the backend from security quarantine',
        steps: isWindows
          ? [
              'Open Windows Security, then go to Virus & threat protection and Protection history.',
              'Restore or allow the DS Agent backend executable, then add an exclusion for its install folder if it is quarantined repeatedly.',
              'Restart DS Agent. If startup still fails, export the support bundle and attach it when escalating.',
            ]
          : [
              'Open your endpoint security or antivirus product and check whether the DS Agent backend executable was quarantined.',
              'Allow the executable or add an exclusion for its install folder.',
              'Restart DS Agent and export the support bundle if the block continues.',
            ],
        note: 'Use the buttons below to reveal the backend location and logs folder directly.',
      };
    case 'binary_not_found':
      return {
        heading: 'Repair or reinstall the packaged backend',
        steps: [
          'Close DS Agent completely before reinstalling or restoring files.',
          'Reveal the backend location and confirm that the packaged executable exists in the ds-agent-backend folder.',
          'If the file is missing, reinstall from a fresh installer and then retry the app.',
        ],
        note: 'If the file was removed by security software, follow the antivirus flow after reinstalling.',
      };
    case 'binary_permission_denied':
      return {
        heading: 'Clear file-permission or quarantine issues',
        steps: [
          'Reveal the backend location and check whether the executable is blocked, quarantined, or missing execute permission.',
          'If your OS or security tool exposes an Unblock or Allow action, apply it to the backend executable.',
          'Restart DS Agent after permissions are restored.',
        ],
      };
    case 'port_in_use':
      return {
        heading: 'Clear repeated port conflicts',
        steps: [
          'Close any duplicate DS Agent instances or stale backend processes.',
          `If the failure repeats, inspect what is binding port ${resolvedPort ?? DEFAULT_PORT_LABEL} and stop the conflicting process.`,
          'Start DS Agent again. The app can fall back to another port, but repeated conflicts should still be investigated.',
        ],
      };
    case 'health_check_failed':
      return {
        heading: 'Investigate partial backend startup',
        steps: [
          'Export the support bundle so the startup handshake and follow-up health failure are captured together.',
          'Review the stderr summary and recent logs for import errors, port bind issues, or immediate shutdown after READY.',
          'Retry the app after addressing the failing dependency or environment issue.',
        ],
      };
    case 'startup_timeout':
      return {
        heading: 'Narrow down a slow or blocked startup',
        steps: [
          'Reveal the logs folder and check whether the backend is starting slowly, blocked by security software, or waiting on an unavailable dependency.',
          'Export the support bundle before retrying so the timeout context is preserved.',
          'Restart the app after addressing the blocking condition.',
        ],
      };
    case 'python_error':
      return {
        heading: 'Fix the backend error before retrying',
        steps: [
          'Read the stderr summary and technical details for the first concrete Python or dependency error.',
          'Reveal the logs folder and export the support bundle so the failing startup path is preserved.',
          'Retry the app only after the root cause is fixed.',
        ],
      };
    case 'crash_loop':
      return {
        heading: 'Stop the repeated startup failure loop',
        steps: [
          'Export the support bundle so all recent startup attempts are captured in one artifact.',
          'Use the technical details and logs to identify what is crashing the backend before it stabilizes.',
          'If the backend executable is missing or quarantined, use the recovery buttons below before retrying.',
        ],
      };
    default:
      return {
        heading: 'Collect context before retrying',
        steps: [
          'Export the support bundle so the current startup failure state is preserved.',
          'Review the diagnostic details and logs for the first actionable error.',
          'Retry the app after the underlying issue is addressed.',
        ],
      };
  }
}

function buildRecoveryActions(
  diagnostics: StartupDiagnostics | undefined
): RecoveryAction[] {
  const actions: RecoveryAction[] = [{ id: 'copy_steps', label: 'Copy Steps' }];

  if (diagnostics?.binaryPath) {
    actions.unshift({ id: 'reveal_binary', label: 'Reveal Backend' });
  }

  if (diagnostics?.logsPath) {
    actions.push({ id: 'reveal_logs', label: 'Open Logs Folder' });
  }

  return actions;
}

const DEFAULT_PORT_LABEL = '18790';

export function DiagnosticPanel({ payload }: Props) {
  const normalized = useMemo(() => normalizePayload(payload), [payload]);
  const [copied, setCopied] = useState(false);
  const [actionState, setActionState] = useState<string | null>(null);
  const reason = normalized.reason;
  const copy = reason ? REASON_COPY[reason] : FALLBACK_REASON;
  const diagnostics = normalized.diagnostics;
  const recoveryPlan = useMemo(() => buildRecoveryPlan(reason, diagnostics), [reason, diagnostics]);
  const recoveryActions = useMemo(() => buildRecoveryActions(diagnostics), [diagnostics]);
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
      setActionState('Support-bundle export is not available in this environment.');
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
        setActionState('Export cancelled.');
        return;
      }
      setActionState(result.path ? `Support bundle saved to ${result.path}` : 'Support bundle saved.');
    } catch (error) {
      console.error('[diagnostic] failed to export diagnostics:', error);
      setActionState('Failed to export support bundle.');
    }
  };

  const handleRevealPath = async (targetPath: string | undefined, label: string) => {
    if (!targetPath) {
      setActionState(`${label} is not available for this failure.`);
      return;
    }
    if (!window.electronAPI?.revealPath) {
      setActionState('Path reveal is not available in this environment.');
      return;
    }

    try {
      const result = await window.electronAPI.revealPath(targetPath);
      if (!result.ok) {
        setActionState(result.error ?? `Unable to reveal ${label.toLowerCase()}.`);
        return;
      }
      setActionState(`${label} opened.`);
    } catch (error) {
      console.error('[diagnostic] failed to reveal path:', error);
      setActionState(`Failed to open ${label.toLowerCase()}.`);
    }
  };

  const handleCopyRecoverySteps = async () => {
    try {
      await navigator.clipboard.writeText(recoveryText);
      setActionState('Recovery steps copied.');
    } catch (error) {
      console.error('[diagnostic] failed to copy recovery steps:', error);
      setActionState('Failed to copy recovery steps.');
    }
  };

  const handleRecoveryAction = async (action: RecoveryAction) => {
    if (action.id === 'reveal_binary') {
      await handleRevealPath(diagnostics?.binaryPath, 'Backend location');
      return;
    }
    if (action.id === 'reveal_logs') {
      await handleRevealPath(diagnostics?.logsPath, 'Logs folder');
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
              <div className="text-xs uppercase tracking-[0.3em] text-ds-muted">Startup Diagnostics</div>
              <h1 id="diagnostic-title" className="mt-2 text-2xl font-semibold text-ds-text">{copy.title}</h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-ds-muted">{copy.description}</p>
              <p className="mt-4 text-sm text-ds-text">
                <span className="text-ds-muted">Next step:</span> {copy.nextStep}
              </p>
            </div>
          </div>
        </div>

        <div className="grid gap-6 px-8 py-8 lg:grid-cols-[1.15fr,0.85fr]">
          <section className="space-y-4">
            <div className="rounded-2xl border border-ds-border bg-ds-bg/60 p-5">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.25em] text-ds-muted">
                {reason === 'antivirus_blocked' ? <ShieldAlert size={14} /> : <Wrench size={14} />}
                Guided Recovery
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
                Failure Summary
              </div>
              <dl className="mt-4 space-y-3 text-sm">
                <SummaryRow label="Reason" value={reason ?? 'unknown'} mono />
                <SummaryRow label="Detail" value={diagnostics?.detail ?? 'No detail captured.'} />
                <SummaryRow
                  label="Attempts"
                  value={diagnostics?.attempts !== undefined ? String(diagnostics.attempts) : '-'}
                />
                <SummaryRow
                  label="Port"
                  value={
                    diagnostics?.resolvedPort !== undefined
                      ? `${diagnostics.resolvedPort}`
                      : '-'
                  }
                />
                <SummaryRow
                  label="Exit Code"
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
                  Technical Details
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleExport}
                    className="inline-flex items-center gap-2 rounded-full border border-ds-border px-3 py-1.5 text-xs text-ds-muted transition-colors hover:text-ds-text"
                  >
                    <Download size={14} />
                    Export Bundle
                  </button>
                  <button
                    type="button"
                    onClick={handleCopy}
                    className="inline-flex items-center gap-2 rounded-full border border-ds-border px-3 py-1.5 text-xs text-ds-muted transition-colors hover:text-ds-text"
                  >
                    <ClipboardCopy size={14} />
                    {copied ? 'Copied' : 'Copy'}
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
                Environment
              </div>
              <dl className="mt-4 space-y-3 text-sm">
                <SummaryRow label="App Version" value={diagnostics?.appVersion ?? '-'} mono />
                <SummaryRow label="Platform" value={diagnostics?.platform ?? '-'} />
                <SummaryRow label="Architecture" value={diagnostics?.arch ?? '-'} />
                <SummaryRow
                  label="App Path"
                  value={diagnostics?.appPath ?? '-'}
                  mono
                />
                <SummaryRow
                  label="Binary"
                  value={diagnostics?.binaryPath ?? diagnostics?.command ?? '-'}
                  mono
                />
                <SummaryRow
                  label="Logs Path"
                  value={diagnostics?.logsPath ?? '-'}
                  mono
                />
                <SummaryRow
                  label="Binary Exists"
                  value={
                    diagnostics?.binaryExists === undefined
                      ? '-'
                      : diagnostics.binaryExists
                        ? 'yes'
                        : 'no'
                  }
                />
                <SummaryRow
                  label="Timestamp"
                  value={diagnostics?.timestamp ?? '-'}
                  mono
                />
              </dl>
            </div>

            <div className="rounded-2xl border border-ds-border bg-ds-bg/60 p-5">
              <div className="text-xs font-semibold uppercase tracking-[0.25em] text-ds-muted">
                Quick Actions
              </div>
              <div className="mt-4 space-y-3">
                <button
                  type="button"
                  onClick={handleReload}
                  className="flex w-full items-center justify-center gap-2 rounded-2xl bg-ds-accent px-4 py-3 text-sm font-medium text-white transition-opacity hover:opacity-90"
                >
                  <RefreshCw size={16} />
                  Reload Window
                </button>
                <p className="text-xs leading-6 text-ds-muted">
                  Reloading retries the renderer only. If the backend binary or Python process is still
                  unhealthy, restart the full app after addressing the issue shown above.
                </p>
                {diagnostics?.stderrSummary && (
                  <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4 text-xs leading-6 text-amber-100">
                    <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.25em] text-amber-300">
                      Stderr Summary
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
