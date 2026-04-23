import { useId, type KeyboardEvent } from 'react';
import { Check } from 'lucide-react';
import { Button } from '../../design-system/primitives';
import { useI18n } from '../../stores/i18nStore';
import {
  AUDIENCE_VIEW_IDS,
  type AudienceView,
} from '../../domain/workspace/audienceView';

interface Props {
  value: AudienceView;
  onChange: (view: AudienceView) => void;
}

/**
 * Workspace-wide DS / Exec / ML view toggle. Renders as an ARIA radio group
 * styled like a segmented control. Active state is communicated via border,
 * weight, and a checkmark icon, not color alone, to satisfy the
 * "no color-only signaling" a11y rule.
 */
export function AudienceViewSwitcher({ value, onChange }: Props) {
  const { t } = useI18n();
  const groupId = useId().replace(/:/g, '');
  const labelId = `${groupId}-label`;
  const descriptionId = `${groupId}-description`;

  function focusOption(index: number) {
    const targetId = `${groupId}-option-${AUDIENCE_VIEW_IDS[index]}`;
    const target = document.getElementById(targetId);
    if (target instanceof HTMLButtonElement) {
      target.focus();
    }
  }

  function handleKeyDown(
    event: KeyboardEvent<HTMLButtonElement>,
    currentIndex: number,
  ) {
    if (
      event.key !== 'ArrowRight'
      && event.key !== 'ArrowLeft'
      && event.key !== 'Home'
      && event.key !== 'End'
    ) {
      return;
    }
    event.preventDefault();
    const total = AUDIENCE_VIEW_IDS.length;
    let nextIndex = currentIndex;
    if (event.key === 'ArrowRight') {
      nextIndex = (currentIndex + 1) % total;
    } else if (event.key === 'ArrowLeft') {
      nextIndex = (currentIndex - 1 + total) % total;
    } else if (event.key === 'Home') {
      nextIndex = 0;
    } else if (event.key === 'End') {
      nextIndex = total - 1;
    }
    onChange(AUDIENCE_VIEW_IDS[nextIndex]);
    focusOption(nextIndex);
  }

  return (
    <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-3">
      <div>
        <p
          id={labelId}
          className="text-[11px] font-semibold uppercase tracking-[0.22em] text-ds-muted"
        >
          {t('workspace:audienceView.label')}
        </p>
        <p
          id={descriptionId}
          className="mt-0.5 text-xs text-ds-muted/80"
        >
          {t('workspace:audienceView.description')}
        </p>
      </div>
      <div
        role="radiogroup"
        aria-labelledby={labelId}
        aria-describedby={descriptionId}
        aria-orientation="horizontal"
        className="inline-flex flex-wrap items-center gap-1.5 rounded-full border border-ds-border bg-ds-bg/50 p-1"
      >
        {AUDIENCE_VIEW_IDS.map((view, index) => {
          const selected = view === value;
          const optionLabel = t(`workspace:audienceView.option.${view}`);
          const optionHint = t(`workspace:audienceView.option.${view}Hint`);
          return (
            <Button
              key={view}
              id={`${groupId}-option-${view}`}
              type="button"
              role="radio"
              aria-checked={selected}
              aria-label={`${optionLabel}. ${optionHint}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(view)}
              onKeyDown={(event) => handleKeyDown(event, index)}
              variant="ghost"
              size="sm"
              leadingIcon={selected ? (
                <Check size={12} aria-hidden="true" />
              ) : (
                <span aria-hidden="true" className="inline-block w-3" />
              )}
              className={`min-h-9 gap-1.5 px-ds-3 py-1 text-xs shadow-none ${
                selected
                  ? 'border-ds-accent bg-ds-accent/15 text-ds-accent hover:bg-ds-accent/20 hover:text-ds-accent'
                  : 'border-transparent text-ds-muted hover:bg-ds-bg hover:text-ds-text'
              }`}
              data-audience-option={view}
              data-selected={selected ? 'true' : 'false'}
              title={optionHint}
            >
              <span>{optionLabel}</span>
            </Button>
          );
        })}
      </div>
    </div>
  );
}
