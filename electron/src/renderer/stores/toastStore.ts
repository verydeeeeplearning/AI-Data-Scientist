import { create } from 'zustand';

export type AppToastTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger';

export interface AppToast {
  readonly id: string;
  readonly title: string;
  readonly description?: string;
  readonly tone: AppToastTone;
  readonly createdAt: number;
}

interface ToastState {
  readonly toasts: readonly AppToast[];
  readonly pushToast: (toast: Omit<AppToast, 'id' | 'createdAt'>) => string;
  readonly dismissToast: (id: string) => void;
}

let toastCounter = 0;

function nextToastId(): string {
  toastCounter += 1;
  return `toast-${toastCounter}-${Date.now().toString(36)}`;
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  pushToast: (toast) => {
    const id = nextToastId();
    set((state) => ({
      toasts: [
        ...state.toasts,
        {
          ...toast,
          id,
          createdAt: Date.now(),
        },
      ],
    }));
    return id;
  },
  dismissToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((toast) => toast.id !== id),
    })),
}));

