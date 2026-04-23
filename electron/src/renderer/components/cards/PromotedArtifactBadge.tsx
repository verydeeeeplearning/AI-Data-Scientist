import { formatCardTimestamp } from './cardPresentation';
import { useRunPromotedArtifacts } from '../../hooks/useRunPromotedArtifacts';
import { useI18n } from '../../stores/i18nStore';

interface Props {
  readonly runId: string | null | undefined;
  readonly cardId: string | null | undefined;
  readonly refreshToken?: number;
}

function normalizeAudienceLabel(audience: string, t: (key: string) => string): string {
  const normalized = audience.trim().toLowerCase();
  if (normalized === 'exec' || normalized === 'ml' || normalized === 'ds') {
    return t(`cards:promoteDialog.audience.${normalized}`);
  }
  return audience;
}

export function PromotedArtifactBadge({ runId, cardId, refreshToken = 0 }: Props) {
  const { t } = useI18n();
  const { artifacts } = useRunPromotedArtifacts(runId, cardId, refreshToken);

  if (artifacts.length === 0) {
    return null;
  }

  const visible = artifacts.slice(0, 2);
  const hiddenCount = Math.max(0, artifacts.length - visible.length);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-ds-muted">
        {t('cards:promotedBadge.label')}
      </span>
      {visible.map((artifact) => (
        <span
          key={artifact.artifactId}
          className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2 py-1 text-[11px] text-emerald-200"
        >
          {t('cards:promotedBadge.entry', {
            audience: normalizeAudienceLabel(artifact.audience, t),
            timestamp: formatCardTimestamp(artifact.createdAt),
          })}
        </span>
      ))}
      {hiddenCount > 0 && (
        <span className="rounded-full border border-ds-border px-2 py-1 text-[11px] text-ds-muted">
          {t('cards:promotedBadge.more', { count: hiddenCount })}
        </span>
      )}
    </div>
  );
}
