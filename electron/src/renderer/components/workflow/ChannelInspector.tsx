import type { DeliveryArtifactView, DeliveryLogRecordView } from '../../types/taskContract';
import { useI18n } from '../../stores/i18nStore';

type TranslateFn = (
  key: string,
  vars?: Record<string, string | number | undefined | null>,
) => string;

interface Props {
  artifact: DeliveryArtifactView | null;
  records: DeliveryLogRecordView[];
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export function ChannelInspector({ artifact, records }: Props) {
  const { t } = useI18n();

  if (!artifact) {
    return (
      <div className="rounded-xl border border-ds-border bg-ds-surface px-3 py-3 text-xs text-ds-muted">
        {t('workspace.workflow.channelInspector.empty')}
      </div>
    );
  }

  const latestByChannel = new Map<string, DeliveryLogRecordView>();
  for (const record of records) {
    if (record.artifact_id !== artifact.artifact_id) {
      continue;
    }
    if (!latestByChannel.has(record.channel)) {
      latestByChannel.set(record.channel, record);
    }
  }

  return (
    <div className="rounded-xl border border-ds-border bg-ds-surface px-3 py-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] uppercase tracking-wide text-ds-muted">
          {t('workspace.workflow.channelInspector.title')}
        </p>
        <span className="text-[10px] text-ds-muted">
          {translateDeliveryDispatchMode(artifact.dispatch_mode, t)}
        </span>
      </div>
      <div className="mt-2 space-y-2">
        {artifact.delivery_channel.map((channel) => {
          const record = latestByChannel.get(channel);
          return (
            <div
              key={channel}
              className="rounded-lg border border-ds-border/70 bg-ds-bg/50 px-3 py-2"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-medium text-ds-text">{channel}</span>
                <span className="text-[10px] text-ds-muted">
                  {record
                    ? translateDeliveryDispatchStatus(record.status, t)
                    : t('workspace.workflow.channelInspector.status.notAttempted')}
                </span>
              </div>
              <p className="mt-1 text-[11px] text-ds-muted">
                {record?.reason ?? record?.adapter_name ?? t('workspace.workflow.channelInspector.awaitingDispatch')}
              </p>
              {record && (
                <p className="mt-1 text-[10px] text-ds-muted">
                  {formatTimestamp(record.recorded_at)}
                </p>
              )}
            </div>
          );
        })}
      </div>

      {records.some((record) => record.artifact_id === artifact.artifact_id) && (
        <div className="mt-3 space-y-1 border-t border-ds-border/70 pt-3">
          <p className="text-[11px] uppercase tracking-wide text-ds-muted">
            {t('workspace.workflow.channelInspector.recentAttempts')}
          </p>
          {records
            .filter((record) => record.artifact_id === artifact.artifact_id)
            .slice(0, 4)
            .map((record) => (
              <div key={record.idempotency_key} className="text-[11px] text-ds-muted">
                {record.channel} | {translateDeliveryDispatchStatus(record.status, t)} |{' '}
                {formatTimestamp(record.recorded_at)}
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

function translateDeliveryDispatchMode(value: string, t: TranslateFn): string {
  const keyByMode: Record<string, string> = {
    auto: 'workspace.workflow.deliveryPack.dispatchMode.auto',
    auto_with_signature: 'workspace.workflow.deliveryPack.dispatchMode.autoWithSignature',
    manual_review: 'workspace.workflow.deliveryPack.dispatchMode.manualReview',
  };
  const key = keyByMode[value];
  return key ? t(key) : value;
}

function translateDeliveryDispatchStatus(value: string, t: TranslateFn): string {
  const keyByStatus: Record<string, string> = {
    sent: 'workspace.workflow.deliveryPack.status.sent',
    blocked: 'workspace.workflow.deliveryPack.status.blocked',
    duplicate: 'workspace.workflow.deliveryPack.status.duplicate',
    failed: 'workspace.workflow.deliveryPack.status.failed',
    dry_run: 'workspace.workflow.deliveryPack.status.dryRun',
  };
  const key = keyByStatus[value];
  return key ? t(key) : value;
}
