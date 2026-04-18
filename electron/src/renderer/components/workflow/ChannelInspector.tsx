import type { DeliveryArtifactView, DeliveryLogRecordView } from '../../types/taskContract';

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
  if (!artifact) {
    return (
      <div className="rounded-xl border border-ds-border bg-ds-surface px-3 py-3 text-xs text-ds-muted">
        Select one artifact to inspect channel policy and dispatch history.
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
        <p className="text-[11px] uppercase tracking-wide text-ds-muted">Channel Inspector</p>
        <span className="text-[10px] text-ds-muted">{artifact.dispatch_mode}</span>
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
                  {record?.status ?? 'not attempted'}
                </span>
              </div>
              <p className="mt-1 text-[11px] text-ds-muted">
                {record?.reason ?? record?.adapter_name ?? 'Awaiting dispatch evaluation.'}
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
          <p className="text-[11px] uppercase tracking-wide text-ds-muted">Recent Attempts</p>
          {records
            .filter((record) => record.artifact_id === artifact.artifact_id)
            .slice(0, 4)
            .map((record) => (
              <div key={record.idempotency_key} className="text-[11px] text-ds-muted">
                {record.channel} | {record.status} | {formatTimestamp(record.recorded_at)}
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
