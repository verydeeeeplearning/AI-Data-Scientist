import { ArrowRight, X } from 'lucide-react';
import { useI18n } from '../../stores/i18nStore';

interface Props {
  fromPath: string;
  toPath: string;
  onDismiss: () => void;
}

export function MigrationBanner({ fromPath, toPath, onDismiss }: Props) {
  const { t } = useI18n();

  return (
    <div className="flex items-start gap-3 rounded-xl border border-ds-accent/30 bg-ds-accent/10 px-4 py-3">
      <div className="flex-1">
        <div className="text-sm font-semibold text-ds-text">{t('area.migration.title')}</div>
        <div className="mt-1 flex items-center gap-2 text-xs text-ds-muted">
          <span className="font-mono">{fromPath}</span>
          <ArrowRight size={12} aria-hidden="true" />
          <span className="font-mono">{toPath}</span>
        </div>
        <div className="mt-1 text-xs text-ds-muted">{t('area.migration.notice')}</div>
      </div>
      <button
        type="button"
        onClick={onDismiss}
        aria-label={t('common.close')}
        className="rounded p-1 text-ds-muted transition-colors hover:bg-ds-bg hover:text-ds-text"
      >
        <X size={14} />
      </button>
    </div>
  );
}
