import { useEffect, useMemo, useRef } from 'react';
import { UploadCloud } from 'lucide-react';
import { createFocusTrap } from '../../application/a11y/focusManagement';
import { prefersReducedMotion } from '../../application/a11y/reducedMotion';
import type { UploadedFileResult } from '../../domain/workspace/uploadedFile';
import { useGlobalFileDrop } from '../../hooks/useGlobalFileDrop';
import { useI18n } from '../../stores/i18nStore';
import { UploadErrorState } from './UploadErrorState';

interface Props {
  onUploadFile: (file: File) => Promise<UploadedFileResult>;
}

export function GlobalDropOverlay({ onUploadFile }: Props) {
  const { t } = useI18n();
  const { state, dismissError, retry } = useGlobalFileDrop({ uploadFile: onUploadFile });
  const overlayRef = useRef<HTMLDivElement>(null);
  const trapRef = useRef<ReturnType<typeof createFocusTrap> | null>(null);
  const reduce = useMemo(() => prefersReducedMotion(), []);

  useEffect(() => {
    if (state.phase !== 'active') {
      trapRef.current?.deactivate();
      trapRef.current = null;
      return;
    }
    if (!overlayRef.current) return;
    const trap = createFocusTrap(overlayRef.current);
    trapRef.current = trap;
    trap.activate();
    return () => {
      trap.deactivate();
      trapRef.current = null;
    };
  }, [state.phase]);

  const showOverlay = state.phase === 'active' || state.phase === 'uploading';
  const transitionClass = reduce ? '' : 'transition-opacity duration-150';

  return (
    <>
      {showOverlay && (
        <div
          ref={overlayRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby="global-drop-overlay-title"
          aria-describedby="global-drop-overlay-description"
          tabIndex={-1}
          className={`
            pointer-events-none fixed inset-0 z-[2000] flex items-center justify-center
            bg-ds-bg/80 backdrop-blur-sm ${transitionClass}
          `}
        >
          <div
            className={`
              pointer-events-auto mx-4 flex w-full max-w-md flex-col items-center gap-3
              rounded-2xl border-2 border-dashed border-ds-accent/70 bg-ds-surface/90 px-8 py-10
              shadow-2xl ${transitionClass}
            `}
          >
            <div className="rounded-full bg-ds-accent/15 p-4 text-ds-accent">
              <UploadCloud size={36} aria-hidden="true" />
            </div>
            <div
              id="global-drop-overlay-title"
              className="text-center text-base font-semibold text-ds-text"
            >
              {t('workspace.dropOverlay.title')}
            </div>
            <div
              id="global-drop-overlay-description"
              className="text-center text-[12px] leading-5 text-ds-muted"
            >
              {t('workspace.dropOverlay.description')}
            </div>
            <div className="text-center text-[10px] text-ds-muted">
              {t('workspace.dropOverlay.cancel')}
            </div>
          </div>
        </div>
      )}

      {state.lastError && (
        <div className="pointer-events-auto fixed bottom-12 right-4 z-[2100] w-full max-w-sm">
          <UploadErrorState
            error={state.lastError}
            onRetry={retry}
            onDismiss={dismissError}
          />
        </div>
      )}
    </>
  );
}
