import type { DeliveryArtifactView } from '../../types/taskContract';
import { useI18n } from '../../stores/i18nStore';

export interface AudienceSelectionOption {
  audience: string;
  selected: boolean;
  deliverableTypes: string[];
  formats: string[];
  artifact?: DeliveryArtifactView | null;
}

interface Props {
  options: AudienceSelectionOption[];
  disabled?: boolean;
  onToggle: (audience: string) => void;
}

export function AudienceSelector({ options, disabled = false, onToggle }: Props) {
  const { t } = useI18n();

  if (options.length === 0) {
    return (
      <div className="rounded-xl border border-ds-border bg-ds-surface px-3 py-3 text-xs text-ds-muted">
        {t('workspace.workflow.audience.empty')}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {options.map((option) => {
        const artifactStatus = option.artifact?.rendered_uri
          ? option.artifact.dispatch_mode === 'manual_review'
            ? 'rendered'
            : 'ready'
          : option.artifact
            ? 'planned'
            : 'not built';

        return (
          <label
            key={option.audience}
            className={`flex cursor-pointer items-start gap-3 rounded-xl border px-3 py-2 ${
              option.selected
                ? 'border-ds-accent/60 bg-ds-accent/10'
                : 'border-ds-border bg-ds-surface'
            } ${disabled ? 'cursor-not-allowed opacity-70' : ''}`}
          >
            <input
              type="checkbox"
              checked={option.selected}
              onChange={() => onToggle(option.audience)}
              disabled={disabled}
              className="mt-0.5 h-3.5 w-3.5 rounded border-ds-border bg-ds-bg text-ds-accent"
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-wide text-ds-text">
                  {option.audience}
                </span>
                <span className="rounded-full border border-ds-border px-2 py-0.5 text-[10px] text-ds-muted">
                  {translateAudienceArtifactStatus(artifactStatus, t)}
                </span>
              </div>
              <p className="mt-1 text-[11px] text-ds-muted">
                {option.deliverableTypes.join(', ')} | {option.formats.join(', ')}
              </p>
            </div>
          </label>
        );
      })}
    </div>
  );
}

function translateAudienceArtifactStatus(
  value: string,
  t: (key: string, vars?: Record<string, string | number | undefined | null>) => string,
): string {
  const keyByStatus: Record<string, string> = {
    rendered: 'workspace.workflow.audience.status.rendered',
    ready: 'workspace.workflow.audience.status.ready',
    planned: 'workspace.workflow.audience.status.planned',
    'not built': 'workspace.workflow.audience.status.notBuilt',
  };
  const key = keyByStatus[value];
  return key ? t(key) : value;
}
