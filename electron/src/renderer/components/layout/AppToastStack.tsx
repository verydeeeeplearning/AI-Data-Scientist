import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react';
import { useEffect, useMemo } from 'react';

import { Toast, ToastViewport } from '../../design-system/primitives';
import { useI18n } from '../../stores/i18nStore';
import { useToastStore, type AppToastTone } from '../../stores/toastStore';

const TOAST_TTL_MS = 6000;
const VISIBLE_LIMIT = 3;

function ToastIcon({ tone }: { readonly tone: AppToastTone }) {
  const props = { size: 14, className: 'shrink-0' };
  if (tone === 'success') {
    return <CheckCircle2 {...props} />;
  }
  if (tone === 'warning') {
    return <AlertTriangle {...props} />;
  }
  if (tone === 'danger') {
    return <XCircle {...props} />;
  }
  return <Info {...props} />;
}

export function AppToastStack() {
  const t = useI18n((state) => state.t);
  const toasts = useToastStore((state) => state.toasts);
  const dismissToast = useToastStore((state) => state.dismissToast);
  const visible = useMemo(() => toasts.slice(-VISIBLE_LIMIT), [toasts]);

  useEffect(() => {
    if (visible.length === 0) {
      return;
    }
    const timers = visible.map((toast) =>
      window.setTimeout(() => dismissToast(toast.id), TOAST_TTL_MS),
    );
    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [dismissToast, visible]);

  if (visible.length === 0) {
    return null;
  }

  return (
    <ToastViewport
      placement="bottom-right"
      label={t('common.notifications')}
      className="z-50 max-w-[360px]"
    >
      {visible.map((toast) => (
        <Toast
          key={toast.id}
          title={toast.title}
          description={toast.description}
          tone={toast.tone}
          leadingIcon={<ToastIcon tone={toast.tone} />}
          announce={toast.tone === 'danger' || toast.tone === 'warning' ? 'assertive' : 'polite'}
          onDismiss={() => dismissToast(toast.id)}
          dismissLabel={t('common.close')}
          className="text-xs"
        />
      ))}
    </ToastViewport>
  );
}
