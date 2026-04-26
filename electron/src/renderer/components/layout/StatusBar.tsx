/**
 * Status bar — model, mode, step, cost, connection status.
 */

import { Circle, MessageCircle, Wifi, WifiOff } from 'lucide-react';
import { useAgentStore } from '../../stores/agentStore';
import { useAuthStore } from '../../stores/authStore';
import { useChatStore } from '../../stores/chatStore';
import { useI18n } from '../../stores/i18nStore';
import { useProjectStore } from '../../stores/projectStore';
import { useRuntimeStore } from '../../stores/runtimeStore';
import { useTelegramStore } from '../../stores/telegramStore';
import { useWorkflowStore } from '../../stores/workflowStore';
import { translateRuntimeMode } from '../runtime/runtimeI18n';
import { describeModelAccess } from '../../utils/modelAuth';
import { getQualityPresetDefinition } from '../../utils/qualityPreset';

const MODE_ICONS: Record<string, string> = {
  auto: '\u25cf',
  supervised: '\u25cb',
  'step-by-step': '\u25e6',
};

interface Props {
  readonly onNavigate: (path: string) => void;
}

export function StatusBar({ onNavigate }: Props) {
  const { t } = useI18n();
  const { model, qualityPreset, mode, cost, step, connected } = useAgentStore();
  const { isStreaming, sessionId } = useChatStore();
  const context = useWorkflowStore((s) => s.context);
  const overallQuality = useWorkflowStore((s) => s.overallQuality);
  const runtimeStatus = useRuntimeStore((s) => s.status);
  const providerStatuses = useAuthStore((s) => s.providerStatuses);
  const oauthStatuses = useAuthStore((s) => s.oauthStatuses);
  const projects = useProjectStore((s) => s.projects);
  const selectedProjectId = useProjectStore((s) => s.selectedProjectId);
  const telegramStatus = useTelegramStore((s) => s.status);
  const telegramPairedChat = useTelegramStore((s) => s.pairedChat);
  const telegramPairedCount = useTelegramStore((s) => s.pairedChats.length);
  const telegramBotIdentity = useTelegramStore((s) => s.botIdentity);
  const telegramLastError = useTelegramStore((s) => s.lastError);

  const modelAccess = describeModelAccess({
    modelId: model,
    providerStatuses,
    oauthStatuses,
  });
  const presetDefinition = getQualityPresetDefinition(qualityPreset);
  const selectedProject = projects.find((project) => project.projectId === selectedProjectId) ?? null;
  const presetLabel = t(`settings.qualityPreset.${presetDefinition.id}.label`);
  const modelAccessLabel = translateModelAccessShortLabel(modelAccess.shortLabel, t);
  const canOpenCredentialSettings = modelAccess.shortLabel === 'Key required';
  const telegramLabel = translateTelegramStatus(
    telegramStatus,
    Boolean(telegramPairedChat),
    t,
  );
  const telegramStatusClass = telegramStatusClasses(telegramStatus, Boolean(telegramPairedChat));
  const telegramTitle = translateTelegramTooltip(
    {
      botUsername: telegramBotIdentity?.username ?? null,
      lastError: telegramLastError,
      paired: Boolean(telegramPairedChat),
      pairedCount: telegramPairedCount,
      status: telegramStatus,
    },
    t,
  );

  return (
    <div className="h-6 bg-ds-surface border-t border-ds-border flex items-center px-3 text-[11px] text-ds-muted gap-4">
      {/* Connection */}
      <div className="flex items-center gap-1">
        {connected ? (
          <Wifi size={10} className="text-ds-success" />
        ) : (
          <WifiOff size={10} className="text-ds-error" />
        )}
      </div>

      {/* Model */}
      <span title={model}>{presetLabel}</span>

      {canOpenCredentialSettings ? (
        <button
          type="button"
          onClick={() => onNavigate('/admin/connectors')}
          title={t('settings.status.needKeyHint')}
          className="rounded border border-ds-warning/30 px-1.5 py-0.5 leading-none text-ds-warning transition-colors hover:bg-ds-warning/10 focus:outline-none focus-visible:ring-1 focus-visible:ring-ds-accent"
        >
          {modelAccessLabel}
        </button>
      ) : (
        <span className={modelAccess.ready ? 'text-ds-success' : 'text-ds-warning'}>
          {modelAccessLabel}
        </span>
      )}

      {/* Separator */}
      <span className="text-ds-border">|</span>

      {/* Mode */}
      <span>
        {MODE_ICONS[mode] ?? ''} {translateRuntimeMode(mode, t)}
      </span>

      {/* Step (when streaming) */}
      {isStreaming && step > 0 && (
        <>
          <span className="text-ds-border">|</span>
          <span>{t('run.runtime.statusBar.step', { step })}</span>
        </>
      )}

      {/* Streaming indicator */}
      {isStreaming && (
        <>
          <span className="text-ds-border">|</span>
          <span className="flex items-center gap-1">
            <Circle size={6} className="text-ds-accent fill-ds-accent animate-pulse" />
            {t('run.runtime.statusBar.running')}
          </span>
        </>
      )}

      {/* Context usage */}
      {context && context.usedPct > 0 && (
        <>
          <span className="text-ds-border">|</span>
          <span className={context.usedPct >= 80 ? 'text-ds-warning' : ''}>
            {context.usedPct}% ctx
          </span>
        </>
      )}

      {/* Quality grade */}
      {overallQuality && (
        <>
          <span className="text-ds-border">|</span>
          <span className="font-mono font-semibold">{overallQuality.grade}</span>
        </>
      )}

      {runtimeStatus?.autonomousRuntimeEnabled && (
        <>
          <span className="text-ds-border">|</span>
          <span
            className={runtimeStatus.autonomousRuntimeRunning ? 'text-ds-success' : 'text-ds-warning'}
          >
            {runtimeStatus.autonomousRuntimeRunning
              ? t('run.runtime.statusBar.autonomyOn')
              : t('run.runtime.statusBar.autonomyIdle')}
          </span>
        </>
      )}

      {runtimeStatus && runtimeStatus.sensorBacklog > 0 && (
        <>
          <span className="text-ds-border">|</span>
          <span>{t('run.runtime.statusBar.queued', { count: runtimeStatus.sensorBacklog })}</span>
        </>
      )}

      <span className="text-ds-border">|</span>
      <button
        type="button"
        onClick={() => onNavigate('/admin/notifications')}
        title={telegramTitle}
        className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 leading-none transition-colors hover:bg-ds-bg focus:outline-none focus-visible:ring-1 focus-visible:ring-ds-accent ${telegramStatusClass}`}
      >
        <MessageCircle size={10} aria-hidden="true" />
        {telegramLabel}
      </button>

      {sessionId && (
        <>
          <span className="text-ds-border">|</span>
          <span className="font-mono truncate max-w-44" title={sessionId}>
            {sessionId}
          </span>
        </>
      )}

      {selectedProject && (
        <>
          <span className="text-ds-border">|</span>
          <span className="truncate max-w-40" title={selectedProject.name}>
            {selectedProject.name}
          </span>
        </>
      )}

      {/* Cost (right-aligned) */}
      <span className="ml-auto">${cost.toFixed(4)}</span>
    </div>
  );
}

function telegramStatusClasses(status: string, paired: boolean): string {
  if (status === 'running' && paired) {
    return 'text-ds-success';
  }
  if (status === 'starting' || status === 'stopping' || (status === 'running' && !paired)) {
    return 'text-ds-warning';
  }
  if (status === 'error') {
    return 'text-ds-error';
  }
  return 'text-ds-muted';
}

function translateTelegramStatus(
  status: string,
  paired: boolean,
  t: (key: string, vars?: Record<string, string | number | undefined | null>) => string,
): string {
  if (status === 'running' && paired) {
    return t('settings.telegramConnect.status.connected');
  }
  if (status === 'running') {
    return t('settings.telegramConnect.status.running');
  }
  if (status === 'starting') {
    return t('settings.telegramConnect.status.starting');
  }
  if (status === 'stopping') {
    return t('settings.telegramConnect.status.stopping');
  }
  if (status === 'error') {
    return t('settings.telegramConnect.status.error');
  }
  return t('settings.telegramConnect.status.disabled');
}

function translateTelegramTooltip(
  args: {
    botUsername: string | null;
    lastError: string | null;
    paired: boolean;
    pairedCount: number;
    status: string;
  },
  t: (key: string, vars?: Record<string, string | number | undefined | null>) => string,
): string {
  if (args.status === 'error') {
    return t('settings.statusbar.telegram.tooltip.error', {
      message: args.lastError ?? t('settings.telegramConnect.status.error'),
    });
  }
  if (args.status === 'running' && args.paired) {
    return t('settings.statusbar.telegram.tooltip.connected', {
      bot: args.botUsername ? `@${args.botUsername}` : 'Telegram',
      count: args.pairedCount,
    });
  }
  return t('settings.statusbar.telegram.tooltip.disconnected');
}

function translateModelAccessShortLabel(
  shortLabel: string,
  t: (key: string, vars?: Record<string, string | number | undefined | null>) => string,
): string {
  const keyByShortLabel: Record<string, string> = {
    Local: 'settings.status.local',
    'Checking auth': 'settings.status.checkingAuth',
    Connected: 'settings.oauth.connected',
    'Ready via key': 'settings.status.readyViaKey',
    'Login required': 'settings.status.needLogin',
    Ready: 'settings.status.ready',
    'Key required': 'settings.status.needKey',
  };
  const key = keyByShortLabel[shortLabel];
  return key ? t(key) : shortLabel;
}
