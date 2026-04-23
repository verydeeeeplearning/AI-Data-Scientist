import { useEffect, useMemo, useState, type ReactElement } from 'react';
import { useTranslation } from 'react-i18next';

type SubjectSource = 'config' | 'env' | null;

interface WebPushSubjectBridge {
  getSubject: () => Promise<{
    ok: boolean;
    subject?: string | null;
    source?: SubjectSource;
    reason?: string;
  }>;
  setSubject: (payload: { subject: string }) => Promise<{
    ok: boolean;
    subject?: string | null;
    source?: SubjectSource;
    error?: string;
  }>;
}

export function normalizeVapidSubject(value: string): string {
  return value.trim();
}

export function isValidVapidSubject(value: string): boolean {
  const normalized = normalizeVapidSubject(value);
  return normalized.startsWith('mailto:') || normalized.startsWith('https://');
}

function getBridge(): WebPushSubjectBridge | undefined {
  return window.electronAPI?.webPush;
}

function getSourceLabelKey(source: SubjectSource): string {
  if (source === 'config') return 'mobile.push.subject.source.config';
  if (source === 'env') return 'mobile.push.subject.source.env';
  return 'mobile.push.subject.source.unset';
}

export function VapidSubjectField(): ReactElement {
  const { t } = useTranslation('mobile');
  const bridge = useMemo(() => getBridge(), []);
  const [subject, setSubject] = useState('');
  const [source, setSource] = useState<SubjectSource>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!bridge) {
      setIsLoading(false);
      setErrorMessage(t('mobile.push.error.bridgeMissing'));
      return () => {
        cancelled = true;
      };
    }

    (async () => {
      const response = await bridge.getSubject();
      if (cancelled) return;
      if (!response.ok) {
        setErrorMessage(response.reason ?? t('mobile.push.subject.error.load'));
        setIsLoading(false);
        return;
      }
      setSubject(response.subject ?? '');
      setSource(response.source ?? null);
      setErrorMessage(null);
      setSavedMessage(null);
      setIsLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [bridge, t]);

  const normalizedSubject = normalizeVapidSubject(subject);
  const canSave = Boolean(bridge) && !isLoading && !isSaving && isValidVapidSubject(normalizedSubject);

  const handleSave = async () => {
    if (!bridge) {
      setErrorMessage(t('mobile.push.error.bridgeMissing'));
      return;
    }
    const trimmed = normalizeVapidSubject(subject);
    if (!isValidVapidSubject(trimmed)) {
      setErrorMessage(t('mobile.push.subject.error.format'));
      setSavedMessage(null);
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);
    setSavedMessage(null);
    try {
      const response = await bridge.setSubject({ subject: trimmed });
      if (!response.ok) {
        setErrorMessage(response.error ?? t('mobile.push.subject.error.save'));
        return;
      }
      setSubject(response.subject ?? trimmed);
      setSource(response.source ?? 'config');
      setSavedMessage(t('mobile.push.subject.status.saved'));
    } catch (error) {
      const message = error instanceof Error ? error.message : t('mobile.push.subject.error.save');
      setErrorMessage(message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section className="rounded-2xl border border-ds-border bg-ds-surface/70 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ds-text">
            {t('mobile.push.subject.label')}
          </h3>
          <p className="mt-1 text-xs leading-5 text-ds-muted">
            {t('mobile.push.subject.help')}
          </p>
        </div>
        <span className="rounded-full border border-ds-border/70 px-2 py-1 text-[11px] uppercase tracking-[0.16em] text-ds-muted">
          {t(getSourceLabelKey(source))}
        </span>
      </div>
      <label className="mt-3 block">
        <span className="sr-only">{t('mobile.push.subject.label')}</span>
        <input
          type="text"
          value={subject}
          onChange={(event) => {
            setSubject(event.target.value);
            setErrorMessage(null);
            setSavedMessage(null);
          }}
          placeholder={t('mobile.push.subject.placeholder')}
          className="mt-1 w-full rounded-xl border border-ds-border bg-ds-bg/70 px-3 py-2 text-sm text-ds-text placeholder:text-ds-muted focus:border-ds-accent focus:outline-none"
          inputMode="text"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
        />
      </label>
      <p className="mt-2 text-xs leading-5 text-ds-muted">
        {t('mobile.push.subject.description')}
      </p>
      {savedMessage ? (
        <p className="mt-2 text-xs text-emerald-300" role="status" aria-live="polite">
          {savedMessage}
        </p>
      ) : null}
      {errorMessage ? (
        <p className="mt-2 text-xs text-rose-300" role="alert">
          {errorMessage}
        </p>
      ) : null}
      <div className="mt-3 flex items-center justify-between gap-3">
        <p className="text-[11px] leading-5 text-ds-muted">
          {normalizedSubject.length > 0 && isValidVapidSubject(normalizedSubject)
            ? t('mobile.push.subject.validation.ok')
            : t('mobile.push.subject.validation.hint')}
        </p>
        <button
          type="button"
          onClick={() => {
            void handleSave();
          }}
          disabled={!canSave}
          className="rounded-full border border-ds-border px-3 py-1 text-xs text-ds-text disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSaving ? t('mobile.push.subject.button.saving') : t('mobile.push.subject.button.save')}
        </button>
      </div>
    </section>
  );
}
