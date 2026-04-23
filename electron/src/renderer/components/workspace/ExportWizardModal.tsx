/**
 * Workspace export wizard modal.
 *
 * Multi-step wizard that drives `POST /api/export/file` for individual
 * workspace artifacts. Format options derive from the renderer's current
 * exportable file snapshot, while the backend remains authoritative for the
 * actual export execution.
 *
 * The component is transport-aware but otherwise pure render: callers pass an
 * exporter port plus the candidate list, the wizard owns step state and
 * focus/keyboard handling.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Download, Loader2, X } from 'lucide-react';
import {
  AUDIENCE_VIEW_IDS,
  type AudienceView,
} from '../../domain/workspace/audienceView';
import { useI18n } from '../../stores/i18nStore';

export interface ExportWizardCandidate {
  id: string;
  name: string;
  path: string;
  type: string;
  formats: readonly string[];
}

export interface ExportWizardResult {
  path: string;
  format: string;
  audience: AudienceView;
  exported: Record<string, unknown>;
}

export type ExportPort = (input: {
  path: string;
  format: string;
  audience: AudienceView;
}) => Promise<Record<string, unknown>>;

interface Props {
  open: boolean;
  candidates: readonly ExportWizardCandidate[];
  defaultAudience: AudienceView;
  exportPort: ExportPort;
  onClose: () => void;
  onSuccess?: (result: ExportWizardResult) => void;
}

type WizardStep = 1 | 2 | 3;

export function ExportWizardModal({
  open,
  candidates,
  defaultAudience,
  exportPort,
  onClose,
  onSuccess,
}: Props) {
  const { t } = useI18n();
  const dialogRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  const [step, setStep] = useState<WizardStep>(1);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [selectedFormat, setSelectedFormat] = useState<string | null>(null);
  const [selectedAudience, setSelectedAudience] = useState<AudienceView>(defaultAudience);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<ExportWizardResult | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    previouslyFocused.current = (document.activeElement as HTMLElement | null) ?? null;
    setStep(1);
    setSelectedCandidateId(candidates[0]?.id ?? null);
    setSelectedFormat(candidates[0]?.formats[0] ?? null);
    setSelectedAudience(defaultAudience);
    setBusy(false);
    setError(null);
    setSuccess(null);
    queueMicrotask(() => {
      dialogRef.current?.focus();
    });
    return () => {
      previouslyFocused.current?.focus();
    };
  }, [open, candidates, defaultAudience]);

  const selectedCandidate = useMemo(
    () => candidates.find((entry) => entry.id === selectedCandidateId) ?? null,
    [candidates, selectedCandidateId],
  );

  if (!open) {
    return null;
  }

  const canAdvance = step === 1
    ? Boolean(selectedCandidate)
    : step === 2
      ? Boolean(selectedFormat)
      : true;

  const handleNext = () => {
    if (!canAdvance) return;
    if (step === 1) {
      const fallback = selectedCandidate?.formats[0] ?? null;
      if (selectedFormat === null || selectedCandidate?.formats.includes(selectedFormat) !== true) {
        setSelectedFormat(fallback);
      }
      setStep(2);
      return;
    }
    if (step === 2) {
      setStep(3);
    }
  };

  const handleBack = () => {
    if (step === 1) return;
    setError(null);
    setStep((prev) => (prev === 3 ? 2 : 1) as WizardStep);
  };

  const handleExport = async () => {
    if (!selectedCandidate || !selectedFormat || busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const exported = await exportPort({
        path: selectedCandidate.path,
        format: selectedFormat,
        audience: selectedAudience,
      });
      const result: ExportWizardResult = {
        path: selectedCandidate.path,
        format: selectedFormat,
        audience: selectedAudience,
        exported,
      };
      setSuccess(result);
      onSuccess?.(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : t('approval:grant.list.error', { message: '' });
      setError(message || t('exportWizard.error.fallback'));
    } finally {
      setBusy(false);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-6 backdrop-blur-sm"
      onKeyDown={handleKeyDown}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="export-wizard-title"
        tabIndex={-1}
        className="flex w-[min(560px,100%)] flex-col overflow-hidden rounded-2xl border border-ds-border bg-ds-surface shadow-2xl"
      >
        <header className="border-b border-ds-border bg-ds-bg/40 px-5 py-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ds-muted">
                {t('exportWizard.heading')}
              </p>
              <h2 id="export-wizard-title" className="mt-2 text-base font-semibold text-ds-text">
                {step === 1
                  ? t('exportWizard.step1.title')
                  : step === 2
                    ? t('exportWizard.step2.title')
                    : t('exportWizard.step3.title')}
              </h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full border border-ds-border bg-ds-surface px-2 py-1 text-ds-muted transition hover:text-ds-text"
              aria-label={t('exportWizard.button.close')}
            >
              <X size={14} />
            </button>
          </div>
        </header>

        <section className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
          {success ? (
            <SuccessPanel result={success} />
          ) : step === 1 ? (
            <CandidatePicker
              candidates={candidates}
              selectedCandidateId={selectedCandidateId}
              onSelect={(id) => setSelectedCandidateId(id)}
            />
          ) : step === 2 ? (
            <div className="space-y-5">
              <FormatPicker
                candidate={selectedCandidate}
                selectedFormat={selectedFormat}
                onSelect={setSelectedFormat}
              />
              <AudiencePicker
                selectedAudience={selectedAudience}
                onSelect={setSelectedAudience}
              />
            </div>
          ) : (
            <ConfirmPanel
              candidate={selectedCandidate}
              format={selectedFormat}
              audience={selectedAudience}
              error={error}
            />
          )}
        </section>

        <footer className="border-t border-ds-border bg-ds-bg/40 px-5 py-4">
          <div className="flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={handleBack}
              disabled={step === 1 || busy || Boolean(success)}
              className="inline-flex items-center gap-2 rounded-xl border border-ds-border bg-ds-surface px-3 py-2 text-sm text-ds-muted transition hover:text-ds-text disabled:opacity-40"
            >
              <ChevronLeft size={14} /> {t('exportWizard.button.back')}
            </button>
            {success ? (
              <button
                type="button"
                onClick={onClose}
                className="inline-flex items-center gap-2 rounded-xl bg-ds-accent px-4 py-2 text-sm font-medium text-white"
              >
                {t('exportWizard.button.close')}
              </button>
            ) : step === 3 ? (
              <button
                type="button"
                onClick={handleExport}
                disabled={!selectedCandidate || !selectedFormat || busy}
                className="inline-flex items-center gap-2 rounded-xl bg-ds-accent px-4 py-2 text-sm font-medium text-white transition hover:brightness-110 disabled:opacity-50"
              >
                {busy ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                {busy ? t('exportWizard.button.exporting') : t('exportWizard.button.export')}
              </button>
            ) : (
              <button
                type="button"
                onClick={handleNext}
                disabled={!canAdvance}
                className="inline-flex items-center gap-2 rounded-xl bg-ds-accent px-4 py-2 text-sm font-medium text-white transition hover:brightness-110 disabled:opacity-50"
              >
                {t('exportWizard.button.next')} <ChevronRight size={14} />
              </button>
            )}
          </div>
        </footer>
      </div>
    </div>
  );
}

function CandidatePicker({
  candidates,
  selectedCandidateId,
  onSelect,
}: {
  candidates: readonly ExportWizardCandidate[];
  selectedCandidateId: string | null;
  onSelect: (id: string) => void;
}) {
  const { t } = useI18n();

  if (candidates.length === 0) {
    return (
      <p className="rounded-xl border border-ds-border bg-ds-bg/40 px-4 py-6 text-sm text-ds-muted">
        {t('exportWizard.step1.empty')}
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm leading-6 text-ds-muted">{t('exportWizard.step1.description')}</p>
      <div className="space-y-2" role="radiogroup" aria-label={t('exportWizard.step1.title')}>
        {candidates.map((candidate) => (
          <label
            key={candidate.id}
            className={`flex cursor-pointer items-start gap-3 rounded-xl border px-3 py-3 transition ${
              selectedCandidateId === candidate.id
                ? 'border-ds-accent bg-ds-accent/10'
                : 'border-ds-border bg-ds-surface/70 hover:border-ds-accent/50'
            }`}
          >
            <input
              type="radio"
              name="export-candidate"
              checked={selectedCandidateId === candidate.id}
              onChange={() => onSelect(candidate.id)}
              className="mt-1"
            />
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-ds-text">{candidate.name}</div>
              <div className="mt-1 truncate text-xs text-ds-muted">{candidate.path}</div>
              <div className="mt-2 flex flex-wrap gap-1">
                {candidate.formats.map((format) => (
                  <span
                    key={format}
                    className="rounded-full border border-ds-border bg-ds-bg/40 px-2 py-0.5 text-[11px] text-ds-muted"
                  >
                    {format}
                  </span>
                ))}
              </div>
            </div>
          </label>
        ))}
      </div>
    </div>
  );
}

function FormatPicker({
  candidate,
  selectedFormat,
  onSelect,
}: {
  candidate: ExportWizardCandidate | null;
  selectedFormat: string | null;
  onSelect: (format: string) => void;
}) {
  const { t } = useI18n();

  if (!candidate) {
    return null;
  }

  return (
    <div className="space-y-3">
      <p className="text-sm leading-6 text-ds-muted">{t('exportWizard.step2.description')}</p>
      <div className="space-y-2" role="radiogroup" aria-label={t('exportWizard.step2.title')}>
        {candidate.formats.map((format) => (
          <label
            key={format}
            className={`flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-3 transition ${
              selectedFormat === format
                ? 'border-ds-accent bg-ds-accent/10'
                : 'border-ds-border bg-ds-surface/70 hover:border-ds-accent/50'
            }`}
          >
            <input
              type="radio"
              name="export-format"
              checked={selectedFormat === format}
              onChange={() => onSelect(format)}
            />
            <span className="text-sm font-medium text-ds-text">{format.toUpperCase()}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

function AudiencePicker({
  selectedAudience,
  onSelect,
}: {
  selectedAudience: AudienceView;
  onSelect: (audience: AudienceView) => void;
}) {
  const { t } = useI18n();

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-ds-text">
          {t('exportWizard.step2.audienceTitle')}
        </h3>
        <p className="mt-1 text-sm leading-6 text-ds-muted">
          {t('exportWizard.step2.audienceDescription')}
        </p>
      </div>
      <div className="space-y-2" role="radiogroup" aria-label={t('exportWizard.step2.audienceTitle')}>
        {AUDIENCE_VIEW_IDS.map((audience) => (
          <label
            key={audience}
            className={`flex cursor-pointer items-start gap-3 rounded-xl border px-3 py-3 transition ${
              selectedAudience === audience
                ? 'border-ds-accent bg-ds-accent/10'
                : 'border-ds-border bg-ds-surface/70 hover:border-ds-accent/50'
            }`}
          >
            <input
              type="radio"
              name="export-audience"
              checked={selectedAudience === audience}
              onChange={() => onSelect(audience)}
              className="mt-1"
            />
            <div className="min-w-0">
              <div className="text-sm font-medium text-ds-text">
                {t(`workspace:audienceView.option.${audience}`)}
              </div>
              <div className="mt-1 text-xs leading-5 text-ds-muted">
                {t(`workspace:audienceView.option.${audience}Hint`)}
              </div>
            </div>
          </label>
        ))}
      </div>
    </div>
  );
}

function ConfirmPanel({
  candidate,
  format,
  audience,
  error,
}: {
  candidate: ExportWizardCandidate | null;
  format: string | null;
  audience: AudienceView;
  error: string | null;
}) {
  const { t } = useI18n();

  if (!candidate || !format) {
    return null;
  }

  return (
    <div className="space-y-4">
      <dl className="space-y-3">
        <div className="rounded-xl border border-ds-border bg-ds-bg/40 px-4 py-3">
          <dt className="text-[11px] uppercase tracking-[0.14em] text-ds-muted">
            {t('exportWizard.step3.targetLabel')}
          </dt>
          <dd className="mt-1 text-sm text-ds-text">
            <div className="font-medium">{candidate.name}</div>
            <div className="mt-1 truncate text-xs text-ds-muted">{candidate.path}</div>
          </dd>
        </div>
        <div className="rounded-xl border border-ds-border bg-ds-bg/40 px-4 py-3">
          <dt className="text-[11px] uppercase tracking-[0.14em] text-ds-muted">
            {t('exportWizard.step3.formatLabel')}
          </dt>
          <dd className="mt-1 text-sm font-medium text-ds-text">{format.toUpperCase()}</dd>
        </div>
        <div className="rounded-xl border border-ds-border bg-ds-bg/40 px-4 py-3">
          <dt className="text-[11px] uppercase tracking-[0.14em] text-ds-muted">
            {t('exportWizard.step3.audienceLabel')}
          </dt>
          <dd className="mt-1 text-sm font-medium text-ds-text">
            {t(`workspace:audienceView.option.${audience}`)}
          </dd>
        </div>
      </dl>
      <p className="text-xs leading-relaxed text-ds-muted">{t('exportWizard.step3.note')}</p>
      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-100">
          <div className="font-semibold">{t('exportWizard.error.title')}</div>
          <div className="mt-1">{error}</div>
        </div>
      )}
    </div>
  );
}

function SuccessPanel({ result }: { result: ExportWizardResult }) {
  const { t } = useI18n();
  const exportedPath = pickExportedPath(result.exported) ?? result.path;
  return (
    <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-4 text-sm text-emerald-100">
      <div className="font-semibold">{t('exportWizard.success.title')}</div>
      <div className="mt-2">
        {t('exportWizard.success.description', {
          format: result.format.toUpperCase(),
          audience: t(`workspace:audienceView.option.${result.audience}`),
          path: exportedPath,
        })}
      </div>
    </div>
  );
}

function pickExportedPath(payload: Record<string, unknown>): string | null {
  const directExportPath = payload['exportPath'];
  if (typeof directExportPath === 'string' && directExportPath.trim().length > 0) {
    return directExportPath;
  }
  const direct = payload['path'];
  if (typeof direct === 'string' && direct.trim().length > 0) {
    return direct;
  }
  const nested = payload['export'];
  if (nested && typeof nested === 'object') {
    const nestedExportPath = (nested as Record<string, unknown>)['exportPath'];
    if (typeof nestedExportPath === 'string' && nestedExportPath.trim().length > 0) {
      return nestedExportPath;
    }
    const inner = (nested as Record<string, unknown>)['path'];
    if (typeof inner === 'string' && inner.trim().length > 0) {
      return inner;
    }
    const file = (nested as Record<string, unknown>)['file'];
    if (typeof file === 'string' && file.trim().length > 0) {
      return file;
    }
  }
  return null;
}
