import { Select } from '../../design-system/primitives';
import { useI18n } from '../../stores/i18nStore';
import { useConfigStore } from '../../stores/configStore';
import type { DeepLinkReauthPolicy } from '../../application/deepLink/handleDeepLink';

const REAUTH_OPTIONS: ReadonlyArray<{
  readonly value: DeepLinkReauthPolicy;
  readonly labelKey: string;
}> = [
  { value: 'none', labelKey: 'settings.deepLink.reauth.none' },
  { value: 'once-per-session', labelKey: 'settings.deepLink.reauth.oncePerSession' },
  { value: 'always', labelKey: 'settings.deepLink.reauth.always' },
];

export function DeepLinkSettings() {
  const { t } = useI18n();
  const policy = useConfigStore((state) => state.deepLinkReauth);
  const setPolicy = useConfigStore((state) => state.setDeepLinkReauth);

  return (
    <div className="rounded-lg border border-ds-border bg-ds-bg p-3">
      <Select
        id="deep-link-reauth-selector"
        label={t('settings.deepLink.reauth.label')}
        description={t('settings.deepLink.reauth.description')}
        value={policy}
        onChange={(event) => setPolicy(event.target.value as DeepLinkReauthPolicy)}
        options={REAUTH_OPTIONS.map((option) => ({
          value: option.value,
          label: t(option.labelKey),
        }))}
      />
    </div>
  );
}
