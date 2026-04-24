import type {
  DeliveryArtifactView,
  DeliveryLogRecordView,
  DeliveryPackView,
} from '../../types/taskContract';
import { useI18n } from '../../stores/i18nStore';
import { ArtifactInlinePreview } from './ArtifactInlinePreview';

type TranslateFn = (
  key: string,
  vars?: Record<string, string | number | undefined | null>,
) => string;

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
  const { t } = useI18n();

  if (!pack) {
    return (
      <div className="rounded-xl border border-ds-border bg-ds-surface px-3 py-3 text-xs text-ds-muted">
        {t('workspace.workflow.deliveryPack.empty')}
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
            <p className="text-[11px] uppercase tracking-wide text-ds-muted">
              {t('workspace.workflow.deliveryPack.title')}
            </p>
            <p className="mt-1 text-xs font-medium text-ds-text">{pack.pack_id}</p>
          </div>
          <span className="rounded-full border border-ds-border px-2 py-1 text-[10px] text-ds-text">
            {translateDeliveryPackStatus(pack.status, t)}
          </span>
        </div>
        <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-ds-muted">
          <div>
            {t('workspace.workflow.deliveryPack.generated', {
              value: formatTimestamp(pack.generated_at),
            })}
          </div>
          <div>
            {t('workspace.workflow.deliveryPack.artifacts', { value: pack.artifacts.length })}
          </div>
          <div>
            {t('workspace.workflow.deliveryPack.analysis', {
              value: pack.source_analysis_id ?? '-',
            })}
          </div>
          <div>
            {t('workspace.workflow.deliveryPack.confidence', { value: pack.confidence ?? '-' })}
          </div>
          <div>{t('workspace.workflow.deliveryPack.tenant', { value: pack.tenant })}</div>
          <div>{t('workspace.workflow.deliveryPack.theme', { value: themeId ?? '-' })}</div>
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
                  {translateDeliveryPackStatus(
                    record?.status ?? (artifact.rendered_uri ? 'rendered' : 'planned'),
                    t,
                  )}
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
              <p className="text-[11px] uppercase tracking-wide text-ds-muted">
                {t('workspace.workflow.deliveryPack.preview.title')}
              </p>
              <p className="mt-1 text-xs font-medium text-ds-text">
                {selectedArtifact.type} | {selectedArtifact.audience}
              </p>
            </div>
            <span className="text-[10px] text-ds-muted">
              {translateDeliveryDispatchMode(selectedArtifact.dispatch_mode, t)}
            </span>
          </div>

          <div className="mt-3 space-y-2 text-[11px] text-ds-muted">
            <div>
              {t('workspace.workflow.deliveryPack.template', {
                value: selectedArtifact.template_ref,
              })}
            </div>
            <div>
              {t('workspace.workflow.deliveryPack.structure', {
                value: selectedArtifact.content_policy.structure.join(', '),
              })}
            </div>
            <div>
              {t('workspace.workflow.deliveryPack.channels', {
                value: selectedArtifact.delivery_channel.join(', ') || '-',
              })}
            </div>
            <div>
              {t('workspace.workflow.deliveryPack.verifier', {
                value: selectedArtifact.verifier_report_id ?? '-',
              })}
            </div>
          </div>

          {renderedUri ? (
            <div className="mt-3 rounded-lg border border-ds-border/70 bg-ds-bg/50 px-3 py-2">
              <p className="text-[11px] text-ds-muted">
                {t('workspace.workflow.deliveryPack.renderedFile')}
              </p>
              <p className="mt-1 break-all text-xs text-ds-text">
                {renderedUri}
              </p>
              <button
                type="button"
                onClick={() => onRevealPath(renderedUri)}
                className="mt-2 rounded border border-ds-border px-2 py-1 text-[10px] text-ds-muted hover:text-ds-text"
              >
                {t('workspace.workflow.deliveryPack.revealFile')}
              </button>
            </div>
          ) : (
            <div className="mt-3 rounded-lg border border-ds-border/70 bg-ds-bg/50 px-3 py-2 text-[11px] text-ds-muted">
              {t('workspace.workflow.deliveryPack.notRendered')}
            </div>
          )}

          <ArtifactInlinePreview artifact={selectedArtifact} renderedUri={renderedUri} />
        </div>
      )}
    </div>
  );
}

function translateDeliveryPackStatus(
  value: string,
  t: TranslateFn,
): string {
  const keyByStatus: Record<string, string> = {
    draft: 'workspace.workflow.deliveryPack.status.draft',
    rendered: 'workspace.workflow.deliveryPack.status.rendered',
    planned: 'workspace.workflow.deliveryPack.status.planned',
    dispatched: 'workspace.workflow.deliveryPack.status.dispatched',
    rejected: 'workspace.workflow.deliveryPack.status.rejected',
    sent: 'workspace.workflow.deliveryPack.status.sent',
    blocked: 'workspace.workflow.deliveryPack.status.blocked',
    duplicate: 'workspace.workflow.deliveryPack.status.duplicate',
    failed: 'workspace.workflow.deliveryPack.status.failed',
    dry_run: 'workspace.workflow.deliveryPack.status.dryRun',
  };
  const key = keyByStatus[value];
  return key ? t(key) : value;
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
