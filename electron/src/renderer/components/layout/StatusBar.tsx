/**
 * Status bar — model, mode, step, cost, connection status.
 */

import { Circle, Wifi, WifiOff } from 'lucide-react';
import { useAgentStore } from '../../stores/agentStore';
import { useAuthStore } from '../../stores/authStore';
import { useChatStore } from '../../stores/chatStore';
import { useProjectStore } from '../../stores/projectStore';
import { useRuntimeStore } from '../../stores/runtimeStore';
import { useWorkflowStore } from '../../stores/workflowStore';
import { describeModelAccess } from '../../utils/modelAuth';
import { getQualityPresetDefinition } from '../../utils/qualityPreset';

const MODE_ICONS: Record<string, string> = {
  auto: '\u25cf',
  supervised: '\u25cb',
  'step-by-step': '\u25e6',
};

export function StatusBar() {
  const { model, qualityPreset, mode, cost, step, connected } = useAgentStore();
  const { isStreaming, sessionId } = useChatStore();
  const context = useWorkflowStore((s) => s.context);
  const overallQuality = useWorkflowStore((s) => s.overallQuality);
  const runtimeStatus = useRuntimeStore((s) => s.status);
  const providerStatuses = useAuthStore((s) => s.providerStatuses);
  const oauthStatuses = useAuthStore((s) => s.oauthStatuses);
  const projects = useProjectStore((s) => s.projects);
  const selectedProjectId = useProjectStore((s) => s.selectedProjectId);

  const modelAccess = describeModelAccess({
    modelId: model,
    providerStatuses,
    oauthStatuses,
  });
  const presetDefinition = getQualityPresetDefinition(qualityPreset);
  const selectedProject = projects.find((project) => project.projectId === selectedProjectId) ?? null;

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
      <span title={model}>{presetDefinition.label}</span>

      <span className={modelAccess.ready ? 'text-ds-success' : 'text-amber-400'}>
        {modelAccess.shortLabel}
      </span>

      {/* Separator */}
      <span className="text-ds-border">|</span>

      {/* Mode */}
      <span>
        {MODE_ICONS[mode] ?? ''} {mode}
      </span>

      {/* Step (when streaming) */}
      {isStreaming && step > 0 && (
        <>
          <span className="text-ds-border">|</span>
          <span>Step {step}</span>
        </>
      )}

      {/* Streaming indicator */}
      {isStreaming && (
        <>
          <span className="text-ds-border">|</span>
          <span className="flex items-center gap-1">
            <Circle size={6} className="text-ds-accent fill-ds-accent animate-pulse" />
            Running
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
            autonomy {runtimeStatus.autonomousRuntimeRunning ? 'on' : 'idle'}
          </span>
        </>
      )}

      {runtimeStatus && runtimeStatus.sensorBacklog > 0 && (
        <>
          <span className="text-ds-border">|</span>
          <span>{runtimeStatus.sensorBacklog} queued</span>
        </>
      )}

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
