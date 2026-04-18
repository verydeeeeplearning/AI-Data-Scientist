import type {
  DeliveryArtifactView,
  DeliveryLogRecordView,
  DeliveryPackView,
} from '../../types/taskContract';
import { ArtifactInlinePreview } from './ArtifactInlinePreview';

interface Props {
  pack: DeliveryPackView | null;
  selectedArtifactId: string | null;
  logRecords: DeliveryLogRecordView[];
  onRevealPath: (targetPath: string) => void;
  onSelectArtifact: (artifactId: string) => void;
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function latestRecordForArtifact(
  artifact: DeliveryArtifactView,
  records: DeliveryLogRecordView[],
): DeliveryLogRecordView | null {
  return records.find((record) => record.artifact_id === artifact.artifact_id) ?? null;
}

export function DeliveryPackPreview({
  pack,
  selectedArtifactId,
  logRecords,
  onRevealPath,
  onSelectArtifact,
}: Props) {
  if (!pack) {
    return (
      <div className="rounded-xl border border-ds-border bg-ds-surface px-3 py-3 text-xs text-ds-muted">
        Build a delivery pack to inspect audience-specific artifacts and dispatch readiness.
      </div>
    );
  }

  const selectedArtifact =
    pack.artifacts.find((artifact) => artifact.artifact_id === selectedArtifactId)
    ?? pack.artifacts[0]
    ?? null;
  const renderedUri = selectedArtifact?.rendered_uri ?? null;
  const themeId = typeof pack.global_context.theme_id === 'string'
    ? pack.global_context.theme_id.trim() || null
    : null;

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-ds-border bg-ds-surface px-3 py-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <p className="text-[11px] uppercase tracking-wide text-ds-muted">Delivery Pack</p>
            <p className="mt-1 text-xs font-medium text-ds-text">{pack.pack_id}</p>
          </div>
          <span className="rounded-full border border-ds-border px-2 py-1 text-[10px] text-ds-text">
            {pack.status}
          </span>
        </div>
        <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-ds-muted">
          <div>Generated: {formatTimestamp(pack.generated_at)}</div>
          <div>Artifacts: {pack.artifacts.length}</div>
          <div>Analysis: {pack.source_analysis_id ?? '-'}</div>
          <div>Confidence: {pack.confidence ?? '-'}</div>
          <div>Tenant: {pack.tenant}</div>
          <div>Theme: {themeId ?? '-'}</div>
        </div>
      </div>

      <div className="space-y-2">
        {pack.artifacts.map((artifact) => {
          const record = latestRecordForArtifact(artifact, logRecords);
          const isSelected = artifact.artifact_id === selectedArtifact?.artifact_id;
          return (
            <button
              key={artifact.artifact_id}
              type="button"
              onClick={() => onSelectArtifact(artifact.artifact_id)}
              className={`w-full rounded-xl border px-3 py-3 text-left ${
                isSelected
                  ? 'border-ds-accent/60 bg-ds-accent/10'
                  : 'border-ds-border bg-ds-surface'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-xs font-medium text-ds-text">{artifact.type}</p>
                  <p className="mt-1 text-[11px] text-ds-muted">
                    {artifact.audience} | {artifact.format}
                  </p>
                </div>
                <span className="text-[10px] text-ds-muted">
                  {record?.status ?? (artifact.rendered_uri ? 'rendered' : 'planned')}
                </span>
              </div>
              <p className="mt-2 text-[11px] text-ds-muted">
                {artifact.content_policy.structure.join(' | ')}
              </p>
            </button>
          );
        })}
      </div>

      {selectedArtifact && (
        <div className="rounded-xl border border-ds-border bg-ds-surface px-3 py-3">
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="text-[11px] uppercase tracking-wide text-ds-muted">Preview</p>
              <p className="mt-1 text-xs font-medium text-ds-text">
                {selectedArtifact.type} | {selectedArtifact.audience}
              </p>
            </div>
            <span className="text-[10px] text-ds-muted">{selectedArtifact.dispatch_mode}</span>
          </div>

          <div className="mt-3 space-y-2 text-[11px] text-ds-muted">
            <div>Template: {selectedArtifact.template_ref}</div>
            <div>Structure: {selectedArtifact.content_policy.structure.join(', ')}</div>
            <div>Channels: {selectedArtifact.delivery_channel.join(', ') || '-'}</div>
            <div>Verifier: {selectedArtifact.verifier_report_id ?? '-'}</div>
          </div>

          {renderedUri ? (
            <div className="mt-3 rounded-lg border border-ds-border/70 bg-ds-bg/50 px-3 py-2">
              <p className="text-[11px] text-ds-muted">Rendered file</p>
              <p className="mt-1 break-all text-xs text-ds-text">
                {renderedUri}
              </p>
              <button
                type="button"
                onClick={() => onRevealPath(renderedUri)}
                className="mt-2 rounded border border-ds-border px-2 py-1 text-[10px] text-ds-muted hover:text-ds-text"
              >
                Reveal file
              </button>
            </div>
          ) : (
            <div className="mt-3 rounded-lg border border-ds-border/70 bg-ds-bg/50 px-3 py-2 text-[11px] text-ds-muted">
              Artifact is planned but not rendered yet.
            </div>
          )}

          <ArtifactInlinePreview artifact={selectedArtifact} renderedUri={renderedUri} />
        </div>
      )}
    </div>
  );
}
