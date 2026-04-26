import { Globe } from 'lucide-react';
import { useState } from 'react';

import { Select } from '../../design-system/primitives';
import { LOCALE_OPTIONS, type Locale } from '../../stores/i18nStore';
import { useI18n } from '../../stores/i18nStore';

interface Props {
  value: Locale;
  onChange: (locale: Locale) => void | Promise<void>;
  id?: string;
  labelKey?: string;
  descriptionKey?: string;
  compact?: boolean;
}

export function LocaleSelector({
  value,
  onChange,
  id = 'locale-selector',
  labelKey = 'settings.language.label',
  descriptionKey = 'settings.language.description',
  compact = false,
}: Props) {
  const { t } = useI18n();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const descriptionId = descriptionKey ? `${id}-description` : undefined;

  const handleChange = async (next: Locale) => {
    setErrorMessage(null);
    try {
      await onChange(next);
    } catch (error) {
      console.warn('[LocaleSelector] language update failed:', error);
      setErrorMessage(
        t('settings.language.errorSyncFailed', {
          message: error instanceof Error ? error.message : String(error),
        }),
      );
    }
  };

  return (
    <div className={compact ? 'flex items-start justify-between gap-4' : 'space-y-2'}>
      <div className="flex min-w-0 items-start gap-2">
        <Globe size={14} className="mt-0.5 shrink-0 text-ds-muted" aria-hidden="true" />
        <div className="min-w-0">
          <label htmlFor={id} className="block text-xs font-medium text-ds-text">
            {t(labelKey)}
          </label>
          {descriptionKey && (
            <p id={descriptionId} className="mt-1 text-[11px] leading-5 text-ds-muted">
              {t(descriptionKey)}
            </p>
          )}
        </div>
      </div>

      <div className={compact ? 'shrink-0' : ''}>
        <Select
          id={id}
          value={value}
          onChange={(event) => void handleChange(event.target.value as Locale)}
          aria-describedby={descriptionId}
          options={LOCALE_OPTIONS.map((option) => ({
            value: option.code,
            label: `${option.nativeLabel} (${option.englishLabel})`,
          }))}
          className="min-w-[160px]"
        />
      </div>
      {errorMessage ? (
        <p role="alert" className="text-[11px] text-ds-error">
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}
