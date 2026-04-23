import { useCallback, useEffect, useState } from 'react';
import { announce } from '../application/a11y/ariaLive';
import { classifyUploadError } from '../application/workspace/classifyUploadError';
import {
  createInitialDropOverlayState,
  isDataTransferFileLike,
  reduceDragEntered,
  reduceDragLeft,
  reduceDropCompleted,
  reduceUploadFailed,
  reduceUploadSucceeded,
  type DropOverlayState,
  type UploadErrorInfo,
} from '../domain/workspace/globalDropOverlay';
import type { UploadedFileResult } from '../domain/workspace/uploadedFile';
import { useI18n } from '../stores/i18nStore';

interface UseGlobalFileDropArgs {
  uploadFile: (file: File) => Promise<UploadedFileResult>;
}

interface UseGlobalFileDropResult {
  state: DropOverlayState;
  dismissError: () => void;
  retry: (() => void) | null;
}

export function useGlobalFileDrop({
  uploadFile,
}: UseGlobalFileDropArgs): UseGlobalFileDropResult {
  const { t } = useI18n();
  const [state, setState] = useState<DropOverlayState>(createInitialDropOverlayState);
  const [lastFiles, setLastFiles] = useState<File[] | null>(null);

  const announceError = useCallback(
    (error: UploadErrorInfo) => {
      announce(
        t('workspace.dropOverlay.announce.uploadFailed', { message: error.message }),
        { politeness: 'assertive' },
      );
    },
    [t],
  );

  const handleFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0) {
        setState((prev) => reduceUploadSucceeded(prev));
        return;
      }
      setLastFiles(files);
      setState((prev) => reduceDropCompleted(prev));
      announce(t('workspace.dropOverlay.announce.uploadStarted', { count: files.length }));

      let lastError: UploadErrorInfo | null = null;
      let successCount = 0;
      for (const file of files) {
        try {
          await uploadFile(file);
          successCount += 1;
        } catch (err) {
          lastError = classifyUploadError(err, { fileName: file.name });
        }
      }

      if (lastError && successCount === 0) {
        setState((prev) => reduceUploadFailed(prev, lastError as UploadErrorInfo));
        announceError(lastError);
        return;
      }

      setState((prev) => reduceUploadSucceeded(prev));
      announce(t('workspace.dropOverlay.announce.uploadCompleted', { count: successCount }));
      if (lastError) {
        announceError(lastError);
      }
    },
    [announceError, t, uploadFile],
  );

  useEffect(() => {
    function handleDragEnter(event: DragEvent) {
      if (!isDataTransferFileLike(event.dataTransfer)) return;
      event.preventDefault();
      setState((prev) => {
        const next = reduceDragEntered(prev);
        if (prev.phase !== 'active' && next.phase === 'active') {
          announce(t('workspace.dropOverlay.announce.entered'));
        }
        return next;
      });
    }

    function handleDragOver(event: DragEvent) {
      if (!isDataTransferFileLike(event.dataTransfer)) return;
      event.preventDefault();
      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = 'copy';
      }
    }

    function handleDragLeave(event: DragEvent) {
      if (!isDataTransferFileLike(event.dataTransfer)) return;
      setState((prev) => {
        const next = reduceDragLeft(prev);
        if (prev.phase === 'active' && next.phase === 'idle') {
          announce(t('workspace.dropOverlay.announce.cancelled'));
        }
        return next;
      });
    }

    function handleDrop(event: DragEvent) {
      if (!isDataTransferFileLike(event.dataTransfer)) return;
      event.preventDefault();
      const files = Array.from(event.dataTransfer?.files ?? []);
      void handleFiles(files);
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== 'Escape') return;
      setState((prev) => {
        if (prev.phase !== 'active') return prev;
        announce(t('workspace.dropOverlay.announce.cancelled'));
        return createInitialDropOverlayState();
      });
    }

    window.addEventListener('dragenter', handleDragEnter);
    window.addEventListener('dragover', handleDragOver);
    window.addEventListener('dragleave', handleDragLeave);
    window.addEventListener('drop', handleDrop);
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('dragenter', handleDragEnter);
      window.removeEventListener('dragover', handleDragOver);
      window.removeEventListener('dragleave', handleDragLeave);
      window.removeEventListener('drop', handleDrop);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleFiles, t]);

  const dismissError = useCallback(() => {
    setState((prev) => ({ ...prev, lastError: null }));
  }, []);

  const retry = lastFiles && lastFiles.length > 0
    ? () => {
        void handleFiles(lastFiles);
      }
    : null;

  return { state, dismissError, retry };
}
